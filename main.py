# Description: An asynchronous script to fetch recent Reddit posts from specified subreddits,
# analyze them with a language model to identify business opportunities, and generate reports.

import os
import praw
from datetime import datetime
from dotenv import load_dotenv
from litellm import acompletion
import asyncio

# --- CONFIGURATION ---
# Define the subreddits to analyze.
SUBREDDITS = ["indiehackers"]

POST_LIMIT = 15  # Number of posts to fetch from each subreddit.
MODEL = "gemini/gemini-2.5-flash"  # The language model to use for analysis.
SAVE_REDDIT_DUMPS = True  # If True, saves raw Reddit content to a file.

# --- PRAW RATE LIMIT CONFIGURATION ---
# To stay within Reddit's API rate limits (~60 requests/minute),
# we limit concurrent PRAW requests.
REDDIT_API_CONCURRENCY_LIMIT = 1
reddit_semaphore = asyncio.Semaphore(REDDIT_API_CONCURRENCY_LIMIT)

# Set to an integer to limit comment depth and reduce API calls, or None to fetch all.
LIMIT_COMMENT_DEPTH = None

# Load environment variables from a .env file.
load_dotenv()

# --- API INITIALIZATION ---
reddit = praw.Reddit(
    client_id=os.getenv("REDDIT_CLIENT_ID"),
    client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
    user_agent=os.getenv("REDDIT_USER_AGENT"),
)

# --- FILE PATHS ---
SEEN_LINKS_FILE = "seen_links2.txt"
REPORTS_DIR = "reports"
DUMPS_DIR = "reddit_dumps"

# Create directories if they don't exist.
os.makedirs(REPORTS_DIR, exist_ok=True)
if SAVE_REDDIT_DUMPS:
    os.makedirs(DUMPS_DIR, exist_ok=True)


# ==============================================================================
# === ASYNCHRONOUS LLM & HELPER FUNCTIONS ===
# ==============================================================================
async def llm(prompt_text: str) -> str:
    """
    Asynchronously sends a prompt to the LLM and returns the response, handling errors.
    """
    try:
        response = await acompletion(
            model=MODEL,
            messages=[{"role": "user", "content": prompt_text}],
            temperature=0.7,
        )

        # Check for an empty response, which can indicate content filtering.
        if not response.choices or not response.choices[0].message.content:
            print("  [!] LLM returned a successful but EMPTY response. This may be due to safety filters.")
            return "Error: The LLM API returned an empty response, possibly due to content safety filters."

        return response.choices[0].message.content

    except Exception as e:
        print(f"  [!] LLM API Error: {e}")
        return f"Error: The LLM API call failed with an exception. Details: {e}"


def load_seen_links():
    """Loads the set of previously processed post URLs from a file."""
    if not os.path.exists(SEEN_LINKS_FILE):
        return set()
    with open(SEEN_LINKS_FILE, "r") as f:
        return set(line.strip() for line in f)


def save_seen_links(links):
    """Saves the set of processed post URLs to a file."""
    with open(SEEN_LINKS_FILE, "w") as f:
        for link in links:
            f.write(link + "\n")


def fetch_subreddit_posts_sync(subreddit_name, seen_links, post_limit, comment_depth_limit):
    """
    Synchronous function to fetch posts and comments from a subreddit.
    Designed to be run in a separate thread to avoid blocking asyncio event loop.
    """
    print(f"\n--- [Thread] Starting data fetch for r/{subreddit_name} ---")
    all_content_for_llm = []
    new_links_found = []

    try:
        subreddit = reddit.subreddit(subreddit_name)
        for post in subreddit.hot(limit=post_limit):
            if post.stickied or post.url in seen_links:
                continue

            print(f"  [+] Collecting content from r/{subreddit_name}: {post.title[:50]}...")

            post_content = f"### Post Title: {post.title}\nLink: {post.url}\n\n**Post Body:**\n{post.selftext}\n\n"

            # Fetch and flatten the comment tree.
            post.comments.replace_more(limit=comment_depth_limit)

            comment_buffer = [
                f"- {comment.body}\n"
                for comment in post.comments.list()
                if hasattr(comment, "body") and comment.body not in ("[deleted]", "[removed]")
            ]

            if comment_buffer:
                post_content += f"**Comments ({len(comment_buffer)}):**\n" + "".join(comment_buffer)
            else:
                post_content += "**No comments.**"

            all_content_for_llm.append(post_content + "\n\n---\n\n")
            new_links_found.append(post.url)

    except Exception as e:
        print(f"  [!] Reddit API Error in sync thread for r/{subreddit_name}: {e}")
        return f"Error: Could not fetch data from Reddit. Details: {e}", []

    return "".join(all_content_for_llm), new_links_found


async def process_subreddit(subreddit_name, seen_links):
    """
    Asynchronously fetches, analyzes, and generates a report for a single subreddit.
    """
    # 1. Fetch data from Reddit in a separate thread to avoid blocking.
    async with reddit_semaphore:
        combined_content, new_links = await asyncio.to_thread(
            fetch_subreddit_posts_sync, subreddit_name, seen_links, POST_LIMIT, LIMIT_COMMENT_DEPTH
        )

    # 2. Handle cases where fetching failed or returned no new content.
    if not combined_content or "Error:" in combined_content:
        error_summary = combined_content or f"Error: No new content found for r/{subreddit_name}."
        print(f"  [*] Skipping LLM analysis for r/{subreddit_name} due to fetch error or no new content.")
        return {"name": subreddit_name, "summary": error_summary}, []

    # 3. Truncate content if it exceeds the model's approximate context window.
    MAX_CHARS_FOR_LLM = 1000000
    if len(combined_content) > MAX_CHARS_FOR_LLM:
        print(f"  [!] Content for r/{subreddit_name} is {len(combined_content)} chars, truncating to {MAX_CHARS_FOR_LLM}.")
        combined_content = combined_content[:MAX_CHARS_FOR_LLM]

    # 4. Save the raw text dump if enabled.
    if SAVE_REDDIT_DUMPS:
        today = datetime.now().strftime("%Y-%m-%d")
        dump_filename = os.path.join(DUMPS_DIR, f"{subreddit_name}_dump_{today}.txt")
        try:
            with open(dump_filename, "w", encoding="utf-8") as f:
                f.write(combined_content)
            print(f"  [i] Raw data dump saved to {dump_filename}")
        except Exception as e:
            print(f"  [!] Could not save dump file: {e}")

    # 5. Define the prompt for the LLM analysis.
    prompt_for_analysis = f"""You are a world-class market research analyst and strategist. Your sole function is to identify and structure business opportunities based on direct evidence from community discussions.

**Core Principle:** Your analysis must be an objective reflection of the provided data. Do not inject opinions or biases about the scale or type of business that should pursue these opportunities.

Analyze the provided Reddit discussions from r/{subreddit_name} and generate a detailed 'Market Opportunity Report' with the following structure:

### Executive Summary
A concise, high-level overview of the dominant themes and most significant opportunities discussed. Highlight the 2-3 most pressing user needs identified in the data.

### 1. Top 5 User-Stated Pain Points
List the 5 most significant, recurring frustrations, challenges, and time-consuming manual tasks mentioned by users. For each point, include a representative (and anonymized) quote from the text.

### 2. Validated Product & Service Opportunities
Based on the pain points, identify 2-3 concrete product or service opportunities. For each, provide a blueprint in this exact format:
  - **The Problem:** A one-sentence summary of the core user problem this solves.
  - **The Opportunity:** A one-sentence description of the proposed product or service.
  - **Key Features / Deliverables:** List the 3-4 core features (for a product) or deliverables (for a service) that users would expect.
  - **Evidence from Data:** Briefly explain how this opportunity is supported by the recurring themes in the provided text.

### 3. Target Audience Profile
Describe the user persona most affected by the identified pain points. Detail their likely job roles, the tools they currently use, and their primary goals.

### 4. Potential Monetization Models
For each opportunity identified, list several potential business models without expressing a preference. Examples: 'Subscription (SaaS)', 'Fixed-Price Service', 'Pay-per-use API', 'One-time License'.

### 5. Voice of the Customer & Market Signals
This section captures direct evidence from the community. Extract the following signals:
  - **Keywords & Jargon:** List the specific keywords, phrases, and technical jargon the community uses to describe their problems. This is crucial for marketing and SEO.
  - **Existing Tools & Workarounds:** What tools, software, or manual processes (e.g., 'messy spreadsheets', 'custom Python scripts') are users currently employing to solve these problems? Mention them by name if possible.
  - **Quantified Demand Signals:** Identify any explicit signals of strong demand. Examples: 'Multiple users asking for the same feature,' 'threads with high engagement on a specific problem,' 'users offering to pay for a solution.'

**--- CRITICAL INSTRUCTIONS ---**
- **Maintain Objectivity:** Present the opportunities as they appear in the data.
- **Be Specific:** Replace vague terms with concrete outcomes.
- **Data-Driven:** Base all insights exclusively on the provided Reddit data.
- **Formatting:** Adhere strictly to the specified Markdown headings. If a section has no data, state 'No specific insights could be drawn from the provided data.' under the heading.

**--- RAW REDDIT DATA FROM R/{subreddit_name} ---**

{combined_content}"""
    
    # 6. Send to the LLM for analysis.
    print(f"  [*] Sending {len(combined_content)} chars from {len(new_links)} post(s) to LLM for r/{subreddit_name} analysis...")
    summary = await llm(prompt_for_analysis)
    print(f"  [✔] LLM analysis received for r/{subreddit_name}.")

    return {"name": subreddit_name, "summary": summary}, new_links


def create_markdown_report(subreddit_info):
    """Creates a markdown file from the analysis summary."""
    if not subreddit_info or not subreddit_info.get("summary"):
        print(f"  [*] No summary available for r/{subreddit_info.get('name', 'Unknown')}.")
        return

    today = datetime.now().strftime("%Y-%m-%d")
    filename = os.path.join(REPORTS_DIR, f"{subreddit_info['name']}_Market_Analysis_{today}.md")

    report_content = (
        f"# Market Analysis Digest: r/{subreddit_info['name']}\n"
        f"**Date:** {today}\n\n---\n\n"
        f"{subreddit_info['summary']}\n\n---\n\n"
        "*This report was auto-generated by analyzing recent posts to identify market opportunities.*"
    )

    with open(filename, "w", encoding="utf-8") as f:
        f.write(report_content)

    print(f"  [✔] Market analysis report saved to {filename}")


# --- MAIN ASYNCHRONOUS EXECUTION ---
async def main():
    """Main function to orchestrate the fetching and analysis process."""
    print("Starting Reddit Market Analysis Script...")

    seen_links = load_seen_links()
    tasks = [process_subreddit(sub, seen_links) for sub in SUBREDDITS]

    # Run all subreddit processing tasks concurrently.
    results = await asyncio.gather(*tasks)

    print("\n--- All LLM analyses complete. Processing results. ---")

    all_processed_links = set(seen_links)
    for summary_data, new_links in results:
        if summary_data:
            create_markdown_report(summary_data)
            # Log status based on whether the summary contains an error message.
            if "Error:" in summary_data.get("summary", ""):
                print(f"  [Task Complete] r/{summary_data['name']} processed with warnings/errors.")
            else:
                print(f"  [Task Complete] r/{summary_data['name']} processed successfully.")

        if new_links:
            all_processed_links.update(new_links)

    save_seen_links(all_processed_links)

    print("\nScript finished successfully!")


if __name__ == "__main__":
    asyncio.run(main())