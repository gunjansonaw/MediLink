# -----------------------------------------------------------
# Stage 1: Build React Production Bundle
# -----------------------------------------------------------
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package manifests
COPY package*.json ./

# Install dependencies (using legacy-peer-deps for compatibility)
RUN npm install --legacy-peer-deps

# Copy application source code
COPY . ./

# Build arguments for dynamic API URL configuration
ARG REACT_APP_API_URL=/api
ENV REACT_APP_API_URL=$REACT_APP_API_URL \
    NODE_ENV=production \
    CI=false

# Compile production build
RUN npm run build

# -----------------------------------------------------------
# Stage 2: Serve React Static Files with High-Performance Nginx
# -----------------------------------------------------------
FROM nginx:alpine

# Remove default nginx static assets
RUN rm -rf /usr/share/nginx/html/*

# Copy build artifacts from builder stage
COPY --from=builder /app/build /usr/share/nginx/html

# Copy custom Nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose HTTP port
EXPOSE 80

# Run Nginx in the foreground
CMD ["nginx", "-g", "daemon off;"]
