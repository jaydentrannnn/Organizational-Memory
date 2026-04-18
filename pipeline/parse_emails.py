import email
import hashlib
import json
import time
from email.message import Message
from pathlib import Path

import pandas as pd


def extract_body(msg: Message) -> str:
    if msg.is_multipart():
        parts = []
        for part in msg.walk():
            if part.get_content_type() == "text/plain" and not part.get_filename():
                payload = part.get_payload(decode=False)
                if isinstance(payload, bytes):
                    payload = payload.decode("utf-8", errors="replace")
                if payload:
                    parts.append(payload)
        return "\n".join(parts)
    payload = msg.get_payload(decode=False)
    if isinstance(payload, bytes):
        payload = payload.decode("utf-8", errors="replace")
    return payload or ""


def parse_message(raw: str) -> dict | None:
    try:
        msg = email.message_from_string(raw)
        body = extract_body(msg).strip()
        if not body:
            return None
        return {
            "from": msg.get("From", ""),
            "to": msg.get("To", ""),
            "date": msg.get("Date", ""),
            "subject": msg.get("Subject", ""),
            "body": body,
        }
    except Exception:
        return None


def write_email(out_dir: Path, idx: int, parsed: dict) -> None:
    shard_dir = out_dir / str(idx // 5000)
    shard_dir.mkdir(parents=True, exist_ok=True)
    content = (
        f"From: {parsed['from']}\n"
        f"To: {parsed['to']}\n"
        f"Date: {parsed['date']}\n"
        f"Subject: {parsed['subject']}\n"
        f"\n"
        f"{parsed['body']}"
    )
    (shard_dir / f"email_{idx}.txt").write_text(content, encoding="utf-8")


def _load_progress(progress_file: Path) -> dict:
    if progress_file.exists():
        try:
            return json.loads(progress_file.read_text())
        except Exception:
            pass
    return {"last_row": 0, "written": 0, "dedup_skipped": 0, "errors": 0}


def _save_progress(progress_file: Path, state: dict) -> None:
    progress_file.write_text(json.dumps(state, indent=2))


def run(csv_path: Path, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    progress_file = out_dir / ".progress.json"
    state = _load_progress(progress_file)

    resume_row = state["last_row"]
    if resume_row:
        print(f"Resuming from row {resume_row} (written={state['written']}, dedup_skipped={state['dedup_skipped']})")

    seen_hashes: set[bytes] = set()
    global_idx = state["written"]
    rows_processed = resume_row
    start_time = time.time()

    for chunk in pd.read_csv(
        csv_path,
        chunksize=10_000,
        dtype=str,
        keep_default_na=False,
        skiprows=range(1, resume_row + 1) if resume_row else None,
    ):
        for _, row in chunk.iterrows():
            rows_processed += 1
            parsed = parse_message(row.get("message", ""))
            if parsed is None:
                state["errors"] += 1
                continue

            body_hash = hashlib.md5(parsed["body"].encode()).digest()
            if body_hash in seen_hashes:
                state["dedup_skipped"] += 1
                continue
            seen_hashes.add(body_hash)

            write_email(out_dir, global_idx, parsed)
            global_idx += 1
            state["written"] = global_idx

        state["last_row"] = rows_processed
        _save_progress(progress_file, state)

        elapsed = time.time() - start_time
        rate = rows_processed / elapsed if elapsed > 0 else 0
        print(
            f"Rows: {rows_processed:,} | Written: {state['written']:,} | "
            f"Dedup: {state['dedup_skipped']:,} | Errors: {state['errors']} | "
            f"{rate:.0f} rows/s"
        )

    _save_progress(progress_file, state)
    print(f"\nDone. Written={state['written']:,}, Dedup={state['dedup_skipped']:,}, Errors={state['errors']}")


if __name__ == "__main__":
    run(
        csv_path=Path("data/raw/emails.csv"),
        out_dir=Path("data/parsed"),
    )
