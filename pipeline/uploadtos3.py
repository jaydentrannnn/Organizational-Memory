import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import boto3
from botocore.config import Config

BUCKET = "enron-org-memory-data"
PREFIX = "emails/"


def list_existing_keys(client, bucket: str, prefix: str) -> set[str]:
    existing = set()
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            existing.add(obj["Key"])
    print(f"Found {len(existing):,} existing objects in s3://{bucket}/{prefix}")
    return existing


def upload_one(client, bucket: str, local: Path, key: str) -> None:
    client.upload_file(str(local), bucket, key)


def run(local_root: Path, bucket: str, prefix: str) -> None:
    client = boto3.client(
        "s3",
        config=Config(max_pool_connections=64),
    )

    existing_keys = list_existing_keys(client, bucket, prefix)

    all_files = list(local_root.rglob("*.txt"))
    tasks = []
    for local in all_files:
        rel = local.relative_to(local_root)
        key = prefix + rel.as_posix()
        if key not in existing_keys:
            tasks.append((local, key))

    total = len(tasks)
    skipped = len(all_files) - total
    print(f"Files to upload: {total:,} | Already on S3 (skipped): {skipped:,}")

    if total == 0:
        print("Nothing to upload.")
        return

    uploaded = 0
    start_time = time.time()

    with ThreadPoolExecutor(max_workers=64) as executor:
        futures = {executor.submit(upload_one, client, bucket, local, key): key for local, key in tasks}
        for future in as_completed(futures):
            future.result()
            uploaded += 1
            if uploaded % 1000 == 0:
                elapsed = time.time() - start_time
                rate = uploaded / elapsed if elapsed > 0 else 0
                remaining = (total - uploaded) / rate if rate > 0 else 0
                print(f"Uploaded {uploaded:,}/{total:,} | {rate:.0f} files/s | ETA {remaining:.0f}s")

    elapsed = time.time() - start_time
    print(f"\nDone. Uploaded {uploaded:,} files in {elapsed:.1f}s ({uploaded/elapsed:.0f} files/s)")


if __name__ == "__main__":
    run(
        local_root=Path("data/parsed"),
        bucket=BUCKET,
        prefix=PREFIX,
    )
