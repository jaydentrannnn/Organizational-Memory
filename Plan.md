  # 🧠 Organizational Memory — Preventing Institutional Amnesia

  ## Problem Statement

  When key employees leave, they take years of invisible context with them — why a vendor was blacklisted, why a pricing
  decision was made, the unofficial workaround for a broken process. Knowledge bases and wikis fail because writing
  documentation requires discipline nobody has. Companies slowly forget themselves, re-litigate the same decisions, and
  pay consultants to rediscover things they already knew.

  ## Solution

  A system that passively ingests email data and enables natural language queries to surface not just what was decided,
  but **why** — extracting reasoning chains embedded in conversations without requiring anyone to write documentation.

  For this hackathon, we demonstrate the concept using the **Enron email dataset** (~500k real corporate emails) as our
  data source, built entirely on **AWS services**.

  ## Demo

  A single search bar: "Ask your company anything." A user types a question like *"Why did Enron use special purpose
  entities?"* and gets a synthesized answer citing the actual email threads where that decision was discussed — with
  sender, date, and subject line attribution.

  ---

  ## Architecture

  ```mermaid
  flowchart LR
      A[Enron CSV Dataset] -->|parse_emails.py| B[Individual .txt Files]
      B -->|upload_to_s3.py| C[S3 Bucket]
      C --> D[Bedrock Knowledge Base]
      D -->|Titan Embeddings v2| E[OpenSearch Serverless]
      D --> F[Bedrock Agent + Claude 3 Sonnet]
      F --> G[Lambda Function]
      G --> H[API Gateway HTTP API]
      H --> I[Streamlit Frontend]

      style C fill:#FF9900,color:#000
      style D fill:#FF9900,color:#000
      style E fill:#FF9900,color:#000
      style F fill:#FF9900,color:#000
      style G fill:#FF9900,color:#000
      style H fill:#FF9900,color:#000

  AWS Services Used (11)

  ┌─────┬───────────────────────────────────┬───────────────────────────────────────────────────────┐
  │ #   │ Service                           │ Purpose                                               │
  ├─────┼───────────────────────────────────┼───────────────────────────────────────────────────────┤
  │ 1   │ **S3**                            │ Email document storage                                │
  │ 2   │ **Lambda**                        │ Backend API compute                                   │
  │ 3   │ **API Gateway**                   │ HTTP API endpoint                                     │
  │ 4   │ **Bedrock — Titan Embeddings v2** │ Email vectorization                                   │
  │ 5   │ **Bedrock — Claude 3 Sonnet**     │ Answer generation                                     │
  │ 6   │ **Bedrock Knowledge Base**        │ Managed RAG pipeline (chunking, embedding, retrieval) │
  │ 7   │ **Bedrock Agent**                 │ Query orchestration with system prompt                │
  │ 8   │ **OpenSearch Serverless**         │ Vector store for semantic search                      │
  │ 9   │ **CloudWatch**                    │ Logging and monitoring                                │
  │ 10  │ **IAM**                           │ Roles and access policies                             │
  │ 11  │ **Amplify / CloudFront + S3**     │ Frontend hosting                                      │
  └─────┴───────────────────────────────────┴───────────────────────────────────────────────────────┘

  ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

  Project Structure

  organizational-memory/
  ├── README.md
  ├── CLAUDE.md                    # Claude Code agent instructions
  ├── copilot-instructions.md      # GitHub Copilot instructions
  ├── data/
  │   ├── emails.csv               # Enron dataset from Kaggle (~1.3GB)
  │   └── parsed/                  # Output: individual .txt email files
  ├── pipeline/
  │   ├── parse_emails.py          # Parse CSV → .txt files
  │   └── upload_to_s3.py          # Upload parsed emails to S3
  ├── backend/
  │   └── lambda_function.py       # Lambda handler (Bedrock retrieve_and_generate)
  ├── frontend/
  │   └── app.py                   # Streamlit application
  └── infra/
      └── setup.sh                 # AWS CLI commands for resource creation

  ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

  Team Assignments

  Person 1 — Data Pipeline & AWS Infrastructure

  Owns: Parsing, S3 upload, OpenSearch Serverless, Bedrock Knowledge Base, Bedrock Agent

  Person 2 — Backend API

  Owns: Lambda function, API Gateway, CloudWatch logging, IAM roles for Lambda

  Person 3 — Frontend, Demo & Presentation

  Owns: Streamlit app, hosting, slides, demo script, backup recording

  ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

  Prerequisites (Everyone, Before Kickoff)

  - [ ] AWS account with Bedrock model access enabled:
    - amazon.titan-embed-text-v2:0
    - anthropic.claude-3-sonnet-20240229-v1:0

  - [ ] Download Enron dataset from Kaggle: Enron Email Dataset
  (https://www.kaggle.com/datasets/wcukierski/enron-email-dataset) — download emails.csv
  - [ ] Shared GitHub repo cloned by all team members
  - [ ] Python 3.11+ installed
  - [ ] AWS CLI configured with appropriate credentials
  - [ ] Install dependencies:

    pip install boto3 streamlit pandas requests

  - [ ] Agree on AWS region: us-east-1 (best Bedrock model availability)
  - [ ] Agree on S3 bucket name: enron-org-memory-<team-id>

  ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

  Detailed Task Breakdown

  Task 1: Parse Enron Emails (Person 1, Hour 0–1.5)

  Objective: Convert the raw Kaggle CSV into individual .txt files that Bedrock Knowledge Base can ingest.

  Implementation:

  - Load data/emails.csv with pandas (columns: file, message)
  - The message column contains raw RFC 2822 email format — parse with Python's email module to extract:
    - From
    - To
    - Date
    - Subject
    - Body (plain text payload)

  - Drop rows with empty/null bodies
  - Drop duplicate emails (deduplicate on body hash)
  - Limit to 50,000 emails (balance between coverage and KB sync time)
  - Write each email as a .txt file to data/parsed/ with naming: email_{index}.txt
  - File format:

    From: sender@enron.com
    To: recipient@enron.com
    Date: Mon, 14 May 2001 08:30:00 -0700
    Subject: Re: California Power Situation

    <email body text here>

  Output: data/parsed/ directory with 50k .txt files

  Verification: Spot-check 10 random files — confirm metadata is correct and body is readable.

  ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

  Task 2: Upload Emails to S3 (Person 1, Hour 1.5–2)

  Objective: Get all parsed emails into S3 for Bedrock Knowledge Base ingestion.

  Implementation:

  - Create S3 bucket via CLI or console
  - Upload all files from data/parsed/ to s3://<bucket>/emails/
  - Use concurrent uploads (concurrent.futures.ThreadPoolExecutor, 10-20 workers) for speed
  - Print progress (e.g., "Uploaded 5000/50000")

  Verification: aws s3 ls s3://<bucket>/emails/ | wc -l returns expected count.

  ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

  Task 3: Create OpenSearch Serverless Collection (Person 1, Hour 2–2.5)

  Objective: Provision the vector store that Bedrock Knowledge Base will use.

  Implementation:

  1. Create encryption policy (required before collection):

     aws opensearchserverless create-security-policy \
       --name enron-encryption \
       --type encryption \
       --policy '{"Rules":[{"ResourceType":"collection","Resource":["collection/enron-memory"]}],"AWSOwnedKey":true}'

  2. Create network policy (allow public access for hackathon):

     aws opensearchserverless create-security-policy \
       --name enron-network \
       --type network \
       --policy
  '[{"Rules":[{"ResourceType":"collection","Resource":["collection/enron-memory"]},{"ResourceType":"dashboard","Resource
  ":["collection/enron-memory"]}],"AllowFromPublic":true}]'

  3. Create data access policy (allow Bedrock and your IAM user):

     aws opensearchserverless create-access-policy \
       --name enron-access \
       --type data \
       --policy
  '[{"Rules":[{"ResourceType":"index","Resource":["index/enron-memory/*"],"Permission":["aoss:*"]},{"ResourceType":"coll
  ection","Resource":["collection/enron-memory"],"Permission":["aoss:*"]}],"Principal":["arn:aws:iam::<ACCOUNT_ID>:role/
  BedrockKBRole","arn:aws:iam::<ACCOUNT_ID>:root"]}]'

  4. Create collection:

     aws opensearchserverless create-collection \
       --name enron-memory \
       --type VECTORSEARCH

  ⚠️ This takes 10-20 minutes to become ACTIVE. Start immediately and move on to other tasks while waiting.

  Verification: aws opensearchserverless list-collections shows status ACTIVE.

  ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

  Task 4: Create Bedrock Knowledge Base (Person 1, Hour 2.5–3.5)

  Objective: Set up the managed RAG pipeline that connects S3 emails to OpenSearch vectors.

  Implementation (via AWS Console — faster than CLI for this):

  1. Go to Bedrock → Knowledge bases → Create
  2. Name: enron-organizational-memory
  3. IAM role: Create new or use existing with S3 + OpenSearch + Bedrock permissions
  4. Data source: S3, point to s3://<bucket>/emails/
  5. Embedding model: Titan Text Embeddings v2
  6. Vector store: Select existing OpenSearch Serverless collection enron-memory
  7. Create, then click Sync to start data ingestion

  ⚠️ Sync takes 30-60 minutes for 50k documents. Start ASAP. Work on other tasks while it runs.

  Verification: Bedrock console shows sync status as COMPLETE. Test with the built-in "Test Knowledge Base" chat in the
  console.

  ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

  Task 5: Create Bedrock Agent (Person 1, Hour 3.5–4)

  Objective: Create an agent with a system prompt optimized for reasoning extraction.

  Implementation (via AWS Console):

  1. Go to Bedrock → Agents → Create
  2. Name: enron-memory-agent
  3. Foundation model: Claude 3 Sonnet
  4. System prompt:

     You are an organizational memory system for Enron Corporation.
     Given email excerpts from Enron's internal communications, answer the user's question.
     Focus on extracting the REASONING behind decisions — not just what happened, but WHY.
     Always cite which emails you're drawing from (sender, date, subject line).
     If you don't have enough context to answer confidently, say so.

  5. Attach the Knowledge Base created in Task 4
  6. Create and prepare the agent
  7. Note the Agent ID and Agent Alias ID — Person 2 needs these

  Verification: Test in the Bedrock console chat. Ask "Why did Enron use special purpose entities?" and confirm it
  returns a cited answer.

  ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

  Task 6: Lambda Function (Person 2, Hour 0–2)

  Objective: Backend API that queries the Bedrock Knowledge Base and returns answers with source citations.

  Implementation:

  backend/lambda_function.py:

  import boto3, json, os

  client = boto3.client("bedrock-agent-runtime")

  def handler(event, context):
      try:
          body = json.loads(event.get("body", "{}"))
          question = body.get("question", "")
          if not question:
              return {"statusCode": 400, "headers": cors(), "body": json.dumps({"error": "question is required"})}

          resp = client.retrieve_and_generate(
              input={"text": question},
              retrieveAndGenerateConfiguration={
                  "type": "KNOWLEDGE_BASE",
                  "knowledgeBaseConfiguration": {
                      "knowledgeBaseId": os.environ["KB_ID"],
                      "modelArn":
  f"arn:aws:bedrock:{os.environ['AWS_REGION']}::foundation-model/anthropic.claude-3-sonnet-20240229-v1:0",
                  },
              },
          )

          citations = []
          for cite in resp.get("citations", []):
              for ref in cite.get("retrievedReferences", []):
                  citations.append({
                      "text": ref.get("content", {}).get("text", "")[:500],
                      "location": ref.get("location", {}),
                  })

          return {
              "statusCode": 200,
              "headers": cors(),
              "body": json.dumps({"answer": resp["output"]["text"], "sources": citations}),
          }
      except client.exceptions.ThrottlingException:
          return {"statusCode": 429, "headers": cors(), "body": json.dumps({"error": "Rate limited, try again"})}
      except Exception as e:
          return {"statusCode": 500, "headers": cors(), "body": json.dumps({"error": str(e)})}

  def cors():
      return {"Access-Control-Allow-Origin": "*", "Content-Type": "application/json"}

  Deployment:

  cd backend
  zip function.zip lambda_function.py
  aws lambda create-function \
    --function-name enron-query \
    --runtime python3.11 \
    --handler lambda_function.handler \
    --zip-file fileb://function.zip \
    --role <LAMBDA_ROLE_ARN> \
    --timeout 30 \
    --memory-size 256 \
    --environment "Variables={KB_ID=<KNOWLEDGE_BASE_ID>,AWS_REGION=us-east-1}"

  IAM Role for Lambda needs:

  - bedrock:InvokeModel
  - bedrock:Retrieve
  - bedrock:RetrieveAndGenerate
  - logs:CreateLogGroup, logs:CreateLogStream, logs:PutLogEvents

  Verification: aws lambda invoke --function-name enron-query --payload '{"body":"{\"question\":\"Who is Ken Lay?\"}"}'
  output.json && cat output.json

  ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

  Task 7: API Gateway (Person 2, Hour 2–3)

  Objective: Expose the Lambda function as an HTTP endpoint with CORS.

  Implementation:

  1. Create HTTP API:

     aws apigatewayv2 create-api \
       --name enron-memory-api \
       --protocol-type HTTP \
       --cors-configuration AllowOrigins="*",AllowMethods="POST,OPTIONS",AllowHeaders="Content-Type"

  2. Create Lambda integration
  3. Create route: POST /ask
  4. Create stage: $default with auto-deploy
  5. Grant API Gateway permission to invoke Lambda:

     aws lambda add-permission \
       --function-name enron-query \
       --statement-id apigateway \
       --action lambda:InvokeFunction \
       --principal apigateway.amazonaws.com

  Output: API URL like https://<api-id>.execute-api.us-east-1.amazonaws.com/ask

  Verification:

  curl -X POST https://<api-id>.execute-api.us-east-1.amazonaws.com/ask \
    -H "Content-Type: application/json" \
    -d '{"question":"What was the California energy crisis about?"}'

  ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

  Task 8: CloudWatch Logging (Person 2, Hour 3–3.5)

  Objective: Ensure all Lambda invocations are logged for debugging.

  Implementation:

  - Lambda automatically logs to CloudWatch if the IAM role has logs:* permissions
  - Add structured logging in the Lambda function (already included via print or logging)
  - Verify logs appear in CloudWatch → Log Groups → /aws/lambda/enron-query

  Verification: Make a test API call, confirm log entry appears in CloudWatch within 30 seconds.

  ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

  Task 9: Streamlit Frontend (Person 3, Hour 0–3)

  Objective: Build the demo UI — a search bar that queries the API and displays answers with source citations.

  Implementation:

  frontend/app.py:

  import streamlit as st
  import requests
  import os

  API_URL = os.environ.get("API_URL", "https://<api-id>.execute-api.us-east-1.amazonaws.com/ask")

  st.set_page_config(page_title="Ask Enron", layout="centered")
  st.title("🧠 Organizational Memory")
  st.caption("Preventing institutional amnesia — powered by AWS Bedrock")

  examples = [
      "Why did Enron use special purpose entities?",
      "What concerns did employees raise about accounting practices?",
      "Who was involved in the California energy trading?",
      "What did executives know about the Raptor transactions?",
  ]

  st.markdown("**Try an example:**")
  for ex in examples:
      if st.button(ex, key=ex):
          st.session_state["q"] = ex

  question = st.text_input("Ask your company anything...", value=st.session_state.get("q", ""))

  if question:
      with st.spinner("Searching organizational memory..."):
          try:
              resp = requests.post(API_URL, json={"question": question}, timeout=35).json()
              st.markdown("### Answer")
              st.markdown(resp["answer"])
              if resp.get("sources"):
                  with st.expander(f"📧 Source Emails ({len(resp['sources'])})"):
                      for i, s in enumerate(resp["sources"], 1):
                          st.markdown(f"**Source {i}**")
                          st.code(s["text"], language=None)
          except Exception as e:
              st.error(f"Error: {e}")

  Run locally:

  API_URL=https://<api-id>.execute-api.us-east-1.amazonaws.com/ask streamlit run frontend/app.py

  Verification: Open in browser, type a question, see answer + sources.

  ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

  Task 10: Host Frontend on AWS (Person 3, Hour 3–4)

  Objective: Get the Streamlit app running on AWS infrastructure.

  Option A — EC2 (fastest):

  1. Launch a t3.micro instance with Amazon Linux 2023
  2. SSH in, install Python, pip install deps, clone repo
  3. Run Streamlit on port 8501
  4. Open security group port 8501
  5. Access via http://<ec2-public-ip>:8501

  Option B — Amplify (more AWS points):

  1. Push repo to GitHub
  2. Create Amplify app connected to the repo
  3. Configure build to install Python + Streamlit
  4. Deploy

  Recommendation: Use Option A for speed. Mention Option B in the architecture slide as the "production path."

  ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

  Task 11: Integration Testing (Everyone, Hour 4–4.5)

  Objective: End-to-end verification that the full pipeline works.

  Test checklist:

  - [ ] Emails are in S3
  - [ ] Knowledge Base sync is complete
  - [ ] Bedrock Agent returns answers in console
  - [ ] Lambda returns correct JSON via direct invoke
  - [ ] API Gateway returns correct JSON via curl
  - [ ] Streamlit displays answer and source citations
  - [ ] All 4 example questions produce good answers
  - [ ] Error states handled (empty question, timeout)

  ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

  Task 12: Presentation & Demo (Person 3 leads, Everyone, Hour 4.5–5+)

  Objective: Prepare a compelling 3-5 minute demo.

  Slides (4 max):

  ┌───────┬─────────────────────────────────────────────────────────────────────────────────────────────────────────────
  ─────────┐
  │ Slide │ Content
                                                                                                                │
  ├───────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────
  ─────────┤
  │ 1     │ **The Problem** — Institutional amnesia. When people leave, knowledge leaves. Wikis fail because nobody
  writes docs. │
  │ 2     │ **The Solution** — Passive capture + reasoning extraction. No documentation required.
                                  │
  │ 3     │ **Architecture** — Diagram showing all 11 AWS services.
                                                                │
  │ 4     │ **Live Demo** — Switch to the app.
                                                                                     │
  └───────┴─────────────────────────────────────────────────────────────────────────────────────────────────────────────
  ─────────┘

  Demo Script (3 minutes):

  1. (30s) State the problem: "Every company slowly forgets itself."
  2. (15s) Show the search bar: "This is organizational memory for Enron."
  3. (60s) Ask first question live: "Why did Enron use special purpose entities?" — show the answer AND the source
  emails.
  4. (30s) Ask second question: "What concerns did employees raise about accounting?" — show reasoning extraction.
  5. (15s) Highlight: "These answers come from actual emails. Nobody wrote documentation. The system extracted the
  reasoning automatically."
  6. (30s) Close: "Now imagine this for your company's Slack, email, and meetings. No more institutional amnesia."

  ⚠️ Record a backup video of the demo working in case of live demo failure.

  ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

  Timeline

  ┌────────────┬───────────────────────────────────────────┬────────────────────────────────────────┬───────────────────
  ─────────────────────┐
  │ Time       │ Person 1 (Data/Infra)                     │ Person 2 (Backend)                     │ Person 3
  (Frontend/Demo)               │
  ├────────────┼───────────────────────────────────────────┼────────────────────────────────────────┼───────────────────
  ─────────────────────┤
  │ 0:00–0:30  │ Prerequisites check                       │ Prerequisites check                    │ Prerequisites
  check                    │
  │ 0:30–1:30  │ **Task 1**: Parse emails                  │ **Task 6**: Lambda function            │ **Task 9**:
  Streamlit skeleton         │
  │ 1:30–2:00  │ **Task 2**: Upload to S3                  │ Task 6 continued                       │ Task 9 continued
                         │
  │ 2:00–2:30  │ **Task 3**: Create OpenSearch (then wait) │ Task 6: test with mock data            │ Task 9: wire up
  API calls              │
  │ 2:30–3:30  │ **Task 4**: Create KB + start sync        │ **Task 7**: API Gateway                │ Task 9: polish UI
                        │
  │ 3:30–4:00  │ **Task 5**: Create Bedrock Agent          │ **Task 8**: CloudWatch                 │ **Task 10**: Host
  on AWS               │
  │ 4:00–4:30  │ **Task 11**: Integration testing (all)    │ **Task 11**: Integration testing (all) │ **Task 11**:
  Integration testing (all) │
  │ 4:30–5:00+ │ **Task 12**: Demo prep (all)              │ **Task 12**: Demo prep (all)           │ **Task 12**:
  Slides + demo script      │
  └────────────┴───────────────────────────────────────────┴────────────────────────────────────────┴───────────────────
  ─────────────────────┘

  ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

  Known Risks & Mitigations

  ┌───────────────────────────────────────────────┬─────────────────────────────────┬───────────────────────────────────
  ──────────────────────────────┐
  │ Risk                                          │ Impact                          │ Mitigation
                                                        │
  ├───────────────────────────────────────────────┼─────────────────────────────────┼───────────────────────────────────
  ──────────────────────────────┤
  │ OpenSearch collection takes 20+ min to create │ Blocks KB creation              │ Start Task 3 ASAP, work on other
  tasks while waiting            │
  │ KB sync takes 60+ min for 50k docs            │ No answers until sync completes │ Start with 20k emails. Scale up if
  time allows                  │
  │ Bedrock rate limiting during queries          │ Slow/failed demo                │ Add retry logic in Lambda. Use
  Haiku as fallback model          │
  │ Live demo fails                               │ Embarrassing                    │ Record backup video before
  presenting                           │
  │ Enron CSV parsing edge cases                  │ Missing/corrupt emails          │ Drop bad rows, don't try to fix
  them                            │
  │ API Gateway CORS issues                       │ Frontend can't call backend     │ Test CORS with curl early. Use
  `--cors-configuration` on create │
  └───────────────────────────────────────────────┴─────────────────────────────────┴───────────────────────────────────
  ──────────────────────────────┘

  ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

  Cost Estimate (Hackathon Day)

  ┌──────────────────────────────────────┬──────────────────┐
  │ Service                              │ Estimated Cost   │
  ├──────────────────────────────────────┼──────────────────┤
  │ S3 (50k small files)                 │ < $0.01          │
  │ OpenSearch Serverless (min 2 OCU)    │ ~$7 for 12 hours │
  │ Bedrock Titan Embeddings (50k docs)  │ ~$2-5            │
  │ Bedrock Claude Sonnet (demo queries) │ ~$1-3            │
  │ Lambda + API Gateway                 │ < $0.01          │
  │ EC2 t3.micro (frontend)              │ < $0.50          │
  │ **Total**                            │ **~$10-16**      │
  └──────────────────────────────────────┴──────────────────┘

  ⚠️ Delete OpenSearch Serverless collection after the hackathon — it charges per hour.

  ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

  Cleanup After Hackathon

  # Delete OpenSearch collection (biggest cost)
  aws opensearchserverless delete-collection --id <collection-id>

  # Delete S3 bucket
  aws s3 rb s3://enron-org-memory --force

  # Delete Lambda
  aws lambda delete-function --function-name enron-query

  # Delete API Gateway
  aws apigatewayv2 delete-api --api-id <api-id>

  # Delete Bedrock KB and Agent via console

  # Terminate EC2 instance if used
  aws ec2 terminate-instances --instance-ids <instance-id>