# Copilot Instructions — Organizational Memory

## Build, test, and lint commands

There is no configured test or lint framework in the current repository state (`pytest`, `ruff`, `flake8`, etc. are not present).

Use the documented run/deploy commands from `CLAUDE.md`:

```bash
# Parse Enron CSV into individual text emails
python pipeline/parse_emails.py

# Upload parsed emails to S3
python pipeline/uploadtos3.py

# Run Streamlit frontend locally
cd frontend && streamlit run app.py

# Package and deploy Lambda code
cd backend && zip function.zip lambda_function.py
aws lambda update-function-code --function-name enron-query --zip-file fileb://function.zip

# Sync local parsed emails to S3
aws s3 sync data/parsed/ s3://enron-org-memory/emails/

# Provision AWS resources
bash infra/setup.sh
```

Single-test command: not applicable (no test suite configured yet).

## High-level architecture

This project is a retrieval-augmented "organizational memory" system for Enron emails:

1. `pipeline/parse_emails.py` transforms `data/emails.csv` (`file`, `message`) into one `.txt` email per document in `data/parsed/`.
2. `pipeline/uploadtos3.py` uploads those documents to S3 (`emails/` prefix).
3. Bedrock Knowledge Base ingests from S3 and stores embeddings in OpenSearch Serverless (Titan Embeddings v2).
4. `backend/lambda_function.py` receives `{"question": "..."}` and calls Bedrock `retrieve_and_generate`.
5. API Gateway exposes `POST /ask` for the Lambda.
6. `frontend/app.py` sends user questions to the API and renders answer + source citations.

## Key repository conventions

- Keep all AWS interactions in `boto3` (no LangChain abstraction layer).
- Prefer function-based Python modules; avoid adding classes unless clearly needed.
- Use `logging` in backend/frontend code, but `print` is acceptable for pipeline progress scripts.
- Required env vars across components: `KB_ID`, `AWS_REGION`, `S3_BUCKET`, `API_URL`.
- AWS defaults for this project: `us-east-1`, Lambda runtime `python3.11`, timeout `30s`, memory `256MB`, API Gateway HTTP API with permissive CORS (`*`) for demo use.
- Retrieval responses should include source citations and truncate source snippets to ~500 chars.
- Treat this as a hackathon demo scope: do not add Cognito/auth, FAISS, CloudFormation/CDK, or PII scrubbing unless explicitly requested.
- File naming note: the current uploader script in this repo is `pipeline/uploadtos3.py` (no underscore).
