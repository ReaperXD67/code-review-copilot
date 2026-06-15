import os
import chromadb
from langchain_chroma import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings

# 1. Setup the Gemini Embedding Model
# This translates human-readable rules into queryable mathematical vectors
# 1. Setup the Gemini Embedding Model
# 1. Setup the Gemini Embedding Model
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Updated to the new 2026 standard embedding model
embeddings = GoogleGenerativeAIEmbeddings(
    model="models/gemini-embedding-001", 
    google_api_key=GEMINI_API_KEY
)

# 2. Connect to the local Dockerized ChromaDB instance
# Because FastAPI and Chroma are on the same Docker network, we use the service name.
chroma_client = chromadb.HttpClient(host="chromadb", port=8000)

# 3. Initialize the LangChain VectorStore
vector_store = Chroma(
    client=chroma_client,
    collection_name="pr_house_rules",
    embedding_function=embeddings
)

def learn_convention(rule: str):
    """Embeds and saves a new coding rule to the vector database."""
    vector_store.add_texts(texts=[rule])
    return True

def retrieve_relevant_rules(diff_text: str) -> str:
    """Finds the top 3 most relevant rules based on the code being changed in the PR."""
    print(f"Retrieving rules for diff context: {diff_text[:100]}...")
    try:
        # Perform a semantic search to find rules related to the diff context
        results = vector_store.similarity_search(query=diff_text, k=3)
        
        if not results:
            return "None"
        
        # Format the extracted rules into a bulleted list for the Gemini prompt
        formatted_rules = "\n".join([f"- {doc.page_content}" for doc in results])
        return formatted_rules
    except Exception as e:
        print(f"ChromaDB Retrieval Error: {e}")
        return "None"