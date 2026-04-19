#!/usr/bin/env bash
# Creates (idempotently) an API Gateway HTTP API with:
#   POST /ask  ->  enron-query Lambda
#   CORS allowing POST/OPTIONS from any origin
#
# Usage:
#   source infra/iam_lambda.sh
#   bash infra/deploy_lambda.sh
#   bash infra/api_gateway.sh
#
# Prints the invoke URL as API_GATEWAY_ASK_URL on the final line.

set -euo pipefail

API_NAME="${API_NAME:-enron-memory-api}"
FUNCTION_NAME="${FUNCTION_NAME:-enron-query}"
REGION="${AWS_REGION:-us-east-1}"
ROUTE_KEY="${ROUTE_KEY:-POST /ask}"
STATEMENT_ID="${STATEMENT_ID:-apigateway-invoke}"

if command -v aws >/dev/null 2>&1; then
  AWS_CLI="aws"
elif command -v aws.exe >/dev/null 2>&1; then
  AWS_CLI="aws.exe"
else
  echo "AWS CLI not found." >&2
  exit 1
fi

ACCOUNT_ID=$("$AWS_CLI" sts get-caller-identity --query Account --output text)
FUNCTION_ARN=$("$AWS_CLI" lambda get-function \
  --region "$REGION" \
  --function-name "$FUNCTION_NAME" \
  --query 'Configuration.FunctionArn' --output text)

# Find existing API by name (idempotent).
API_ID=$("$AWS_CLI" apigatewayv2 get-apis \
  --region "$REGION" \
  --query "Items[?Name=='$API_NAME'] | [0].ApiId" \
  --output text 2>/dev/null || echo "None")

CORS_JSON='{"AllowOrigins":["*"],"AllowMethods":["POST","OPTIONS"],"AllowHeaders":["Content-Type","Authorization"]}'

if [ "$API_ID" = "None" ] || [ -z "$API_ID" ]; then
  echo "Creating HTTP API $API_NAME"
  API_ID=$("$AWS_CLI" apigatewayv2 create-api \
    --region "$REGION" \
    --name "$API_NAME" \
    --protocol-type HTTP \
    --cors-configuration "$CORS_JSON" \
    --query 'ApiId' --output text)
else
  echo "Reusing HTTP API $API_NAME ($API_ID); refreshing CORS."
  "$AWS_CLI" apigatewayv2 update-api \
    --region "$REGION" \
    --api-id "$API_ID" \
    --cors-configuration "$CORS_JSON" >/dev/null
fi

# Integration (AWS_PROXY to Lambda).
INTEGRATION_ID=$("$AWS_CLI" apigatewayv2 get-integrations \
  --region "$REGION" \
  --api-id "$API_ID" \
  --query "Items[?IntegrationUri=='$FUNCTION_ARN'] | [0].IntegrationId" \
  --output text 2>/dev/null || echo "None")

if [ "$INTEGRATION_ID" = "None" ] || [ -z "$INTEGRATION_ID" ]; then
  echo "Creating Lambda integration"
  INTEGRATION_ID=$("$AWS_CLI" apigatewayv2 create-integration \
    --region "$REGION" \
    --api-id "$API_ID" \
    --integration-type AWS_PROXY \
    --integration-uri "$FUNCTION_ARN" \
    --payload-format-version 2.0 \
    --query 'IntegrationId' --output text)
else
  echo "Reusing integration $INTEGRATION_ID"
fi

# Route.
ROUTE_ID=$("$AWS_CLI" apigatewayv2 get-routes \
  --region "$REGION" \
  --api-id "$API_ID" \
  --query "Items[?RouteKey=='$ROUTE_KEY'] | [0].RouteId" \
  --output text 2>/dev/null || echo "None")

TARGET="integrations/$INTEGRATION_ID"
if [ "$ROUTE_ID" = "None" ] || [ -z "$ROUTE_ID" ]; then
  echo "Creating route $ROUTE_KEY"
  "$AWS_CLI" apigatewayv2 create-route \
    --region "$REGION" \
    --api-id "$API_ID" \
    --route-key "$ROUTE_KEY" \
    --target "$TARGET" >/dev/null
else
  echo "Reusing route $ROUTE_ID; pointing at $TARGET"
  "$AWS_CLI" apigatewayv2 update-route \
    --region "$REGION" \
    --api-id "$API_ID" \
    --route-id "$ROUTE_ID" \
    --target "$TARGET" >/dev/null
fi

# $default stage with auto-deploy.
if ! "$AWS_CLI" apigatewayv2 get-stage \
    --region "$REGION" --api-id "$API_ID" --stage-name '$default' >/dev/null 2>&1; then
  echo "Creating \$default stage"
  "$AWS_CLI" apigatewayv2 create-stage \
    --region "$REGION" \
    --api-id "$API_ID" \
    --stage-name '$default' \
    --auto-deploy >/dev/null
fi

# Lambda resource-based permission for API Gateway to invoke the function.
SOURCE_ARN="arn:aws:execute-api:$REGION:$ACCOUNT_ID:$API_ID/*/*/ask"
if ! "$AWS_CLI" lambda get-policy \
    --region "$REGION" --function-name "$FUNCTION_NAME" 2>/dev/null \
    | grep -q "\"Sid\":\"$STATEMENT_ID\""; then
  echo "Granting API Gateway invoke permission on $FUNCTION_NAME"
  "$AWS_CLI" lambda add-permission \
    --region "$REGION" \
    --function-name "$FUNCTION_NAME" \
    --statement-id "$STATEMENT_ID" \
    --action lambda:InvokeFunction \
    --principal apigateway.amazonaws.com \
    --source-arn "$SOURCE_ARN" >/dev/null
else
  echo "Invoke permission already attached."
fi

API_ENDPOINT=$("$AWS_CLI" apigatewayv2 get-api \
  --region "$REGION" --api-id "$API_ID" \
  --query 'ApiEndpoint' --output text)

ASK_URL="$API_ENDPOINT/ask"
export API_GATEWAY_ASK_URL="$ASK_URL"

echo "API_ID=$API_ID"
echo "API_GATEWAY_ASK_URL=$ASK_URL"
echo
echo "Smoke test:"
echo "  curl -X POST $ASK_URL -H 'Content-Type: application/json' \\"
echo "    -d '{\"question\":\"What was the California energy crisis about?\"}'"
