# Pinned build stage.
FROM node:20.18.1-alpine3.20 AS builder

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts
COPY . .
RUN npm run build

# Pinned nginx-alpine runtime executed as the dedicated UID, on an unprivileged
# port. The config contains no development server or Vite fallback.
FROM nginx:1.27.4-alpine3.20 AS runtime

RUN addgroup -S -g 10001 attilan \
    && adduser -S -D -H -u 10001 -G attilan attilan \
    && mkdir -p /var/cache/nginx /var/run /tmp/nginx /var/log/nginx \
    && chown -R 10001:10001 /var/cache/nginx /var/run /tmp/nginx /var/log/nginx /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder --chown=10001:10001 /app/dist /usr/share/nginx/html

USER 10001:10001
EXPOSE 8080
CMD ["nginx", "-g", "pid /tmp/nginx/nginx.pid; daemon off;"]
