#!/bin/bash
set -Eeuo pipefail

COMPOSE_FILE="docker-compose.local.yml"
COMPOSE="docker compose -f ${COMPOSE_FILE}"
LOG_PREFIX="[local-deploy-test]"

echo "${LOG_PREFIX} validating required files..."
if [[ ! -f ".env.dev" ]]; then
    echo "${LOG_PREFIX} ERROR: .env.dev is missing."
    exit 1
fi

echo "${LOG_PREFIX} validating compose config..."
${COMPOSE} config >/dev/null

echo "${LOG_PREFIX} stopping previous local stack (if any)..."
${COMPOSE} down --remove-orphans || true

echo "${LOG_PREFIX} building and starting local stack..."
${COMPOSE} up -d --build

echo "${LOG_PREFIX} waiting for web health..."
WEB_CONTAINER="$(${COMPOSE} ps -q web || true)"
if [[ -z "${WEB_CONTAINER}" ]]; then
    echo "${LOG_PREFIX} ERROR: web container id not found."
    ${COMPOSE} ps
    exit 1
fi

STATUS=""
for i in {1..40}; do
    STATUS="$(docker inspect --format='{{.State.Health.Status}}' \
        "${WEB_CONTAINER}" 2>/dev/null || echo unknown)"
    echo "${LOG_PREFIX} check ${i}: web=${STATUS}"
    if [[ "${STATUS}" == "healthy" ]]; then
        break
    fi
    sleep 3
done

if [[ "${STATUS}" != "healthy" ]]; then
    echo "${LOG_PREFIX} ERROR: web did not become healthy."
    ${COMPOSE} ps
    ${COMPOSE} logs --tail=100 web
    exit 1
fi

echo "${LOG_PREFIX} running HTTP smoke checks..."
curl -fsS "http://localhost:8000/health/" >/dev/null
curl -fsS "http://localhost:5173/" >/dev/null

echo "${LOG_PREFIX} container status:"
${COMPOSE} ps

echo "${LOG_PREFIX} SUCCESS: local deployment smoke test passed."
