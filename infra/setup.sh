#!/usr/bin/env bash
set -euo pipefail

REGION="us-west-2"
BUCKET="enron-org-memory-data"

if command -v aws >/dev/null 2>&1; then
  AWS_CLI="aws"
elif command -v aws.exe >/dev/null 2>&1; then
  AWS_CLI="aws.exe"
else
  echo "AWS CLI not found. Install AWS CLI and ensure 'aws' or 'aws.exe' is on PATH." >&2
  exit 1
fi

if "$AWS_CLI" s3api head-bucket --bucket "$BUCKET" >/dev/null 2>&1; then
  CURRENT_REGION=$("$AWS_CLI" s3api get-bucket-location --bucket "$BUCKET" --query 'LocationConstraint' --output text)
  if [ "$CURRENT_REGION" = "None" ] || [ "$CURRENT_REGION" = "null" ]; then
    CURRENT_REGION="us-east-1"
  fi

  if [ "$CURRENT_REGION" != "$REGION" ]; then
    echo "Bucket s3://$BUCKET already exists in $CURRENT_REGION. Use that region or choose a new bucket name." >&2
    exit 1
  fi
else
  if [ "$REGION" = "us-east-1" ]; then
    "$AWS_CLI" s3api create-bucket --bucket "$BUCKET" --region "$REGION"
  else
    "$AWS_CLI" s3api create-bucket --bucket "$BUCKET" --region "$REGION" --create-bucket-configuration "LocationConstraint=$REGION"
  fi
fi

"$AWS_CLI" s3api put-public-access-block --bucket "$BUCKET" --public-access-block-configuration "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"

echo "Bucket s3://$BUCKET is ready in $REGION"
