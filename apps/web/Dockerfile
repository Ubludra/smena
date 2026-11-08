# =============================================================================
# Smena Web — build (node) → serve (nginx-unprivileged static SPA)
# =============================================================================

# --- Build stage ---
FROM docker.io/library/node:20-bookworm-slim AS build
WORKDIR /app

# Dependency layer: manifests only, so source edits don't reinstall node_modules.
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY tsconfig.json vite.config.ts eslint.config.js index.html ./
COPY public ./public
COPY src ./src

# Vite embeds env vars at BUILD time; value comes from compose build args.
ARG VITE_API_BASE_URL=http://localhost:8000
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
ARG VITE_ENABLE_BROWSER_DEMO=false
ENV VITE_ENABLE_BROWSER_DEMO=${VITE_ENABLE_BROWSER_DEMO}

RUN npm run build

# --- Runtime stage ---
# nginx-unprivileged: runs entirely as uid 101, listens on 8080 (no root).
FROM docker.io/nginxinc/nginx-unprivileged:1.27-alpine AS runtime
RUN rm /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
    CMD wget -qO /dev/null http://127.0.0.1:8080/ || exit 1
