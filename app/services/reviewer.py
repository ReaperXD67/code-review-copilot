import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate
from app.models import PRReviewResult

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

llm = ChatGoogleGenerativeAI(
    model="gemini-1.5-flash",
    google_api_key=GEMINI_API_KEY,
    temperature=0.2 # Low temperature for highly analytical, deterministic code review
)

structured_llm = llm.with_structured_output(PRReviewResult)

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
"""

def analyze_pr_diff(diff: str, house_rules: str = "None") -> PRReviewResult:
    """Main entry point for analyzing the diff. Imported by main.py."""
    
    prompt = PromptTemplate(
        template=REVIEW_PROMPT,
        input_variables=["house_rules", "diff"]
    )
    
    # Pipe the prompt directly into our structured LLM
    chain = prompt | structured_llm
    
    try:
        # Run the LLM - Gemini returns the fully populated Pydantic object directly!
        result = chain.invoke({
            "house_rules": house_rules,
            "diff": diff
        })
        return result
        
    except Exception as e:
        print(f"Gemini API Error: {e}")
        # Ultimate fallback if the network fails or API rate limits
        return PRReviewResult(
            risk_score=1,
            risk_summary="The AI Reviewer encountered an API connection error.",
            merge_decision="COMMENT",
            comments=[]
        )