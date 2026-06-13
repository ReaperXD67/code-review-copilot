from github import Github
import os
from app.models import PRReviewResult

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
gh = Github(GITHUB_TOKEN)

def get_pr_diff(repo_name: str, pr_number: int) -> str:
    repo = gh.get_repo(repo_name)
    pr = repo.get_pull(pr_number)
    # Get the raw diff string
    # In a production app, you'd iterate through files to track exact line map positions
    diff_url = pr.diff_url
    import requests
    response = requests.get(diff_url)
    return response.text

def post_pr_review(repo_name: str, pr_number: int, review_data: PRReviewResult):
    repo = gh.get_repo(repo_name)
    pr = repo.get_pull(pr_number)
    
    # Post the overall summary
    summary_body = f"### AI Review Summary\n**Risk Score:** {review_data.risk_score}/10\n**Decision:** {review_data.merge_decision}\n\n**Analysis:** {review_data.risk_summary}"
    pr.create_issue_comment(summary_body)
    
    # Post inline comments (Note: GitHub requires the commit ID to post inline)
    commit_id = pr.get_commits().reversed[0].sha 
    
    for comment in review_data.comments:
        body = f"**[{comment.severity.upper()}]** {comment.summary}\n\n**Why it matters:** {comment.explanation}\n\n**Suggested Fix:**\n```python\n{comment.suggested_fix}\n```"
        try:
            pr.create_review_comment(
                body=body,
                commit_id=commit_id,
                path=comment.file_path,
                line=comment.line_number
            )
        except Exception as e:
            # Fallback if line mapping fails: post as a general PR comment
            pr.create_issue_comment(f"*(Fallback for {comment.file_path}:{comment.line_number})*\n" + body)