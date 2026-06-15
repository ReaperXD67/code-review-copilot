import os
import json
import logging
from github import Github
import google.generativeai as genai
from app.services.chroma import learn_convention

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Store the tracking file in the root of the Docker container
TRACKING_FILE = "processed_repos.json"

def has_been_processed(repo_name: str) -> bool:
    """Checks if the Owner/Repo_Name has already had its history analyzed."""
    if not os.path.exists(TRACKING_FILE):
        return False
    with open(TRACKING_FILE, "r") as f:
        return repo_name in json.load(f)

def mark_as_processed(repo_name: str):
    """Flags the Owner/Repo_Name as complete to ensure idempotency."""
    processed = []
    if os.path.exists(TRACKING_FILE):
        with open(TRACKING_FILE, "r") as f:
            processed = json.load(f)
            
    if repo_name not in processed:
        processed.append(repo_name)
        with open(TRACKING_FILE, "w") as f:
            json.dump(processed, f)

def extract_rules_from_history_task(repo_name: str):
    """
    BACKGROUND TASK: Scrapes merged PRs, extracts rules, and saves them.
    This runs asynchronously and will not block the main FastAPI thread.
    """
    if has_been_processed(repo_name):
        return  # Silently exit if we already learned this repo's history

    logging.info(f"🧠 Background Task Started: Analyzing history for {repo_name}...")
    
    gh = Github(GITHUB_TOKEN)
    genai.configure(api_key=GEMINI_API_KEY)
    llm = genai.GenerativeModel('gemini-2.5-flash')

    try:
        # repo_name is guaranteed to be "Owner/Repo_Name"
        repo = gh.get_repo(repo_name)
        pulls = repo.get_pulls(state='closed', sort='updated', direction='desc')
        
        raw_comments = []
        for pr in pulls[:10]: # Look at the 10 most recent PRs
            if pr.merged:
                for comment in pr.get_review_comments():
                    raw_comments.append(comment.body)
                    
        if not raw_comments:
            logging.info(f"No historical review comments found for {repo_name}.")
            mark_as_processed(repo_name)
            return

        # Use Gemini to extract rules
        prompt = f"""
        Analyze these code review comments from our team. 
        Extract the 3 most important, generalized coding conventions or "house rules" being enforced.
        Format strictly as a bulleted list of actionable rules without markdown blocks.
        
        Comments:
        {raw_comments}
        """
        
        response = llm.generate_content(prompt)
        rules = [r.replace("*", "").replace("-", "").strip() for r in response.text.strip().split('\n') if r.strip()]
        
        # Save to Pinecone / ChromaDB
        for rule in rules:
            if rule:
                learn_convention(rule, repo_name)
                
        mark_as_processed(repo_name)
        logging.info(f"✅ Background Task Complete: Saved {len(rules)} rules for {repo_name}.")

    except Exception as e:
        logging.error(f"❌ Failed to extract history for {repo_name}: {e}")