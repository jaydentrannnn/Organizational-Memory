# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Hackathon project demonstrating "Organizational Memory" — passive ingestion of Enron email data enabling natural language queries to surface decisions and their reasoning. Built entirely on AWS.

## Architecture

```
S3 (parsed .txt emails)
  → Bedrock Knowledge Base (Titan Embeddings v2 + OpenSearch Serverless vector store)
  → Bedrock Agent (Claude 3 Sonnet, retrieve_and_generate)
  → Lambda (API handler, Python 3.11)
  → API Gateway HTTP API (POST /ask)
  → Streamlit frontend
```

## Commands

```bash
# Provision S3 bucket
bash infra/setup.sh

# Parse emails (CSV → sharded .txt files in data/parsed/)
python pipeline/parse_emails.py

# Upload parsed emails to S3 (run from EC2 for speed)
python pipeline/uploadtos3.py

# Run frontend locally
API_URL=https://<api-id>.execute-api.us-east-1.amazonaws.com/ask streamlit run frontend/app.py

# Deploy Lambda
cd backend && zip function.zip lambda_function.py
aws lambda update-function-code --function-name enron-query --zip-file fileb://function.zip
```

## Data Pipeline

**`pipeline/parse_emails.py`** — reads `data/raw/emails.csv` (columns: `file`, `message`). Streams in 10k-row chunks via `pd.read_csv(chunksize=10_000)` to keep memory bounded. Parses each `message` with Python's `email` module, extracts From/To/Date/Subject/Body (walks multipart for `text/plain`), drops empty bodies, and deduplicates on MD5 body hash (~30–40% of Enron corpus are sent/received duplicates). Writes to `data/parsed/{idx//5000}/email_{idx}.txt` (sharded, ≤5k files per dir). Checkpoints progress to `data/parsed/.progress.json` every chunk — restartable after interruption. Expected output: ~300k–350k files.

Output format per file:
```
From: <sender>
To: <recipient>
Date: <date>
Subject: <subject>

<body>
```

**`pipeline/uploadtos3.py`** — uploads `data/parsed/` to `s3://enron-org-memory/emails/` using `ThreadPoolExecutor(64)` + `botocore.config.Config(max_pool_connections=64)`. Lists existing S3 keys at startup and skips already-uploaded files (idempotent reruns). Run from EC2 in `us-east-1` for multi-Gbps throughput; 500k PUTs from a home connection takes hours.

## Backend

**`backend/lambda_function.py`** — receives `{"question": "..."}`, calls `bedrock-agent-runtime` `retrieve_and_generate` with the Knowledge Base ID, returns `{"answer": "...", "sources": [...]}`. Must include `Access-Control-Allow-Origin: *` header. Truncate source snippets to 500 chars.

- Bedrock embedding model: `amazon.titan-embed-text-v2:0`
- Generation model: `anthropic.claude-3-sonnet-20240229-v1:0`
- Model ARN format: `arn:aws:bedrock:{region}::foundation-model/{model-id}`
- Error codes: 429 on throttling, 504 on timeout, 500 on unknown

Environment variables: `KB_ID`, `AWS_REGION` (us-east-1), `S3_BUCKET`.

## Frontend

**`frontend/app.py`** — Streamlit app. API URL from `API_URL` env var. Calls `requests.post(API_URL, json={"question": q})`. Shows spinner, renders answer as markdown, source citations in `st.expander`.

Pre-loaded example questions: "Why did Enron use special purpose entities?", "What concerns did employees raise about accounting practices?", "Who was involved in the California energy trading?", "What did executives know about the Raptor transactions?"

## Code Conventions

- Type hints on all function signatures
- `print` is fine in pipeline scripts; use `logging` elsewhere
- Prefer functions over classes
- Keep functions under 30 lines
- f-strings for formatting

## Hard Constraints

- No authentication (no Cognito) — hackathon demo
- No LangChain — call Bedrock APIs directly via boto3
- No CloudFormation/CDK — use AWS CLI or console
- No FAISS — use OpenSearch Serverless (AWS service count matters for hackathon scoring)
- No PII scrubbing — Enron data is public record

## Dependencies

```
boto3
streamlit
pandas
requests
```

## Timing Notes

- OpenSearch Serverless collection creation: 10–20 min
- Bedrock KB sync: ~30–60 min per 50k docs → full ~350k corpus = 3–7 hours
- Bedrock `retrieve_and_generate` per query: 5–10 sec → Lambda timeout must be 30s
- Parse pipeline (~500k rows): 5–15 min locally
- S3 upload from EC2 (64-way concurrency): ~5–10 min; from home: hours
