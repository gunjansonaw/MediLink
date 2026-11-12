# -----------------------------------------------------------
# Stage 1: Build React Production Bundle
# -----------------------------------------------------------
FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json ./
# Reproducible install from the lockfile
RUN npm ci --legacy-peer-deps --no-audit --no-fund \
      --fetch-retries=5 --fetch-retry-mintimeout=20000 --fetch-retry-maxtimeout=120000

COPY . ./

ARG REACT_APP_API_URL=/api
ENV REACT_APP_API_URL=$REACT_APP_API_URL \
    NODE_ENV=production \
    CI=false \
    GENERATE_SOURCEMAP=false

RUN npm run build

# -----------------------------------------------------------
# Stage 2: Serve with unprivileged Nginx (runs as non-root on :8080)
# -----------------------------------------------------------
FROM nginxinc/nginx-unprivileged:1.27-alpine

COPY --from=builder /app/build /usr/share/nginx/html
# The image renders /etc/nginx/templates/*.template with envsubst at startup
COPY nginx.conf /etc/nginx/templates/default.conf.template

ENV BACKEND_UPSTREAM=http://backend:8000

EXPOSE 8080
