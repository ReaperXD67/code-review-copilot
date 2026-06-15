import os
import logging
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from app.models import PRReviewResult

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=GEMINI_API_KEY,
    temperature=0.0 # Dropped to 0 for maximum strictness
)

parser = PydanticOutputParser(pydantic_object=PRReviewResult)

REVIEW_PROMPT = """
You are a machine-to-machine code review API. Your ONLY purpose is to analyze code diffs and return raw JSON data.

House Rules to Enforce:
{house_rules}

Code Diff:
{diff}

LINE NUMBER INSTRUCTIONS:
The diff has been pre-processed. Added and context lines start with a bracketed number, e.g., [15].
Extract the integer inside the brackets for the `line_number` field. Do not guess.

CRITICAL SYSTEM INSTRUCTION:
You are forbidden from using conversational text, greetings, or markdown formatting (do NOT wrap the output in ```json blocks). 
You MUST output EXACTLY and ONLY a valid JSON object matching this schema:
{format_instructions}
"""

def analyze_pr_diff(diff: str, house_rules: str = "None") -> PRReviewResult:
    """Main entry point for analyzing the diff. Imported by main.py."""
    
    prompt = PromptTemplate(
        template=REVIEW_PROMPT,
        input_variables=["house_rules", "diff"],
        partial_variables={"format_instructions": parser.get_format_instructions()}
    )
    
    chain = prompt | llm | parser
    
    try:
        return chain.invoke({
            "house_rules": house_rules,
            "diff": diff
        })
        
    except Exception as e:
        logging.error(f"Error analyzing PR diff: {e}")
        return PRReviewResult(
            risk_score=1,
            risk_summary="The AI Reviewer encountered a parsing error.",
            merge_decision="COMMENT",
            comments=[]
        )