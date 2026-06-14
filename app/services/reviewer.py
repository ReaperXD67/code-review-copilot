import os
import json
import re
from langchain_community.llms import Ollama
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from app.models import PRReviewResult

OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")

llm = Ollama(model="qwen2.5-coder:3b", base_url=OLLAMA_URL, format="json")

REVIEW_PROMPT = """
You are an expert Senior Software Engineer and a patient mentor. 
Review the following code diff for a Pull Request.

Context (House Rules):
{house_rules}

Diff to review:
{diff}

INSTRUCTIONS FOR LINE NUMBERS:
The diff has been pre-processed. Added and context lines start with a bracketed number, e.g., [15].
Extract the integer inside the brackets for the `line_number` field. Do not guess or invent line numbers.

CRITICAL OUTPUT INSTRUCTIONS:
You MUST respond with ONLY valid JSON. Output the ACTUAL review data following this EXACT structure:

{{
  "risk_score": 5,
  "risk_summary": "A short summary of the highest risk changes.",
  "merge_decision": "COMMENT",
  "comments": [
    {{
      "file_path": "path/to/file.py",
      "line_number": 15,
      "severity": "bug",
      "summary": "Short issue summary",
      "explanation": "Why this matters...",
      "suggested_fix": "code fix"
    }}
  ]
}}
"""

def extract_json(raw_text: str) -> dict:
    match = re.search(r'(\{.*\}|\[.*\])', raw_text, re.DOTALL)
    if match:
        raw_text = match.group(1)
        
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        print(f"Failed to parse JSON. Raw output: {raw_text}")
        return {}

def analyze_pr_diff(diff: str, house_rules: str = "None") -> PRReviewResult:
    prompt = PromptTemplate(
        template=REVIEW_PROMPT,
        input_variables=["house_rules", "diff"]
    )
    
    chain = prompt | llm | StrOutputParser()
    
    raw_response = chain.invoke({
        "house_rules": house_rules,
        "diff": diff
    })
    
    parsed_data = extract_json(raw_response)
    
    risk_score = parsed_data.get("risk_score", 5)
    risk_summary = parsed_data.get("risk_summary", "Auto-generated summary. The LLM omitted the risk analysis.")
    merge_decision = parsed_data.get("merge_decision", "COMMENT")
    comments = parsed_data.get("comments", [])
    
    if isinstance(parsed_data, list):
        comments = parsed_data
    elif isinstance(parsed_data, dict) and "file_path" in parsed_data and "comments" not in parsed_data:
        comments = [parsed_data]

    return PRReviewResult(
        risk_score=risk_score,
        risk_summary=risk_summary,
        merge_decision=merge_decision,
        comments=comments
    )