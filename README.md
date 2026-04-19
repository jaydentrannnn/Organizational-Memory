# 🧠 Organizational Memory

Preventing institutional amnesia — natural language Q&A over 250,000+ Enron emails, powered by Amazon Bedrock.

## Problem

When key employees leave, they take years of invisible context with them — why a vendor was blacklisted, why a pricing decision was made, the reasoning behind a policy change. Organizations slowly forget themselves.

## Solution

We built a RAG pipeline that ingests an organization's email corpus and lets anyone ask natural language questions to surface not just *what* happened, but *why*. The Enron email dataset (517k messages, deduplicated to ~248k) serves as our proof of concept.

## Architecture

```
emails.csv → parse → S3 (248k .txt files)
                       ↓
              Bedrock Knowledge Base
              (Titan Embeddings v2 + OpenSearch Serverless)
                       ↓
              Lambda (Nova Pro via Converse API)
                       ↓
              API Gateway HTTP API (POST /ask)
                       ↓
              Streamlit frontend
```

## AWS Services

- **S3** — parsed email storage (`enron-org-memory-data/emails/`)
- **Amazon Bedrock Knowledge Bases** — RAG retrieval with Titan Embeddings v2
- **OpenSearch Serverless** — vector store backing the Knowledge Base
- **Amazon Bedrock** — answer generation via Nova Pro (Converse API)
- **Lambda** — API handler (Python 3.11, 60s timeout)
- **API Gateway** — HTTP API with CORS
- **EC2** — Streamlit hosting

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the frontend (replace with your API Gateway URL)
export API_URL=https://<api-id>.execute-api.us-west-2.amazonaws.com/ask
streamlit run frontend/app.py
```

## Example Questions

- "Why did Enron use special purpose entities?"
- "What concerns did employees raise about accounting practices?"
- "Who was involved in the California energy trading?"
- "What did executives know about the Raptor transactions?"

## Data Pipeline

1. **Download** — Enron email dataset from Kaggle (517k rows)
2. **Parse** — Extract headers + body, deduplicate by MD5 hash → 248k unique emails
3. **Upload** — 64-way concurrent upload to S3
4. **Index** — Bedrock KB syncs S3 → OpenSearch Serverless vector store

## Team

Built at the AWS Hackathon.
