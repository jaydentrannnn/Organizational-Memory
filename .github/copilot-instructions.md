 # Copilot Instructions — Organizational Memory (Enron Dataset)

## Project Context

Hackathon project demonstrating "Organizational Memory" — passive ingestion of email data enabling natural language queries to surface
decisions and their reasoning. Uses the Enron email dataset. Built entirely on AWS services.

## Tech Stack

- **Language**: Python 3.11
- **Frontend**: Streamlit
- **Cloud**: AWS (S3, Lambda, API Gateway, Bedrock, OpenSearch Serverless, CloudWatch, IAM, Amplify)
- **Key SDK**: `boto3` for all AWS interactions
- **No ORMs, no databases beyond OpenSearch Serverless**

## Architecture

S3 (parsed .txt emails)
   → Bedrock Knowledge Base (managed chunking + Titan Embeddings v2 + OpenSearch Serverless vector store)
   → Bedrock Agent (query orchestration, Claude 3 Sonnet)
   → Lambda (API handler, calls retrieveandgenerate)
   → API Gateway HTTP API (POST /ask)
   → Streamlit frontend (search bar + answer + source citations)

## Project Structure

organizational-memory/
├── copilot-instructions.md
├── README.md
├── data/
│   └── emails.csv              # Enron dataset from Kaggle
├── pipeline/
│   ├── parse_emails.py         # CSV → individual .txt files
│   └── uploadtos3.py         # Upload to S3 bucket
├── backend/
│   └── lambda_function.py      # Lambda handler
├── frontend/
│   └── app.py                  # Streamlit app
└── infra/
    └── setup.sh                # AWS CLI resource creation

## Code Style

- Type hints on all function signatures
- Docstrings on public functions (one-liner is fine)
- No classes unless necessary — prefer functions
- Use `logging` module, not `print`, except in pipeline scripts where `print` is fine for progress
- f-strings for string formatting
- Keep functions short — under 30 lines
- No unused imports

## AWS Conventions

- Region: `us-east-1`
- All AWS calls via `boto3`
- Use environment variables for resource IDs (`KB_ID`, `AWS_REGION`, `S3_BUCKET`)
- Lambda timeout: 30 seconds
- Lambda memory: 256MB
- Lambda runtime: `python3.11`
- API Gateway: HTTP API type (not REST API)
- CORS: allow all origins (hackathon only, not production)

## Data Pipeline Details

### Email Parsing (`pipeline/parse_emails.py`)
- Input: `data/emails.csv` — columns are `file` and `message`
- The `message` column contains raw RFC 2822 email format — parse with Python's `email` module
- Extract: `From`, `To`, `Date`, `Subject`, `Body`
- Drop duplicates and empty bodies
- Limit to 20k-50k emails
- Output: one `.txt` file per email in `data/parsed/` with format:

   From: <sender>
   To: <recipient>
   Date: <date>
   Subject: <subject>

   <body text>

### S3 Upload (`pipeline/upload_to_s3.py`)
- Bucket: `enron-org-memory` (configurable via env var)
- Prefix: `emails/`
- Use concurrent uploads for speed (`concurrent.futures.ThreadPoolExecutor`)

## Backend Details

### Lambda Function (`backend/lambda_function.py`)
- Receives: `{"question": "..."}`
- Calls: `bedrock-agent-runtime` client `retrieve_and_generate`
- Returns: `{"answer": "...", "sources": [{"text": "...", "location": {...}}]}`
- Truncate source snippets to 500 chars
- Handle errors: return 429 on throttling, 504 on timeout, 500 on unknown
- Response must include `Access-Control-Allow-Origin: *` header

### Bedrock Configuration
- Knowledge Base embedding model: `amazon.titan-embed-text-v2:0`
- Generation model: `anthropic.claude-3-sonnet-20240229-v1:0`
- Model ARN format: `arn:aws:bedrock:{region}::foundation-model/{model-id}`

### Bedrock Agent System Prompt

You are an organizational memory system for Enron Corporation.
Given email excerpts from Enron's internal communications, answer the user's question.
Focus on extracting the REASONING behind decisions — not just what happened, but WHY.
Always cite which emails you're drawing from (sender, date, subject line).
If you don't have enough context to answer confidently, say so.

## Frontend Details

### Streamlit App (`frontend/app.py`)
- Page config: title "Ask Enron", centered layout
- Components:
   - Title: "🧠 Organizational Memory — Ask Enron"
   - Caption with brief explanation
   - 3-4 example question buttons (use `st.button`)
   - `st.text_input` for custom questions
   - `st.spinner` while waiting
   - `st.markdown` for answer
   - `st.expander` for source email citations
- API call: `requests.post(API_URL, json={"question": q})`
- API URL from environment variable `API_URL`

### Example Questions
- "Why did Enron use special purpose entities?"
- "What concerns did employees raise about accounting practices?"
- "Who was involved in the California energy trading?"
- "What did executives know about the Raptor transactions?"

## Things to Avoid
- Do NOT add authentication (no Cognito) — hackathon demo
- Do NOT add PII scrubbing — Enron data is public record
- Do NOT use FAISS — we want OpenSearch Serverless for AWS service count
- Do NOT use LangChain — call Bedrock APIs directly via boto3
- Do NOT create CloudFormation/CDK templates — use AWS CLI or console
- Do NOT over-engineer error handling — basic try/except is fine
- Do NOT add tests — hackathon time constraint

## Dependencies

boto3
streamlit
pandas
requests

No other dependencies needed. Keep it minimal.