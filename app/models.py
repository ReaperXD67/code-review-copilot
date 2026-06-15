from pydantic import BaseModel, Field
from typing import List

class ReviewComment(BaseModel):
    file_path: str = Field(description="The path of the file being reviewed")
    line_number: int = Field(description="The exact line number for the comment based on the new file")
    severity: str = Field(description="One of: bug, security, performance, style, suggestion")
    summary: str = Field(description="Short, one sentence summary of the issue")
    explanation: str = Field(description="Plain-English explanation for a junior developer on WHY this matters.")
    suggested_fix: str = Field(description="Concrete code snippet to fix the issue")

class PRReviewResult(BaseModel):
    risk_score: int = Field(description="1 to 10 score indicating overall risk of the PR")
    risk_summary: str = Field(description="Top-level summary of the highest risk changes")
    merge_decision: str = Field(description="One of: APPROVE, REQUEST_CHANGES, COMMENT")
    comments: List[ReviewComment] = Field(default_factory=list, description="List of inline comments to post")