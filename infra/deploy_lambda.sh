#!/usr/bin/env bash
# Packages backend/lambda_function.py into a zip and creates or updates the
# enron-query Lambda function. Idempotent: running a second time updates
# code + environment variables.
#
# Required environment:
#   LAMBDA_ROLE_ARN     Output of infra/iam_lambda.sh
#   KB_ID               Bedrock Knowledge Base ID (skip if USE_MOCK=1)
# Optional:
#   FUNCTION_NAME       default: enron-query
#   AWS_REGION          default: us-west-2
#   MODEL_ID            default: anthropic.claude-3-sonnet-20240229-v1:0
#   AGENT_ID / AGENT_ALIAS_ID  switches Lambda to Option B (agent invocation)
#   USE_MOCK            "1" to deploy in mock mode
#
# Usage:
#   source infra/iam_lambda.sh
#   KB_ID=XXXXXXXXXX bash infra/deploy_lambda.sh

set -euo pipefail

FUNCTION_NAME="${FUNCTION_NAME:-enron-query}"
REGION="${AWS_REGION:-us-west-2}"
MODEL_ID="${MODEL_ID:-us.amazon.nova-pro-v1:0}"
USE_MOCK="${USE_MOCK:-0}"
KB_ID="${KB_ID:-}"
AGENT_ID="${AGENT_ID:-}"
AGENT_ALIAS_ID="${AGENT_ALIAS_ID:-}"
TIMEOUT="${TIMEOUT:-60}"
MEMORY="${MEMORY:-512}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND_DIR="$REPO_ROOT/backend"
ZIP_PATH="$BACKEND_DIR/function.zip"

if command -v aws >/dev/null 2>&1; then
  AWS_CLI="aws"
elif command -v aws.exe >/dev/null 2>&1; then
  AWS_CLI="aws.exe"
else
  echo "AWS CLI not found." >&2
  exit 1
fi

if [ -z "${LAMBDA_ROLE_ARN:-}" ]; then
  echo "LAMBDA_ROLE_ARN is not set. Run: source infra/iam_lambda.sh" >&2
  exit 1
fi

if [ "$USE_MOCK" != "1" ] && [ -z "$KB_ID" ] && { [ -z "$AGENT_ID" ] || [ -z "$AGENT_ALIAS_ID" ]; }; then
  echo "Warning: no KB_ID or AGENT_ID/AGENT_ALIAS_ID supplied. Deploying in mock mode." >&2
  USE_MOCK=1
fi

echo "Packaging $ZIP_PATH"
rm -f "$ZIP_PATH"
(cd "$BACKEND_DIR" && zip -q -j "$ZIP_PATH" lambda_function.py)

ENV_VARS="MODEL_ID=$MODEL_ID"
[ -n "$KB_ID" ]          && ENV_VARS="$ENV_VARS,KB_ID=$KB_ID"
[ -n "$AGENT_ID" ]       && ENV_VARS="$ENV_VARS,AGENT_ID=$AGENT_ID"
[ -n "$AGENT_ALIAS_ID" ] && ENV_VARS="$ENV_VARS,AGENT_ALIAS_ID=$AGENT_ALIAS_ID"
[ "$USE_MOCK" = "1" ]    && ENV_VARS="$ENV_VARS,USE_MOCK=1"

if "$AWS_CLI" lambda get-function --region "$REGION" --function-name "$FUNCTION_NAME" >/dev/null 2>&1; then
  echo "Updating function code: $FUNCTION_NAME"
  "$AWS_CLI" lambda update-function-code \
    --region "$REGION" \
    --function-name "$FUNCTION_NAME" \
    --zip-file "fileb://$ZIP_PATH" >/dev/null

  "$AWS_CLI" lambda wait function-updated \
    --region "$REGION" --function-name "$FUNCTION_NAME"

  echo "Updating function configuration"
  "$AWS_CLI" lambda update-function-configuration \
    --region "$REGION" \
    --function-name "$FUNCTION_NAME" \
    --runtime python3.11 \
    --handler lambda_function.handler \
    --role "$LAMBDA_ROLE_ARN" \
    --timeout "$TIMEOUT" \
    --memory-size "$MEMORY" \
    --environment "Variables={$ENV_VARS}" >/dev/null
else
  echo "Creating function: $FUNCTION_NAME"
  "$AWS_CLI" lambda create-function \
    --region "$REGION" \
    --function-name "$FUNCTION_NAME" \
    --runtime python3.11 \
    --handler lambda_function.handler \
    --role "$LAMBDA_ROLE_ARN" \
    --timeout "$TIMEOUT" \
    --memory-size "$MEMORY" \
    --zip-file "fileb://$ZIP_PATH" \
    --environment "Variables={$ENV_VARS}" >/dev/null
fi

"$AWS_CLI" lambda wait function-updated \
  --region "$REGION" --function-name "$FUNCTION_NAME"

FUNCTION_ARN=$("$AWS_CLI" lambda get-function \
  --region "$REGION" \
  --function-name "$FUNCTION_NAME" \
  --query 'Configuration.FunctionArn' --output text)

export FUNCTION_NAME
export FUNCTION_ARN
echo "FUNCTION_NAME=$FUNCTION_NAME"
echo "FUNCTION_ARN=$FUNCTION_ARN"
