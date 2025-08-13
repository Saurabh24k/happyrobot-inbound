#!/usr/bin/env bash
set -euo pipefail

# 1) Write runtime config used by the SPA at runtime (no rebuild needed)
cat >/usr/share/nginx/html/runtime-config.js <<'EOF'
window.RUNTIME_CONFIG = {
  API_BASE_URL: "${API_BASE_URL}",
  API_KEY: "${API_KEY}"
};
EOF

# 2) Render nginx.conf from template (if the template exists)
if [ -f /etc/nginx/conf.d/default.conf.template ]; then
  envsubst '${API_BASE_URL} ${API_KEY}' </etc/nginx/conf.d/default.conf.template \
    >/etc/nginx/conf.d/default.conf
fi

exec nginx -g 'daemon off;'
