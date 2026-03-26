#!/bin/sh
set -eu

DOMAIN="${DOMAIN:-}"
WARN_DAYS="${CERT_WARN_DAYS:-30}"
MODE="${1:-}"

if [ -z "$DOMAIN" ]; then
    echo "[certbot] ERROR: DOMAIN is not set."
    exit 1
fi

CERT_INFO="$(certbot certificates -d "$DOMAIN" 2>/dev/null || true)"

if [ -z "$CERT_INFO" ]; then
    echo "[certbot] ERROR: certificate for $DOMAIN not found."
    exit 1
fi

DAYS_LEFT="$(printf '%s\n' "$CERT_INFO" | sed -n \
    's/.*VALID: \([0-9][0-9]*\) days.*/\1/p' | sed -n '1p')"

if [ -z "$DAYS_LEFT" ]; then
    echo "[certbot] ERROR: failed to parse certificate validity."
    exit 1
fi

if [ "$MODE" = "--healthcheck" ]; then
    if [ "$DAYS_LEFT" -ge 0 ]; then
        exit 0
    fi
    exit 1
fi

if [ "$DAYS_LEFT" -le "$WARN_DAYS" ]; then
    echo "[certbot] WARNING: certificate for $DOMAIN expires in \
$DAYS_LEFT days (threshold: $WARN_DAYS)."
else
    echo "[certbot] OK: certificate for $DOMAIN is valid for \
$DAYS_LEFT days."
fi
