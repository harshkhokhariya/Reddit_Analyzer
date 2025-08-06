# reddit_analyzer.py (Corrected Version)

import os
import praw
from datetime import datetime
from dotenv import load_dotenv
from litellm import completion

# --- CONFIGURATION ---
SUBREDDITS = ["n8n"] 
POST_LIMIT = 5
MODEL = "gemini/gemini-2.5-flash" 
SAVE_REDDIT_DUMPS = True


# Load environment variables from .env file
load_dotenv()



# --- API INITIALIZATION ---
reddit = praw.Reddit(
    client_id=os.getenv("REDDIT_CLIENT_ID"),
    client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
    user_agent=os.getenv("REDDIT_USER_AGENT")
)

# --- FILE PATHS ---
SEEN_LINKS_FILE = "seen_links.txt"
REPORTS_DIR = "reports"
DUMPS_DIR = "reddit_dumps"



os.makedirs(REPORTS_DIR, exist_ok=True)
if SAVE_REDDIT_DUMPS:
    os.makedirs(DUMPS_DIR, exist_ok=True)


# ==============================================================================
# === LLM FUNCTION (ROBUST) ===
# ==============================================================================
def llm(prompt_text: str) -> str:
    """
    Sends a prompt to the LLM and handles potential errors, including empty responses.
    """
    try:
        response = completion(
            model=MODEL,
            messages=[{"role": "user", "content": prompt_text}],
            temperature=0.7
        )
        
        # Check if the response or its content is empty (silent failure)
        if not response.choices or not response.choices[0].message.content:
            print("  [!] LLM returned a successful but EMPTY response. This can be due to safety filters.")
            return "Error: The LLM API returned an empty response, possibly due to content safety filters on the input data."
            
        return response.choices[0].message.content

    except Exception as e:
        print(f"  [!] LLM API Error: {e}")
        return f"Error: The LLM API call failed with an exception. Details: {e}"

# --- HELPER FUNCTIONS ---

def load_seen_links():
    if not os.path.exists(SEEN_LINKS_FILE):
        return set()
    with open(SEEN_LINKS_FILE, 'r') as f:
        return set(line.strip() for line in f)

def save_seen_links(links):
    with open(SEEN_LINKS_FILE, 'w') as f:
        for link in links:
            f.write(link + '\n')

def process_subreddit(subreddit_name, seen_links):
    """
    Fetches, filters, concatenates content from multiple posts, sends to LLM,
    and prepares data for a single subreddit report.
    """
    print(f"\n--- Processing r/{subreddit_name} ---")
    subreddit = reddit.subreddit(subreddit_name)
    
    all_new_content_for_llm = [] 
    current_subreddit_new_links = [] 

    try:
        # Step 1: Collect content from all new posts
        for post in subreddit.hot(limit=POST_LIMIT):
            if post.stickied or post.url in seen_links:
                continue

            print(f"  [+] Collecting content from: {post.title[:50]}...")
            
            post_content = f"### Post Title: {post.title}\nLink: {post.url}\n\n**Post Body:**\n{post.selftext}\n\n"
            
            post.comments.replace_more(limit=None)
            
            comment_buffer = []
            for comment in post.comments.list():
                if hasattr(comment, 'body') and comment.body not in ('[deleted]', '[removed]'):
                    comment_buffer.append(f"- {comment.body}\n")
            
            if comment_buffer:
                post_content += f"**Comments ({len(comment_buffer)}):**\n" + "".join(comment_buffer)
            else:
                post_content += "**No comments.**"
            
            post_content += "\n\n---\n\n"
            
            all_new_content_for_llm.append(post_content)
            current_subreddit_new_links.append(post.url)

    except Exception as e:
        print(f"  [!] Reddit API Error for r/{subreddit_name}: {e}")
        return None, []

    if not all_new_content_for_llm:
        print(f"  [*] No new posts found to analyze for r/{subreddit_name}.")
        return None, []

    # Step 2: Combine all content and prepare the prompt
    combined_content = "".join(all_new_content_for_llm)
    
    full_prompt_for_subreddit = (f"""
        You are an expert market research analyst specializing in identifying nascent business opportunities and product ideas from unstructured text data. Your task is to thoroughly analyze the provided Reddit discussions from r/{subreddit_name} and generate a detailed, actionable report for a startup founder.

**Your analysis must focus on extracting the following key insights:**

### Executive Summary
A concise overview of the most significant opportunities and findings from this subreddit's analysis. Highlight 1-2 key takeaways that a founder should immediately grasp.

### 1. Key Pain Points & Problems
Identify and describe the core frustrations, challenges, and unmet needs expressed by users.
- Group similar pain points together.
- Provide specific examples or direct quotes where illustrative.
- Categorize pain points by frequency or severity if discernible.

### 2. Unmet Needs & Feature Requests
Detail explicit and implicit requests for features, tools, or solutions that users are asking for or hinting at.
- Distinguish between fully formed requests and subtle indications of missing functionalities.
- Note any recurring themes or highly desired functionalities.

### 3. Concrete Product & SaaS Ideas
Based on the identified pain points and unmet needs, propose specific, actionable product or SaaS ideas.
- For each idea, clearly state the problem it solves.
- Describe the core functionality and potential unique selling propositions.
- Consider both standalone products and potential features for existing platforms.
- Prioritize ideas based on perceived demand or impact.

### 4. Target Audience Insights
Describe the characteristics, demographics (if inferable), motivations, and behaviors of the users experiencing these pain points.
- What are their goals? What are they trying to achieve?
- What kind of language do they use?
- Are there distinct user segments?

### 5. Monetization Potential
Suggest viable business models or monetization strategies for the proposed product ideas.
- Consider subscription models, one-time purchases, freemium, advertising, service integration, etc.
- Justify why a particular model would be suitable for the identified target audience and product.

### 6. Recurring Themes & Positive Sentiments
Identify any recurring topics, common interests, or positive feedback related to existing solutions or concepts.
- What are users consistently discussing?
- What aspects do they appreciate or find effective (even in flawed solutions)?
- Are there any surprising or emerging trends?

### 7. Competitive Landscape (Implicit)
Infer the current solutions users are employing (or struggling with).
- What workarounds are they using?
- What existing tools are they mentioning, and what are their limitations?
- This section should be based on user discussions, not external knowledge.

**--- IMPORTANT INSTRUCTIONS ---**
- **Data-Driven:** Base all insights exclusively on the provided Reddit data. Do not introduce external knowledge.
- **Actionable & Specific:** Provide concrete examples, detailed descriptions, and actionable recommendations. Avoid vague statements.
- **Ignore Noise:** Disregard spam, jokes, personal attacks, off-topic discussions, and non-substantive comments. Focus solely on content relevant to market research.
- **Tone & Style:** Maintain a professional, analytical, and objective tone. Use clear and concise language.
- **Formatting:** Adhere strictly to the specified Markdown headings. Do not add or remove sections.
- **Thoroughness:** Analyze every relevant piece of information within the provided `RAW_REDDIT_DATA`. If a section is not applicable (e.g., no clear positive sentiments), state "N/A - No discernible recurring positive sentiments." rather than omitting the heading.

**--- RAW REDDIT DATA FROM R/{subreddit_name} ---**

{combined_content}
    """)
    
    if SAVE_REDDIT_DUMPS:
        today = datetime.now().strftime("%Y-%m-%d")
        # FIX: Changed filename for consistency
        dump_filename = os.path.join(DUMPS_DIR, f"{subreddit_name}_dumps_{today}.txt")
        try:
            with open(dump_filename, 'w', encoding='utf-8') as f:
                f.write(combined_content)
            print(f"  [i] Raw data dump saved to {dump_filename}")
        except Exception as e:
            print(f"  [!] Could not save dump file: {e}")

    # Step 3: Send the single, large prompt to the LLM
    print(f"  [*] Sending {len(combined_content)} chars from {len(current_subreddit_new_links)} post(s) to LLM for analysis...")
    subreddit_summary = llm(full_prompt_for_subreddit)

    return {"name": subreddit_name, "summary": subreddit_summary}, current_subreddit_new_links

def create_markdown_report(subreddit_info):
    """
    Creates a date-stamped markdown file with the summary for a subreddit.
    """
    if not subreddit_info or not subreddit_info.get('summary'):
        print(f"  [*] No summary available for r/{subreddit_info.get('name', 'Unknown')}.")
        return

    today = datetime.now().strftime("%Y-%m-%d")
    filename = os.path.join(REPORTS_DIR, f"{subreddit_info['name']}_Market_Analysis_{today}.md")

    with open(filename, 'w', encoding='utf-8') as f:
        f.write(f"# Market Analysis Digest: r/{subreddit_info['name']}\n")
        f.write(f"**Date:** {today}\n\n---\n\n")
        f.write(subreddit_info['summary'])
        f.write("\n\n---\n\n*This report was auto-generated by analyzing recent posts to identify market opportunities.*")
            
    print(f"  [✔] Market analysis report saved to {filename}")

# --- MAIN EXECUTION (WITH ROBUST LOGIC) ---
if __name__ == "__main__":
    print("Starting Reddit Market Analysis Script...")
    
    seen_links = load_seen_links()
    all_processed_links = list(seen_links)

    for sub in SUBREDDITS:
        summary_data, new_links = process_subreddit(sub, seen_links)
        
        # Always create a report, even if it's just an error report.
        if summary_data:
            create_markdown_report(summary_data)
            
        # FIX: Always save the links that were processed, even if the LLM call failed.
        # This prevents the script from getting stuck on the same posts on the next run.
        if new_links:
            all_processed_links.extend(new_links)
            
    save_seen_links(set(all_processed_links))
    
    print("\nScript finished successfully!")