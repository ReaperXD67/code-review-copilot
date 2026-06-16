# 🤖 GenAI Code Review Copilot

An autonomous, self-learning Code Review Copilot built with FastAPI, LangChain, and Google Gemini. It reviews Pull Requests in real-time, enforces repository-specific house rules using RAG (Retrieval-Augmented Generation), and automatically learns conventions from past merged PRs.

---

## ✨ Features
* **Real-Time PR Review:** Intercepts GitHub Webhooks to analyze code diffs instantly.
* **Inline GitHub Comments:** Posts contextual, severity-tagged suggestions directly to the exact line of code in the PR.
* **Multi-Environment RAG:** Uses local ChromaDB for development and serverless Pinecone for production.
* **Matryoshka Vector Compression:** Utilizes Google's native SDK to compress 3072-dimension embeddings into 1024 dimensions, saving database costs.
* **Background History Ingestion:** Asynchronously scrapes merged PR history to learn implicit team coding conventions without blocking the webhook thread.
* **Multi-Tenant Data Isolation:** Strictly isolates rules based on the `Owner/Repo_Name` namespace.

---

## 🏗️ Architecture Stack
* **Framework:** FastAPI, Python 3.11
* **AI/LLM:** Google Gemini 2.5 Flash, Gemini Embeddings 001
* **Vector DB:** Pinecone (Prod) / ChromaDB (Dev)
* **Orchestration:** LangChain
* **Containerization:** Docker & Docker Compose

---

## 🚀 Quickstart & Installation

### 1. Prerequisites
* Docker and Docker Compose installed.
* A GitHub Personal Access Token (with `repo` and `pull_requests:write` permissions).
* A Google Gemini API Key.
* (Optional) A Pinecone API Key for production.

### 2. Environment Variables
Create a `.env` file in the root directory:
```env
GITHUB_TOKEN=your_github_token
GEMINI_API_KEY=your_gemini_key
WEBHOOK_SECRET=your_secure_random_string

# For Production (Optional)
ENVIRONMENT=development # Change to 'production' to use Pinecone
PINECONE_API_KEY=your_pinecone_key
```

### 3. Build and Run
Start the API and local ChromaDB containers:

```bash
docker-compose up --build -d
```

The FastAPI server will be available at http://localhost:8000.
Access the interactive API documentation at http://localhost:8000/docs.

### 4. Run Tests
The core request-handling and diff-parsing behavior can be checked without live GitHub, Gemini, or Chroma credentials:

```bash
python -m unittest discover -s tests
```

---

## 🛠️ Usage
### Configuring the GitHub Webhook
1. Go to your GitHub Repository -> Settings -> Webhooks -> Add webhook.

2. Payload URL: https://your-public-url.com/webhook/github (Use ngrok if testing locally).

3. Content type: application/json.

4. Secret: Paste the WEBHOOK_SECRET from your .env file.

5. Select Let me select individual events and check Pull requests.

---

## Manual Rule Injection
You can manually teach the AI a new rule using the Swagger UI or via cURL:

```bash
curl -X 'POST' \
  'http://localhost:8000/conventions/learn' \
  -H 'Content-Type: application/json' \
  -d '{
  "rule": "All print statements must be replaced with logging.info()",
  "repo_name": "YourOwner/YourRepo"
}'
```

---

## Automatic History Learning

The moment a new PR is opened or synchronized, the API will immediately trigger a background task to scrape that repository's last 10 merged PRs, extract the underlying house rules using AI, and save them to the database for future reviews.

---

## 🛡️ Security
This application implements HMAC SHA256 signature validation to ensure all incoming webhooks are strictly authenticated by GitHub, preventing unauthorized access or abuse.
