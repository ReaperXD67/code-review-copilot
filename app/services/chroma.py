import logging
import os
import chromadb
from langchain_chroma import Chroma
from langchain_pinecone import PineconeVectorStore
from langchain_google_genai import GoogleGenerativeAIEmbeddings

# 1. Setup the Gemini Embedding Model
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

embeddings = GoogleGenerativeAIEmbeddings(
    model="models/gemini-embedding-001", 
    google_api_key=GEMINI_API_KEY
)

# 2. Dynamic Vector Store Router
def get_vector_store():
    """Routes to the correct database based on the environment."""
    
    if ENVIRONMENT == "production":
        # --- CLOUD PRODUCTION (Pinecone) ---
        # Requires PINECONE_API_KEY to be set in your production environment
        return PineconeVectorStore(
            index_name="code-review-copilot", 
            embedding=embeddings
        )
    else:
        # --- LOCAL DEVELOPMENT (ChromaDB) ---
        chroma_client = chromadb.HttpClient(host="chromadb", port=8000)
        return Chroma(
            client=chroma_client,
            collection_name="pr_house_rules",
            embedding_function=embeddings
        )

# Initialize the universal vector store instance
vector_store = get_vector_store()

# ---------------------------------------------------------
# The functions below remain EXACTLY the same!
# ---------------------------------------------------------

def learn_convention(rule: str):
    """Embeds and saves a new coding rule to the vector database."""
    vector_store.add_texts(texts=[rule])
    return True

def retrieve_relevant_rules(diff_text: str) -> str:
    """Finds the top 3 most relevant rules based on the code being changed in the PR."""
    try:
        results = vector_store.similarity_search(query=diff_text, k=3)
        
        if not results:
            return "None"
        
        formatted_rules = "\n".join([f"- {doc.page_content}" for doc in results])
        return formatted_rules
    except Exception as e:
        logging.error(f"Error retrieving relevant rules: {e}")
        return "None"