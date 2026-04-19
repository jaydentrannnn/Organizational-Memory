"""Lambda handler for Enron Organizational Memory backend.

Receives API Gateway HTTP API events of shape:
    {"body": "{\"question\": \"...\"}"}

and returns:
    {"statusCode": 200, "headers": {...}, "body": "{\"answer\": ..., \"sources\": [...]}"}

Routing logic:
- If USE_MOCK=1 (or KB_ID is unset and no agent configured), return a deterministic
  mocked response so Person 3 can integrate against a real endpoint before Person 1
  finishes the Knowledge Base sync.
- If AGENT_ID and AGENT_ALIAS_ID are set, invoke the Bedrock Agent (Option B in the
  refined plan).
- Otherwise call bedrock-agent-runtime retrieve_and_generate with the Knowledge Base
  (Option A, default).

Environment variables:
    AWS_REGION         e.g. us-east-1 (Lambda sets this automatically)
    KB_ID              Bedrock Knowledge Base ID (Option A)
    MODEL_ID           foundation model id for generation. Default: Claude 3 Sonnet.
    AGENT_ID           Bedrock Agent ID (Option B, optional)
    AGENT_ALIAS_ID     Bedrock Agent alias ID (Option B, optional)
    USE_MOCK           "1" to force mock responses (useful for local/dev)
    MAX_SNIPPET_CHARS  Max chars per source snippet (default 500)
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, ReadTimeoutError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

REGION = os.environ.get("AWS_REGION", "us-east-1")
KB_ID = os.environ.get("KB_ID", "").strip()
MODEL_ID = os.environ.get(
    "MODEL_ID", "anthropic.claude-3-sonnet-20240229-v1:0"
).strip()
AGENT_ID = os.environ.get("AGENT_ID", "").strip()
AGENT_ALIAS_ID = os.environ.get("AGENT_ALIAS_ID", "").strip()
USE_MOCK = os.environ.get("USE_MOCK", "").strip() == "1"
MAX_SNIPPET_CHARS = int(os.environ.get("MAX_SNIPPET_CHARS", "500"))

# Reuse one client across warm invocations. Read/connect timeouts must stay
# under the 30s Lambda budget so we can return a clean 504 instead of a
# hard Lambda timeout.
_BOTO_CONFIG = Config(
    region_name=REGION,
    read_timeout=25,
    connect_timeout=5,
    retries={"max_attempts": 2, "mode": "standard"},
)

_runtime_client = None
_agent_client = None


def _kb_client():
    global _runtime_client
    if _runtime_client is None:
        _runtime_client = boto3.client("bedrock-agent-runtime", config=_BOTO_CONFIG)
    return _runtime_client


def _agent_runtime_client():
    global _agent_client
    if _agent_client is None:
        _agent_client = boto3.client("bedrock-agent-runtime", config=_BOTO_CONFIG)
    return _agent_client


def _cors_headers() -> dict[str, str]:
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST,OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
        "Content-Type": "application/json",
    }


def _response(status: int, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status,
        "headers": _cors_headers(),
        "body": json.dumps(payload),
    }


def _parse_question(event: dict[str, Any]) -> str | None:
    raw_body = event.get("body")
    if isinstance(raw_body, (bytes, bytearray)):
        raw_body = raw_body.decode("utf-8", errors="replace")
    if not raw_body:
        # Allow direct invocation shape: {"question": "..."}
        q = event.get("question")
        return q.strip() if isinstance(q, str) else None
    try:
        body = json.loads(raw_body)
    except json.JSONDecodeError:
        return None
    q = body.get("question") if isinstance(body, dict) else None
    return q.strip() if isinstance(q, str) else None


def _truncate(text: str) -> str:
    if not isinstance(text, str):
        return ""
    return text if len(text) <= MAX_SNIPPET_CHARS else text[:MAX_SNIPPET_CHARS]


def _citations_from_kb(resp: dict[str, Any]) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    for cite in resp.get("citations", []) or []:
        for ref in cite.get("retrievedReferences", []) or []:
            text = (ref.get("content") or {}).get("text", "")
            sources.append(
                {
                    "text": _truncate(text),
                    "location": ref.get("location", {}) or {},
                }
            )
    return sources


def _model_arn() -> str:
    return f"arn:aws:bedrock:{REGION}::foundation-model/{MODEL_ID}"


def _mock_answer(question: str) -> dict[str, Any]:
    return {
        "answer": (
            "[MOCK] You asked: "
            f"{question!r}. Backend is running in mock mode because KB_ID is "
            "unset or USE_MOCK=1. Wire up the Knowledge Base to get real answers."
        ),
        "sources": [
            {
                "text": (
                    "From: sample@enron.com\n"
                    "To: team@enron.com\n"
                    "Subject: Mock source\n\n"
                    "This is a placeholder snippet returned by the mock backend."
                ),
                "location": {"s3Location": {"uri": "s3://mock/emails/email_0.txt"}},
            }
        ],
    }


def _query_knowledge_base(question: str) -> dict[str, Any]:
    resp = _kb_client().retrieve_and_generate(
        input={"text": question},
        retrieveAndGenerateConfiguration={
            "type": "KNOWLEDGE_BASE",
            "knowledgeBaseConfiguration": {
                "knowledgeBaseId": KB_ID,
                "modelArn": _model_arn(),
            },
        },
    )
    answer = (resp.get("output") or {}).get("text", "")
    return {"answer": answer, "sources": _citations_from_kb(resp)}


def _query_agent(question: str) -> dict[str, Any]:
    """Invoke a prepared Bedrock Agent (Option B) and assemble a streamed response."""
    session_id = str(uuid.uuid4())
    resp = _agent_runtime_client().invoke_agent(
        agentId=AGENT_ID,
        agentAliasId=AGENT_ALIAS_ID,
        sessionId=session_id,
        inputText=question,
    )
    answer_parts: list[str] = []
    sources: list[dict[str, Any]] = []
    for event in resp.get("completion", []) or []:
        chunk = event.get("chunk") or {}
        data = chunk.get("bytes")
        if data:
            answer_parts.append(data.decode("utf-8", errors="replace"))
        attribution = chunk.get("attribution") or {}
        for cite in attribution.get("citations", []) or []:
            for ref in cite.get("retrievedReferences", []) or []:
                sources.append(
                    {
                        "text": _truncate((ref.get("content") or {}).get("text", "")),
                        "location": ref.get("location", {}) or {},
                    }
                )
    return {"answer": "".join(answer_parts), "sources": sources}


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    request_id = getattr(context, "aws_request_id", str(uuid.uuid4()))
    started = time.perf_counter()

    method = (
        event.get("requestContext", {}).get("http", {}).get("method")
        or event.get("httpMethod")
        or ""
    ).upper()
    if method == "OPTIONS":
        return _response(204, {})

    question = _parse_question(event)
    logger.info(
        "request_id=%s method=%s has_question=%s",
        request_id,
        method or "DIRECT",
        bool(question),
    )

    if not question:
        return _response(400, {"error": "question is required"})

    try:
        if USE_MOCK or (not KB_ID and not (AGENT_ID and AGENT_ALIAS_ID)):
            logger.info("request_id=%s path=mock", request_id)
            payload = _mock_answer(question)
        elif AGENT_ID and AGENT_ALIAS_ID:
            logger.info(
                "request_id=%s path=agent agent_id=%s alias=%s",
                request_id,
                AGENT_ID,
                AGENT_ALIAS_ID,
            )
            payload = _query_agent(question)
        else:
            logger.info("request_id=%s path=kb kb_id=%s", request_id, KB_ID)
            payload = _query_knowledge_base(question)

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        logger.info(
            "request_id=%s status=200 sources=%d elapsed_ms=%d",
            request_id,
            len(payload.get("sources", [])),
            elapsed_ms,
        )
        return _response(200, payload)

    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        logger.exception("request_id=%s client_error code=%s", request_id, code)
        if code in {"ThrottlingException", "TooManyRequestsException"}:
            return _response(429, {"error": "rate limited, try again"})
        if code in {"AccessDeniedException", "UnauthorizedException"}:
            return _response(403, {"error": "bedrock access denied", "code": code})
        if code in {"ResourceNotFoundException", "ValidationException"}:
            return _response(400, {"error": exc.response["Error"].get("Message", code)})
        return _response(500, {"error": f"bedrock error: {code or 'unknown'}"})

    except ReadTimeoutError:
        logger.exception("request_id=%s timeout", request_id)
        return _response(504, {"error": "upstream timeout"})

    except Exception as exc:  # pragma: no cover - defensive catch-all
        logger.exception("request_id=%s unhandled_error", request_id)
        return _response(500, {"error": str(exc)})
