# Refined plan: parallel work and integration

This document expands the hackathon plan so **Person 1 (Data / Infra)**, **Person 2 (Backend)**, and **Person 3 (Frontend / Demo)** can work **independently and in parallel**, then **connect** into one working pipeline.

---

## 1. End-to-end pipeline (target state)

```text
emails.csv  →  parse  →  data/parsed/*.txt  →  S3  →  Bedrock Knowledge Base
                                                         ↓
Streamlit  →  API Gateway  →  Lambda  →  Bedrock (retrieve + generate)
```

**Single integration decision (do this at kickoff):**

| Option | Person 1 sets up | Person 2 implements |
|--------|------------------|---------------------|
| **A — Knowledge Base only (recommended for speed)** | S3 data source + KB sync to OpenSearch Serverless | `bedrock-agent-runtime` `retrieve_and_generate` with `KNOWLEDGE_BASE` + `knowledgeBaseId` |
| **B — Bedrock Agent** | KB + Agent attached to same KB, agent prepared | Invoke **agent** (agent ID + alias), not raw KB `retrieve_and_generate` |

The original plan mentions both a **Bedrock Agent** and a **Lambda** snippet that calls the **KB** directly. The team must pick **A or B** and keep the diagram, IAM, and Lambda code consistent.

---

## 2. Shared agreements (everyone, first 15 minutes)

Document these in one place (e.g. `INTEGRATION.md`, pinned chat, or a section in this file copied to the repo):

| Item | Example | Notes |
|------|---------|--------|
| AWS region | `us-east-1` | Same for S3, Bedrock, Lambda, API Gateway |
| S3 bucket | `enron-org-memory-<team-id>` | |
| S3 prefix for parsed emails | `emails/` | KB data source points here only |
| Parsed file naming | `email_{index}.txt` | Stable, unique names |
| HTTP contract | See §5 | Person 2 owns the canonical schema |

**Artifact file (recommended):** `team/outputs.env` (gitignored) or `team/outputs.example` (committed) with empty placeholders filled as resources are created:

```bash
AWS_REGION=us-east-1
S3_BUCKET=
S3_PREFIX=emails/
KNOWLEDGE_BASE_ID=          # Option A
# AGENT_ID=                 # Option B
# AGENT_ALIAS_ID=           # Option B
LAMBDA_FUNCTION_NAME=enron-query
API_GATEWAY_ASK_URL=
```

---

## 3. Person 1 — Data pipeline and AWS data plane (parallel breakdown)

### 3.1 Can start immediately (no dependency on others)

- **Prerequisites:** AWS account, Bedrock access for Titan Embeddings v2 and Claude 3 Sonnet, Kaggle `emails.csv`, Python 3.11+, `boto3` / `pandas`.
- **Task: Parse emails (`pipeline/parse_emails.py`)**
  - Read `data/emails.csv` (`file`, `message`).
  - Parse RFC 2822 with Python `email` module; extract From, To, Date, Subject, plain-text body.
  - Drop null/empty bodies; dedupe by body hash; cap at **50,000** (or **20,000** if time-constrained).
  - Write `data/parsed/email_{index}.txt` with the agreed header block + body.
- **Task: Upload script (`pipeline/upload_to_s3.py`)**
  - Implement concurrent upload with `ThreadPoolExecutor` (10–20 workers), progress logging.
  - Bucket name and prefix from env vars or CLI args so Person 2/3 never hardcode your bucket.

### 3.2 Can run in parallel once AWS CLI is ready (still independent of Lambda/UI)

- **Create S3 bucket** (if not exists) and upload `data/parsed/*` to `s3://$S3_BUCKET/$S3_PREFIX`.
- **OpenSearch Serverless (start early — long wait)**
  - Encryption policy, network policy, data access policy (Bedrock KB role + team principals), then **VECTORSEARCH** collection (e.g. `enron-memory`).
  - Poll until collection status is **ACTIVE** (often 10–20+ minutes).
- **Bedrock Knowledge Base (console is fine)**
  - Data source: S3 prefix above.
  - Embeddings: Titan Text Embeddings v2.
  - Vector store: the OpenSearch Serverless collection.
  - IAM role for KB: S3 read + OpenSearch Serverless + Bedrock invoke as required by the wizard.
  - **Start sync as soon as a first batch of objects exists** (even a subset); expand to full 50k when parser is done.
- **Optional (Option B only): Bedrock Agent**
  - Attach the same KB; system prompt for “why / reasoning” + citations; prepare agent; record **Agent ID** and **Alias ID**.

### 3.3 Person 1’s “handoff package” to Person 2

When ready, Person 1 fills in for Person 2:

- `S3_BUCKET`, `S3_PREFIX` (verified object count).
- `KNOWLEDGE_BASE_ID` (and if Option B: `AGENT_ID`, `AGENT_ALIAS_ID`).
- **KB execution role ARN** (Person 2 needs this only if debugging cross-account or documenting; Lambda uses a **different** role — see §4).
- Confirmation: **KB sync status = COMPLETE** (or “sync running — expect completion by …”).

Person 1 does **not** need the API URL or Streamlit to finish ingestion.

---

## 4. Person 2 — Backend API (parallel breakdown)

### 4.1 Can start immediately (mock-friendly)

- **Implement `backend/lambda_function.py`** to the agreed HTTP contract (§5).
- **Local / unit-level behavior**
  - Parse `event["body"]` JSON; validate `question`; return 400 if empty.
  - Structured `logging` or `print` with a request id for CloudWatch.
  - CORS headers on all responses including errors.
- **Stub mode (recommended)**  
  If `USE_MOCK=1` or missing `KB_ID` / agent IDs, return a fixed JSON answer and fake `sources` so Person 3 can integrate before Bedrock is live.

### 4.2 After Person 1 provides identifiers (short blocking window)

- **Option A:** Set environment `KB_ID`, `AWS_REGION`; call `retrieve_and_generate` with `knowledgeBaseConfiguration` and Claude Sonnet model ARN as in the original plan.
- **Option B:** Switch handler to agent invocation APIs using `AGENT_ID` and `AGENT_ALIAS_ID`; map response shape to the same `answer` + `sources` contract if possible.
- **IAM role for Lambda** (separate from KB role): permissions for `bedrock:RetrieveAndGenerate` (and/or agent invoke), plus **CloudWatch Logs** (`logs:CreateLogGroup`, `CreateLogStream`, `PutLogEvents`).
- **Deploy:** zip, `create-function` / `update-function-code`, set env vars, timeout **≥ 30s**, memory **256MB+** if needed.
- **Verify:** `aws lambda invoke` with API Gateway–style body.

### 4.3 Can run in parallel with Person 1 after Lambda exists (even with mock)

- **API Gateway HTTP API**
  - CORS: `POST`, `OPTIONS`, `Content-Type` (and any headers Streamlit sends).
  - Route `POST /ask` → Lambda integration; `$default` stage auto-deploy.
  - `lambda:InvokeFunction` permission for `apigateway.amazonaws.com`.
- **Smoke test:** `curl` POST with JSON body.

### 4.4 Person 2’s “handoff package” to Person 3

- Full URL: `https://<api-id>.execute-api.<region>.amazonaws.com/ask` (or `/stage/ask` if not `$default`).
- Example `curl` command and a sample JSON response.
- Note any **API keys** (if added later — original plan uses none).

Person 2 does **not** need Streamlit running to finish the API.

---

## 5. Person 3 — Frontend and demo (parallel breakdown)

### 5.1 Can start immediately

- **`frontend/app.py` (Streamlit)**
  - Layout: title, caption, example question buttons, `st.text_input`, spinner, answer markdown, sources in expander.
  - Read `API_URL` from environment (default placeholder URL is fine for layout only).
- **Defensive UI:** empty question, timeout (e.g. 35s), display `error` field from JSON, show raw message on non-JSON failure.

### 5.2 As soon as Person 2 exposes mock or real API

- Set `API_URL` to Person 2’s URL (local: `API_URL=... streamlit run frontend/app.py`).
- End-to-end click test with the four example questions from the original plan.

### 5.3 Hosting (parallel once app works locally)

- **Fast path:** EC2 AL2023, Python, deps, clone repo, `streamlit run` on port **8501**, security group open to judges’ network or your IP; document URL `http://<public-ip>:8501`.
- **Slides / demo script / backup video** — no dependency on Person 1 or 2 after the app is stable.

### 5.4 Person 3’s feedback to the team (optional but helpful)

- If CORS or preflight fails, paste browser devtools error for Person 2.
- If payload shape differs, request a one-line sample response from Person 2.

---

## 6. What runs in parallel (timeline view)

| Time window | Person 1 | Person 2 | Person 3 |
|-------------|----------|----------|----------|
| Early | Parse + upload script; start S3 upload when first files exist | Lambda + mock; zip layout; IAM draft | Streamlit UI + examples |
| After bucket exists | Full upload; **OpenSearch + KB + sync** (long pole) | Deploy Lambda (mock); **API Gateway** | Wire `API_URL` to mock API |
| After KB sync complete | Console KB test; fix data quality if needed | Flip env to real `KB_ID`; fix throttling/retries | Real Q&A polish |
| Late | Support re-sync if parser changes | CloudWatch verification | EC2 hosting + recording |

**Long-running tasks** (Person 1): OpenSearch collection provisioning; KB initial sync — **start these as early as possible** and work on other tasks while waiting.

---

## 7. How to connect the three tracks (integration checklist)

Execute in order for a **first green end-to-end**:

1. **Data in S3** — Person 1: `aws s3 ls s3://$BUCKET/$PREFIX` shows expected file count.
2. **Search index ready** — Person 1: Bedrock KB sync **COMPLETE**; console “Test knowledge base” returns sensible chunks.
3. **Lambda real path** — Person 2: env vars set; invoke returns `answer` + `sources` for a known question.
4. **Public API** — Person 2: `curl` to `/ask` returns the same JSON shape.
5. **UI** — Person 3: Streamlit with `API_URL` shows answer + sources.
6. **Demo dry run** — All: run the four example questions; capture backup video.

**If something breaks:**

| Symptom | Likely layer |
|---------|----------------|
| No objects in S3 | Person 1 parser/upload |
| KB sync failed / empty retrieval | Person 1 S3 prefix, IAM KB role, file format |
| Lambda 403/AccessDenied on Bedrock | Person 2 IAM policy or wrong region/model ARN |
| Lambda 200 but empty answer | KB empty, wrong KB ID, or query mismatch |
| Browser CORS error | Person 2 API Gateway CORS + OPTIONS |
| UI shows error / timeout | Person 3 `API_URL`; Person 2 timeout/throttling |

---

## 8. HTTP contract (canonical — keep stable)

**Request**

```http
POST /ask
Content-Type: application/json

{"question": "Why did Enron use special purpose entities?"}
```

**Success response (200)**

```json
{
  "answer": "string",
  "sources": [
    {
      "text": "string (excerpt)",
      "location": {}
    }
  ]
}
```

**Error responses**

- `400` — missing or empty `question`
- `429` — rate limited (optional handling)
- `500` — server error; body `{"error": "message"}`

Person 2 owns the exact field names; Person 3 must not rename `answer` / `sources` / `error` without team agreement.

---

## 9. Risks called out in the original plan (short)

- **KB sync duration** — reduce corpus or start sync on a subset first.
- **OpenSearch provisioning delay** — create collection immediately after bucket decision.
- **Bedrock throttling** — retries with backoff in Lambda; optional fallback model.
- **Cost** — delete OpenSearch Serverless collection after the event (largest hourly cost).

---

## 10. Summary

| Person | Independent work | Needs from others to go “live” |
|--------|------------------|--------------------------------|
| **1** | Parse, upload, OpenSearch, KB, sync, (optional) Agent | Region + bucket naming agreement |
| **2** | Lambda structure, IAM, API Gateway, CORS, logging | KB ID (and agent IDs if Option B); region |
| **3** | Streamlit UX, hosting prep, slides, recording | `API_URL` from Person 2 |

**Connection mechanism:** one shared **outputs** file plus the **fixed HTTP contract** in §8, **Option A vs B** decided at kickoff, and the **integration checklist** in §7 run once as a group before demo time.
