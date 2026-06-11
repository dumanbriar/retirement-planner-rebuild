#!/usr/bin/env bash
# Deploy backend/ to Railway, handling every Railway token flavor:
#   - personal account token  (Authorization: Bearer; `me` works)
#   - team/workspace token    (Authorization: Bearer; `me` fails, projects work)
#   - project token           (Project-Access-Token header; projectToken works)
# Prints a diagnostic for whichever flavor it detects, then deploys via the
# Railway CLI and emits the public domain as $GITHUB_OUTPUT backend_url.
set -uo pipefail

TOKEN="${RAILWAY_DEPLOY_TOKEN:?RAILWAY_DEPLOY_TOKEN required}"
PROJECT_NAME="${RAILWAY_PROJECT_NAME:-horizon-retirement-engine}"
SERVICE_NAME="${RAILWAY_SERVICE_NAME:-backend}"

gql_bearer() {
  curl -s -X POST "$1/graphql/v2" \
    -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
    -d "$2"
}
gql_project() {
  curl -s -X POST "$1/graphql/v2" \
    -H "Project-Access-Token: $TOKEN" -H "Content-Type: application/json" \
    -d "$2"
}

ENDPOINT=""
MODE=""
for EP in https://backboard.railway.com https://backboard.railway.app; do
  echo "== probing $EP =="
  ME=$(gql_bearer "$EP" '{"query":"query { me { id name email } }"}')
  echo "me: $ME"
  if echo "$ME" | grep -q '"id"'; then ENDPOINT="$EP"; MODE="account"; break; fi
  PROJECTS=$(gql_bearer "$EP" '{"query":"query { projects { edges { node { id name } } } }"}')
  echo "projects: $PROJECTS"
  if echo "$PROJECTS" | grep -q '"edges"'; then ENDPOINT="$EP"; MODE="team"; break; fi
  PT=$(gql_project "$EP" '{"query":"query { projectToken { projectId environmentId } }"}')
  echo "projectToken: $PT"
  if echo "$PT" | grep -q '"projectId"'; then ENDPOINT="$EP"; MODE="project"; break; fi
done

if [ -z "$MODE" ]; then
  echo "::error::Railway token was rejected as account, team, AND project token by both API hosts. The token is likely invalid, revoked, or for a different Railway environment. See probe output above."
  exit 1
fi
echo "== token accepted as: $MODE token via $ENDPOINT =="

if [ "$MODE" = "project" ]; then
  # project token: CLI works directly with RAILWAY_TOKEN
  cd "$(dirname "$0")/../backend"
  export RAILWAY_TOKEN="$TOKEN"
  railway up -c || { echo "::error::railway up failed"; exit 1; }
  DOMAIN_OUT=$(railway domain --json 2>/dev/null || railway domain 2>/dev/null || true)
  echo "domain output: $DOMAIN_OUT"
  URL=$(echo "$DOMAIN_OUT" | grep -oE '[a-zA-Z0-9.-]+\.up\.railway\.app' | head -1)
  [ -n "$URL" ] || { echo "::error::no public domain found"; exit 1; }
  echo "backend_url=https://$URL" >> "${GITHUB_OUTPUT:-/dev/stdout}"
  echo "Backend URL: https://$URL"
else
  # account/team token: GraphQL for project/service/domain, CLI for upload
  export RAILWAY_ENDPOINT="$ENDPOINT/graphql/v2"
  export RAILWAY_PROJECT_NAME="$PROJECT_NAME" RAILWAY_SERVICE_NAME="$SERVICE_NAME"
  exec python3 "$(dirname "$0")/deploy_railway.py"
fi
