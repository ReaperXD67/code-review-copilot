from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from pydantic import BaseModel
from app.services.github import get_pr_diff, post_pr_review
from app.services.reviewer import analyze_pr_diff
from app.services.chroma import learn_convention, retrieve_relevant_rules
from app.services.history import extract_rules_from_history_task
import hmac
import hashlib
import os

app = FastAPI(title="Code Review Copilot")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")

# --- DATA MODELS ---
class ManualReviewRequest(BaseModel):
    repo_name: str
    pr_number: int

class ConventionRequest(BaseModel):
    rule: str

# --- ENDPOINTS ---
@app.post("/conventions/learn")
async def add_house_rule(request: ConventionRequest):
    """Endpoint to teach the Copilot a new house rule."""
    learn_convention(request.rule)
    return {"status": "success", "message": f"Learned new rule: {request.rule}"}

@app.post("/review/manual")
async def manual_review(request: ManualReviewRequest):
    """Manual endpoint for testing PRs."""
    diff = get_pr_diff(request.repo_name, request.pr_number)
    
    # Query ChromaDB for rules related to this specific code diff
    house_rules = retrieve_relevant_rules(diff, request.repo_name)
    
    # Pass the targeted rules into the Gemini reasoning engine
    review_result = analyze_pr_diff(diff, house_rules=house_rules)
    post_pr_review(request.repo_name, request.pr_number, review_result)
    
    return {"status": "success", "applied_rules": house_rules, "summary": review_result.risk_summary}

@app.post("/webhook/github")
async def github_webhook(request: Request, background_tasks: BackgroundTasks):
    """Receives GitHub webhooks and coordinates the AI review."""
    
    payload = await request.json()
    action = payload.get("action")
    
    repo_name = payload.get("repository", {}).get("full_name")
    
    if not repo_name:
        raise HTTPException(status_code=400, detail="Repository full_name missing from payload")

    # Only process newly opened or synchronized (updated) PRs
    if action not in ["opened", "synchronize"]:
        return {"status": "ignored", "reason": f"Action '{action}' is not reviewable"}

    pr_number = payload.get("pull_request", {}).get("number")
    
    # 2. FIRE AND FORGET: Trigger the history scraper in the background.
    # If the repo is already processed, the task will instantly exit.
    # This does NOT block the rest of this function from running!
    background_tasks.add_task(extract_rules_from_history_task, repo_name)

    # 3. Proceed with the immediate PR review
    diff = get_pr_diff(repo_name, pr_number)
    
    # Pass the isolated repo_name to Chroma to ensure we only get this repo's rules
    house_rules = retrieve_relevant_rules(diff, repo_name)
    
    # Generate the review JSON
    review_result = analyze_pr_diff(diff, house_rules=house_rules)
    
    # Post the comments back to GitHub
    post_pr_review(repo_name, pr_number, review_result)
    
    return {"status": "review_triggered_and_history_checked"}