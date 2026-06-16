from fastapi import FastAPI, HTTPException, Request, BackgroundTasks, Header
from pydantic import BaseModel, Field
from app.services.github import get_pr_diff, post_pr_review
from app.services.reviewer import analyze_pr_diff
from app.services.chroma import learn_convention, retrieve_relevant_rules
from app.services.history import extract_rules_from_history_task
import hmac
import hashlib
import os
import json
from json import JSONDecodeError

app = FastAPI(title="Code Review Copilot")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")

def verify_github_signature(payload_body: bytes, signature_header: str) -> bool:
    """Verifies the HMAC SHA256 signature from GitHub."""
    if not signature_header or not WEBHOOK_SECRET:
        return False
        
    # Hash the raw payload using your secret
    hash_object = hmac.new(
        WEBHOOK_SECRET.encode('utf-8'), 
        msg=payload_body, 
        digestmod=hashlib.sha256
    )
    expected_signature = "sha256=" + hash_object.hexdigest()
    
    # Use hmac.compare_digest to prevent timing attacks
    return hmac.compare_digest(expected_signature, signature_header)

# --- DATA MODELS ---
class ManualReviewRequest(BaseModel):
    repo_name: str = Field(min_length=1, examples=["Owner/Repository"])
    pr_number: int = Field(gt=0)

class ConventionRequest(BaseModel):
    repo_name: str = Field(min_length=1, examples=["Owner/Repository"])
    rule: str = Field(min_length=1)

# --- ENDPOINTS ---
@app.post("/conventions/learn")
async def add_house_rule(request: ConventionRequest):
    """Endpoint to teach the Copilot a new house rule."""
    learn_convention(request.rule, request.repo_name)
    return {
        "status": "success",
        "repo_name": request.repo_name,
        "message": f"Learned new rule: {request.rule}",
    }

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
async def github_webhook(request: Request, background_tasks: BackgroundTasks, x_hub_signature_256: str = Header(None)):
    """Receives GitHub webhooks and coordinates the AI review."""
    
    payload_body = await request.body()

    if not verify_github_signature(payload_body, x_hub_signature_256):
        raise HTTPException(status_code=401, detail="Invalid signature. Unauthorized webhook.")

    try:
        payload = json.loads(payload_body)
    except JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    action = payload.get("action")
    
    repo_name = payload.get("repository", {}).get("full_name")
    
    if not repo_name:
        raise HTTPException(status_code=400, detail="Repository full_name missing from payload")

    # Only process newly opened or synchronized (updated) PRs
    if action not in ["opened", "synchronize"]:
        return {"status": "ignored", "reason": f"Action '{action}' is not reviewable"}

    pr_number = payload.get("pull_request", {}).get("number")
    if not isinstance(pr_number, int):
        raise HTTPException(status_code=400, detail="Pull request number missing from payload")
    
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
