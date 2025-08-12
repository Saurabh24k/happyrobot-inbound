#!/usr/bin/env sh
set -eu

# Default PORT to 8080 locally if not provided
: "${PORT:=8080}"

# Substitute env vars into the nginx template
envsubst '${PORT} ${API_BASE_URL} ${API_KEY}' \
  < /etc/nginx/conf.d/default.conf \
  > /etc/nginx/conf.d/default.conf.out

mv /etc/nginx/conf.d/default.conf.out /etc/nginx/conf.d/default.conf

exec nginx -g 'daemon off;'
