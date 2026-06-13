import json
from langchain_community.llms import Ollama
from langchain.prompts import PromptTemplate
from app.models import PRReviewResult
import os

OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")

# We use Qwen or Llama3 via Ollama
llm = Ollama(model="qwen2.5-coder:3b", base_url=OLLAMA_URL, format="json")

REVIEW_PROMPT = """
You are an expert Senior Software Engineer and a patient mentor. 
Review the following code diff for a Pull Request.

Context (House Rules):
{house_rules}

Diff to review:
{diff}

Your task is to identify bugs, security flaws, performance issues, and stylistic problems.
Provide your response strictly as a JSON object matching this schema:
{schema}

Ensure line numbers strictly correspond to the added/modified lines in the diff.
"""

def analyze_pr_diff(diff: str, house_rules: str = "None") -> PRReviewResult:
    schema = PRReviewResult.schema_json()
    prompt = PromptTemplate(
        template=REVIEW_PROMPT,
        input_variables=["house_rules", "diff", "schema"]
    )
    
    chain = prompt | llm
    
    # Run the LLM
    raw_response = chain.invoke({
        "house_rules": house_rules,
        "diff": diff,
        "schema": schema
    })
    
    # Parse the local LLM JSON output into our Pydantic model
    parsed_json = json.loads(raw_response)
    return PRReviewResult(**parsed_json)