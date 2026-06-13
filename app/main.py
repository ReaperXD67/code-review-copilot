from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel
from app.services.github import get_pr_diff, post_pr_review
from app.services.reviewer import analyze_pr_diff
import hmac
import hashlib
import os

app = FastAPI(title="Code Review Copilot")

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")

class ManualReviewRequest(BaseModel):
    repo_name: str # e.g., "octocat/Hello-World"
    pr_number: int

@app.post("/review/manual")
async def manual_review(request: ManualReviewRequest):
    """Manual endpoint for testing before webhooks are wired up."""
    diff = get_pr_diff(request.repo_name, request.pr_number)
    
    # Optional: fetch from ChromaDB here
    house_rules = "Prefer list comprehensions over loops." 
    
    review_result = analyze_pr_diff(diff, house_rules)
    post_pr_review(request.repo_name, request.pr_number, review_result)
    
    return {"status": "success", "summary": review_result.risk_summary}

@app.post("/webhook/github")
async def github_webhook(request: Request, x_hub_signature_256: str = Header(None)):
    """Webhook endpoint for GitHub."""
    payload = await request.body()
    
    # Verify Webhook Signature for security
    if WEBHOOK_SECRET:
        signature = "sha256=" + hmac.new(WEBHOOK_SECRET.encode(), payload, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, x_hub_signature_256):
            raise HTTPException(status_code=403, detail="Invalid signature")

    data = await request.json()
    
    # Only act on PR open or synchronize (push to PR) events
    if "pull_request" in data and data.get("action") in ["opened", "synchronize"]:
        repo_name = data["repository"]["full_name"]
        pr_number = data["pull_request"]["number"]
        
        diff = get_pr_diff(repo_name, pr_number)
        review_result = analyze_pr_diff(diff)
        post_pr_review(repo_name, pr_number, review_result)
        
        return {"status": "review_triggered"}
    
    return {"status": "ignored"}