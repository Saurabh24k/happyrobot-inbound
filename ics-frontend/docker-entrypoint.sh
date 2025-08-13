#!/usr/bin/env sh
set -eu

# Defaults (Render will override via service env)
: "${PORT:=8080}"
: "${API_BASE_URL:=https://happyrobot-inbound.onrender.com}"
: "${API_KEY:=}"

# Generate runtime-config.js with envsubst (no caching)
cat >/usr/share/nginx/html/runtime-config.js.tmpl <<'EOF'
window.RUNTIME_CONFIG = {
  API_BASE_URL: "${API_BASE_URL}",
  API_KEY: "${API_KEY}"
};
EOF
envsubst '${API_BASE_URL} ${API_KEY}' \
  </usr/share/nginx/html/runtime-config.js.tmpl \
  >/usr/share/nginx/html/runtime-config.js

# Render nginx.conf with the right PORT
envsubst '${PORT}' \
  </etc/nginx/conf.d/default.conf.tmpl \
  >/etc/nginx/conf.d/default.conf

# (optional) tiny debug so you can see the injected values in Render logs
echo "runtime-config.js ->"
cat /usr/share/nginx/html/runtime-config.js

exec nginx -g 'daemon off;'
