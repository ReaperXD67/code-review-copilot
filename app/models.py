from pydantic import BaseModel, Field, field_validator
from typing import List, Any

class ReviewComment(BaseModel):
    file_path: str = Field(description="The path of the file being reviewed")
    line_number: int = Field(description="The exact line number for the comment based on the new file")
    severity: str = Field(description="One of: bug, security, performance, style, suggestion")
    summary: str = Field(description="Short, one sentence summary of the issue")
    explanation: str = Field(description="Plain-English explanation for a junior developer on WHY this matters.")
    suggested_fix: str = Field(description="Concrete code snippet to fix the issue")

    @field_validator('line_number', mode='before')
    @classmethod
    def clean_line_number(cls, v: Any) -> int:
        """Strips brackets if the LLM accidentally outputs a list or string like [10] or '[10]'."""
        # If the LLM output a JSON array: [10]
        if isinstance(v, list) and len(v) > 0:
            v = v[0]
        # If the LLM output a string with brackets: "[10]"
        if isinstance(v, str):
            v = v.replace('[', '').replace(']', '').strip()
        # Cast to int
        try:
            return int(v)
        except (ValueError, TypeError):
            return 1 # Safe fallback to line 1 if it completely hallucinated
            
class PRReviewResult(BaseModel):
    risk_score: int = Field(description="1 to 10 score indicating overall risk of the PR")
    risk_summary: str = Field(description="Top-level summary of the highest risk changes")
    merge_decision: str = Field(description="One of: APPROVE, REQUEST_CHANGES, COMMENT")
    comments: List[ReviewComment] = Field(description="List of inline comments to post")