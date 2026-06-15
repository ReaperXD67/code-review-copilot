import logging
import os
import chromadb
from langchain_chroma import Chroma
from langchain_pinecone import PineconeVectorStore
import google.generativeai as genai

# 1. Setup the Gemini Embedding Model
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

genai.configure(api_key=GEMINI_API_KEY)

class NativeGeminiEmbeddings:
    """A custom bridge that bypasses LangChain to use Google's native API directly."""
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Used by Pinecone when you save new house rules."""
        result = genai.embed_content(
            model="models/gemini-embedding-001",
            content=texts,
            task_type="retrieval_document", # Optimizes the vector for storage
            output_dimensionality=1024      # Natively requests the 1024 Matryoshka slice
        )
        # Google's SDK returns a dictionary; Pinecone expects a raw list of lists
        return result['embedding']

    def embed_query(self, text: str) -> list[float]:
        """Used by Pinecone when searching the diff text."""
        result = genai.embed_content(
            model="models/gemini-embedding-001",
            content=text,
            task_type="retrieval_query",    # Optimizes the vector for searching
            output_dimensionality=1024
        )
        return result['embedding']

# Initialize our custom native bridge
embeddings = NativeGeminiEmbeddings()

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