#!/bin/sh
set -e

# Default to empty if not provided
: "${BACKEND_BASE_URL:=}"

INDEX_FILE="/usr/share/nginx/html/index.html"
if [ -f "$INDEX_FILE" ]; then
  # Replace placeholder with the provided BACKEND_BASE_URL (can be empty)
  sed -i "s|__BACKEND_BASE_URL__|${BACKEND_BASE_URL}|g" "$INDEX_FILE"
fi

exec nginx -g 'daemon off;'
