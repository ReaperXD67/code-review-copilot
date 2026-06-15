from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel
from app.services.github import get_pr_diff, post_pr_review
from app.services.reviewer import analyze_pr_diff
from app.services.chroma import learn_convention, retrieve_relevant_rules
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
    house_rules = retrieve_relevant_rules(diff)
    
    # Pass the targeted rules into the Gemini reasoning engine
    review_result = analyze_pr_diff(diff, house_rules=house_rules)
    post_pr_review(request.repo_name, request.pr_number, review_result)
    
    return {"status": "success", "applied_rules": house_rules, "summary": review_result.risk_summary}

@app.post("/webhook/github")
async def github_webhook(request: Request, x_hub_signature_256: str = Header(None)):
    """Webhook endpoint for automated GitHub PRs."""
    payload = await request.body()
    
    if WEBHOOK_SECRET:
        signature = "sha256=" + hmac.new(WEBHOOK_SECRET.encode(), payload, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, x_hub_signature_256):
            raise HTTPException(status_code=403, detail="Invalid signature")

    data = await request.json()
    
    if "pull_request" in data and data.get("action") in ["opened", "synchronize"]:
        repo_name = data["repository"]["full_name"]
        pr_number = data["pull_request"]["number"]
        
        diff = get_pr_diff(repo_name, pr_number)
        
        # Dynamic Convention Injector
        house_rules = retrieve_relevant_rules(diff)
        
        review_result = analyze_pr_diff(diff, house_rules=house_rules)
        post_pr_review(repo_name, pr_number, review_result)
        
        return {"status": "review_triggered"}
    
    return {"status": "ignored"}