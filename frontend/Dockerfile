# ── Build Stage ─────────────────────────────────────────────────────────────
FROM node:20.20.2-alpine AS builder

WORKDIR /app

# Copy dependency manifests
COPY package*.json ./

# Install dependencies cleanly
RUN npm ci

# Copy frontend source files
COPY . .

# Build optimized production bundle
RUN npm run build

# ── Runtime Stage (Nginx Reverse Proxy & Static Host) ───────────────────────
# nginx-unprivileged: the official nginx image can't bind port 80 as a
# non-root user (that needs CAP_NET_BIND_SERVICE / root); this image is
# built to run as the non-root "nginx" user on port 8080 instead, with the
# handful of runtime directories nginx needs to write to (cache, pid,
# temp) already owned by that user — no manual chown list required.
FROM nginxinc/nginx-unprivileged:1.27.5-alpine

USER root

# Remove default nginx static files
RUN rm -rf /usr/share/nginx/html/*

# Copy built static assets, owned by the non-root nginx user
COPY --chown=nginx:nginx --from=builder /app/dist /usr/share/nginx/html

# The site config ships as a template rather than a finished .conf so the
# entrypoint can substitute BACKEND_API_KEY into it at container start (see
# templates/default.conf.template). The stock nginx entrypoint renders
# /etc/nginx/templates/*.template into /etc/nginx/conf.d/ before nginx starts.
COPY --chown=nginx:nginx templates/ /etc/nginx/templates/

# Only BACKEND_API_KEY is substituted. Without this filter envsubst would also
# eat nginx's own runtime variables ($host, $remote_addr, $http_upgrade, ...),
# which are written with the same syntax and must survive verbatim.
ENV NGINX_ENVSUBST_FILTER="^BACKEND_API_KEY$"
ENV BACKEND_API_KEY=""

# Empty by default, so the optional access-gate include matches nothing and the
# demo is reachable without credentials. Mount a .conf (plus its htpasswd file)
# here to require auth.
RUN mkdir -p /etc/nginx/auth-gate && chown nginx:nginx /etc/nginx/auth-gate

USER nginx

EXPOSE 8080

# Health check verifying Nginx and backend connectivity
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1:8080/health || exit 1

CMD ["nginx", "-g", "daemon off;"]
