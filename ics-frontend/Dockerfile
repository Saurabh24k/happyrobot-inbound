# --- build stage ---
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# --- runtime stage ---
FROM nginx:1.25-alpine
RUN apk add --no-cache bash gettext

# static assets
COPY --from=builder /app/dist /usr/share/nginx/html

# nginx template + entrypoint
COPY default.conf.tmpl /etc/nginx/conf.d/default.conf.tmpl
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# runtime envs (Render will set them)
ENV PORT=8080
ENV API_BASE_URL=""
ENV API_KEY=""

EXPOSE 8080
ENTRYPOINT ["/docker-entrypoint.sh"]
