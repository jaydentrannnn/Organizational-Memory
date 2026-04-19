#!/usr/bin/env bash
# Creates (idempotently) the IAM role that the Enron organizational-memory
# Lambda assumes. Attaches an inline policy granting:
#   - Bedrock KB / agent invocation (retrieve, retrieve-and-generate, invoke)
#   - CloudWatch Logs write
#
# Exports the role ARN so deploy_lambda.sh can consume it.
#
# Usage:
#   bash infra/iam_lambda.sh
#   # or source to capture LAMBDA_ROLE_ARN in the current shell:
#   source infra/iam_lambda.sh

set -euo pipefail

ROLE_NAME="${ROLE_NAME:-enron-query-lambda-role}"
POLICY_NAME="${POLICY_NAME:-enron-query-lambda-policy}"
REGION="${AWS_REGION:-us-east-1}"

if command -v aws >/dev/null 2>&1; then
  AWS_CLI="aws"
elif command -v aws.exe >/dev/null 2>&1; then
  AWS_CLI="aws.exe"
else
  echo "AWS CLI not found. Install AWS CLI and ensure 'aws' is on PATH." >&2
  exit 1
fi

TRUST_POLICY=$(cat <<'JSON'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {"Service": "lambda.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }
  ]
}
JSON
)

INLINE_POLICY=$(cat <<'JSON'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "BedrockInvoke",
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream",
        "bedrock:Retrieve",
        "bedrock:RetrieveAndGenerate",
        "bedrock:InvokeAgent"
      ],
      "Resource": "*"
    },
    {
      "Sid": "CloudWatchLogs",
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "*"
    }
  ]
}
JSON
)

if "$AWS_CLI" iam get-role --role-name "$ROLE_NAME" >/dev/null 2>&1; then
  echo "IAM role $ROLE_NAME already exists; refreshing trust + inline policy."
  "$AWS_CLI" iam update-assume-role-policy \
    --role-name "$ROLE_NAME" \
    --policy-document "$TRUST_POLICY" >/dev/null
else
  echo "Creating IAM role $ROLE_NAME"
  "$AWS_CLI" iam create-role \
    --role-name "$ROLE_NAME" \
    --assume-role-policy-document "$TRUST_POLICY" \
    --description "Execution role for enron-query Lambda" >/dev/null
fi

"$AWS_CLI" iam put-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-name "$POLICY_NAME" \
  --policy-document "$INLINE_POLICY"

LAMBDA_ROLE_ARN=$("$AWS_CLI" iam get-role --role-name "$ROLE_NAME" --query 'Role.Arn' --output text)
export LAMBDA_ROLE_ARN
export AWS_REGION="$REGION"

echo "LAMBDA_ROLE_ARN=$LAMBDA_ROLE_ARN"
