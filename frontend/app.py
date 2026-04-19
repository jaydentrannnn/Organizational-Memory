"""Streamlit frontend for Organizational Memory — Enron email Q&A."""

import os

import requests
import streamlit as st

API_URL: str = os.environ.get("API_URL", "")

EXAMPLES: list[str] = [
    "Why did Enron use special purpose entities?",
    "What concerns did employees raise about accounting practices?",
    "Who was involved in the California energy trading?",
    "What did executives know about the Raptor transactions?",
]

st.set_page_config(page_title="Organizational Memory", page_icon="🧠")
st.title("🧠 Organizational Memory")
st.caption("Ask natural-language questions about the Enron email corpus — powered by Amazon Bedrock")

# --- example question buttons ---
st.markdown("**Try an example:**")
cols = st.columns(2)
for i, ex in enumerate(EXAMPLES):
    if cols[i % 2].button(ex, key=f"ex{i}", use_container_width=True):
        st.session_state["question"] = ex

question: str = st.text_input(
    "Your question",
    value=st.session_state.get("question", ""),
    placeholder="e.g. Why did Enron use special purpose entities?",
)


def call_api(q: str) -> dict:
    """POST the question to the backend and return parsed JSON."""
    resp = requests.post(API_URL, json={"question": q}, timeout=35)
    resp.raise_for_status()
    return resp.json()


if st.button("Ask", type="primary", disabled=not question.strip()):
    if not API_URL:
        st.error("Set the `API_URL` env var, e.g. `API_URL=https://xxx.execute-api.us-east-1.amazonaws.com/ask streamlit run frontend/app.py`")
    else:
        with st.spinner("Searching organizational memory…"):
            try:
                data = call_api(question.strip())
            except requests.exceptions.Timeout:
                st.error("Request timed out — the backend may be under heavy load.")
                st.stop()
            except requests.exceptions.ConnectionError:
                st.error("Cannot reach the API. Check that API_URL is correct and the backend is running.")
                st.stop()
            except requests.exceptions.HTTPError as exc:
                code = exc.response.status_code if exc.response is not None else 0
                if code == 429:
                    st.warning("Rate limited — wait a moment and retry.")
                else:
                    try:
                        body = exc.response.json()
                        st.error(body.get("error", f"Server error ({code})"))
                    except Exception:
                        st.error(f"Server error ({code}): {exc.response.text[:300]}")
                st.stop()
            except Exception as exc:
                st.error(f"Unexpected error: {exc}")
                st.stop()

        st.markdown("### Answer")
        st.markdown(data.get("answer", "_No answer returned._"))

        sources: list[dict] = data.get("sources", [])
        if sources:
            with st.expander(f"📄 Sources ({len(sources)})"):
                for j, src in enumerate(sources, 1):
                    st.markdown(f"**Source {j}**")
                    st.text(src.get("text", ""))
                    loc = src.get("location")
                    if loc:
                        st.caption(str(loc))
                    if j < len(sources):
                        st.divider()
