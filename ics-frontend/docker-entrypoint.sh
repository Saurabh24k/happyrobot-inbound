#!/usr/bin/env bash
set -e

# Generate runtime config.js for the SPA
cat >/usr/share/nginx/html/config.js <<'EOF'
window.__ENV__ = {
  API_BASE_URL: "${API_BASE_URL}",
  API_KEY: "${API_KEY}"
};
EOF

# Show what got injected (useful in logs)
echo "[config] API_BASE_URL=${API_BASE_URL}"
echo "[config] API_KEY set? $([[ -n "${API_KEY}" ]] && echo yes || echo no)"

# Run nginx in foreground
exec nginx -g 'daemon off;'
