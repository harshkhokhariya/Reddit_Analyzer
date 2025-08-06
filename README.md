# Reddit Analyzer

The Reddit Analyzer is a Python script designed to automatically identify business opportunities, pain points, and product ideas by analyzing discussions in specified subreddits. It leverages the Reddit API to fetch posts and comments, and a Large Language Model (LLM) (via LiteLLM) to synthesize these conversations into structured market research reports.

This tool is ideal for startup founders, product managers, or anyone looking to uncover unmet needs and emerging trends directly from community discussions.

## Features

*   **Automated Data Collection:** Fetches top posts and their comments from specified subreddits.
*   **Duplicate Prevention:** Uses a `seen_links.txt` file to avoid re-processing the same posts on subsequent runs.
*   **LLM-Powered Analysis:** Sends collected Reddit content to an LLM (defaulting to Gemini via LiteLLM) to generate detailed market analysis reports.
*   **Structured Reports:** Generates Markdown reports with predefined sections: Executive Summary, Pain Points, Unmet Needs, Product Ideas, Target Audience Insights, Monetization Potential, Recurring Themes, and Implicit Competitive Landscape.
*   **Raw Data Dumps (Optional):** Option to save the raw text sent to the LLM for review and debugging.
*   **Robust LLM Handling:** Includes error handling for LLM API calls, including cases of empty responses (e.g., due to safety filters).
*   **Configurable:** Easily adjust target subreddits, post limits, and LLM model.

## How It Works

1.  **Configuration:** You define which subreddits to analyze and how many posts to fetch.
2.  **Reddit Data Collection:** The script connects to the Reddit API, identifies new "hot" posts within the specified subreddits, and collects their titles, body text, and comments.
3.  **Data Preprocessing:** All collected text data for a subreddit is concatenated into a single, comprehensive string.
4.  **LLM Prompting:** This combined text, along with a carefully crafted prompt, is sent to the configured LLM. The prompt instructs the LLM to act as a market research analyst and extract specific insights.
5.  **Report Generation:** The LLM's response is then saved as a Markdown file in the `reports/` directory, providing a structured summary of market opportunities.
6.  **Link Tracking:** Processed post URLs are saved to `seen_links.txt` to prevent redundant analysis in future runs.

## Setup and Installation

### 1. Clone the Repository

```bash
git clone https://github.com/harshkhokhariya/Reddit_Analyzer.git
cd reddit-market-opportunity-analyzer # Or whatever your project folder is named
```

### 2. Create a Virtual Environment (Recommended)

```bash
python -m venv venv
# On Windows
.\venv\Scripts\activate
# On macOS/Linux
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure API Credentials

You need API credentials for both Reddit and the LLM you choose (e.g., Google Gemini).

#### Reddit API Credentials

1.  Go to [Reddit App Preferences](https://www.reddit.com/prefs/apps).
2.  Scroll to the bottom and click "are you a developer? create an app...".
3.  Fill in the details:
    *   **Name:** Give it a meaningful name (e.g., "RedditAnalyzer").
    *   **Type:** Select "script".
    *   **Description:** (Optional) A brief description.
    *   **About URL:** (Optional) Your website or GitHub repo.
    *   **Redirect URI:** Enter `http://localhost:8080` (or any valid URL, it's not strictly used for script apps but is required).
4.  Click "create app".
5.  After creation, you'll see your app details. Your **`client_id`** is the string under "personal use script" (e.g., `8ZfrjBWosSB6go_HrCJBlw`). Your **`client_secret`** is the string next to "secret" (e.g., `VQ8-CtVKF6hEguCLghRx_R1BDN9hMw`).

#### LLM API Key (e.g., Google Gemini)

1.  Go to [Google AI Studio](https://aistudio.google.com/app/apikey) to generate a Gemini API key.
2.  Make sure you enable the Gemini API for your project.

### 5. Create `.env` File

Create a file named `.env` in the root directory of your project (the same directory as `main.py`). Copy the content from `.env.example` into it and replace the placeholder values with your actual API keys and Reddit user agent.

```dotenv
# .env file

# Reddit API Credentials (App-Only)
REDDIT_CLIENT_ID="YOUR_REDDIT_CLIENT_ID"
REDDIT_CLIENT_SECRET="YOUR_REDDIT_CLIENT_SECRET"
REDDIT_USER_AGENT="REDDIT ANALYZER Script by u/your_reddit_username" # IMPORTANT: Change your_reddit_username

# LLM API Key (e.g., Gemini, OpenAI, etc.)
GEMINI_API_KEY="YOUR_GEMINI_API_KEY" # Or OPENAI_API_KEY for OpenAI, etc.
```

**Important:** Replace `YOUR_REDDIT_CLIENT_ID`, `YOUR_REDDIT_CLIENT_SECRET`, `YOUR_GEMINI_API_KEY`, and `your_reddit_username` with your actual values. The `user_agent` is crucial for Reddit to identify your script and avoid rate limiting.

## Configuration

You can adjust the script's behavior by modifying the `main.py` file:

*   **`SUBREDDITS`**: A list of subreddit names you want to analyze (e.g., `["n8n", "AI_Agents"]`).
    ```python
    SUBREDDITS = ["SideProject","Python","AI_Agents"]
    ```
*   **`POST_LIMIT`**: The number of "hot" posts to fetch from each subreddit. Be mindful that fetching more posts increases processing time and LLM token usage.
    ```python
    POST_LIMIT = 15
    ```
*   **`MODEL`**: The LiteLLM model string to use for analysis. Default is `gemini/gemini-2.5-flash`. You can change this to other models supported by LiteLLM (e.g., `"gpt-4o"`, `"ollama/llama3"`, etc.), provided you have the corresponding API keys or local setup.
    ```python
    MODEL = "gemini/gemini-2.5-flash"
    ```
*   **`SAVE_REDDIT_DUMPS`**: Set to `True` to save the raw text sent to the LLM in the `reddit_dumps` folder. Set to `False` to only generate the final reports.
* (this is optional, but can be used to deep dive into reddit posts)
    ```python
    SAVE_REDDIT_DUMPS = True
    ```

## Running the Script

Once configured, run the script from your terminal:

```bash
python main.py
```

The script will:
1.  Print its progress to the console.
2.  Save raw data dumps (if `SAVE_REDDIT_DUMPS` is `True`) in the `reddit_dumps/` directory.
3.  Generate Markdown reports in the `reports/` directory.

## Output

*   **`reports/`**: This directory will contain Markdown files (e.g., `n8n_Market_Analysis_2024-07-30.md`) for each subreddit analyzed, containing the LLM-generated market research report.
*   **`reddit_dumps/`**: (If enabled) This directory will contain plain text files (e.g., `n8n_dumps_2024-07-30.txt`) with the raw Reddit content that was fed into the LLM.
*   **`seen_links.txt`**: A file that keeps track of all Reddit post URLs that have already been processed to avoid duplication across runs.

## Troubleshooting

*   **`praw.exceptions.ClientException: invalid_grant error`**: This usually means your `REDDIT_CLIENT_ID` or `REDDIT_CLIENT_SECRET` is incorrect or your Reddit app setup is wrong. Double-check them on your Reddit App Preferences page.
*   **`[!] LLM API Error: ...`**:
    *   Check your `GEMINI_API_KEY` (or other LLM API key) in the `.env` file.
    *   Ensure your internet connection is stable.
    *   Verify that the `MODEL` specified in `main.py` is correct and supported by LiteLLM and your API key.
    *   **`LLM returned a successful but EMPTY response. This can be due to safety filters.`**: This means the LLM processed the request but returned no content, often because the input data (Reddit posts/comments) triggered content safety policies. Try reducing `POST_LIMIT` or analyzing different subreddits.
*   **`No new posts found to analyze`**: This means all recent posts (up to `POST_LIMIT`) have already been processed in previous runs and their links are in `seen_links.txt`. Delete `seen_links.txt` to force a re-analysis of all posts, or wait for new content on Reddit.
*   **Rate Limiting**: If you encounter errors related to too many requests, reduce `POST_LIMIT` or increase the `time.sleep()` duration (not currently implemented, but a common solution for API rate limits) between API calls in a more complex setup.

## Contributing

Feel free to open issues or submit pull requests if you have suggestions for improvements or bug fixes.

## License

This project is open-source and licensed under the [MIT License](LICENSE.txt).

---