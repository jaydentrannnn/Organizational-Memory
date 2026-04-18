# Copilot Instructions - Organizational Memory

## Build, test, and lint commands

There is currently no configured automated test or lint framework in this repository.

Use the project run/deploy commands from `CLAUDE.md`:

```bash
# (Optional) Download Enron dataset to data/raw/
python data/download.py

# Parse raw CSV into sharded text files in data/parsed/
python pipeline/parse_emails.py

# Upload parsed files to S3
python pipeline/uploadtos3.py

# Provision S3 bucket and public-access-block settings
bash infra/setup.sh

# Run Streamlit frontend locally
API_URL=https://<api-id>.execute-api.us-east-1.amazonaws.com/ask streamlit run frontend/app.py

# Package/deploy Lambda code
cd backend && zip function.zip lambda_function.py
aws lambda update-function-code --function-name enron-query --zip-file fileb://function.zip
```

Single-test command: not applicable (no test suite exists yet).

## High-level architecture

This project implements an AWS-based retrieval workflow for Enron emails:

1. `data/download.py` fetches the Kaggle Enron dataset into `data/raw/`.
2. `pipeline/parse_emails.py` reads `data/raw/emails.csv` in chunks, parses message headers/body, deduplicates by body hash, and writes one `.txt` email per document into sharded folders under `data/parsed/`, with resume state in `data/parsed/.progress.json`.
3. `pipeline/uploadtos3.py` uploads `data/parsed/` to `s3://enron-org-memory/emails/` using 64-way concurrency and skips keys that already exist in S3.
4. The intended serving path (documented in `CLAUDE.md`) is S3 -> Bedrock Knowledge Base (Titan Embeddings v2 + OpenSearch Serverless) -> Lambda/API Gateway -> Streamlit UI.

## Key repository conventions

- Keep AWS integrations in `boto3`; do not introduce LangChain wrappers.
- Prefer function-based Python modules over class-heavy designs.
- Use `print` for progress in pipeline scripts; use `logging` for backend/frontend services.
- Preserve the parser output contract exactly (`From/To/Date/Subject` header block followed by body text) because downstream retrieval indexing depends on this shape.
- Preserve parser scaling patterns: chunked CSV reads (`chunksize=10_000`), directory sharding (`idx // 5000`), and checkpointing via `.progress.json` for resumable runs.
- Preserve uploader idempotency and throughput patterns: pre-list S3 keys, skip existing objects, and use `ThreadPoolExecutor(64)` with matching S3 connection pooling.
- Keep demo scope constraints from `CLAUDE.md`: no Cognito/auth layer, no FAISS, no CloudFormation/CDK, and no PII scrubbing unless explicitly requested.
- AWS defaults assumed across docs/scripts: `us-east-1`, Lambda `python3.11`, 30s timeout, 256 MB memory, permissive CORS for demo API.
