FROM node:24-bookworm-slim@sha256:d6aa754f16b3197301076f047b5def2f02ea1dbbc2ca920407d46d7ec7f87b20 AS build
WORKDIR /app
COPY frontend/package*.json ./
RUN --mount=type=secret,id=enterprise_ca,target=/run/secrets/enterprise-ca.crt if [ -f /run/secrets/enterprise-ca.crt ]; then NODE_EXTRA_CA_CERTS=/run/secrets/enterprise-ca.crt npm ci --no-audit --no-fund; else npm ci --no-audit --no-fund; fi
COPY frontend ./
RUN npm run build
FROM nginxinc/nginx-unprivileged:stable-alpine@sha256:56b8272e43a0525f67aed68d1e0794a712d10e3e45a563e118e9a77c817e6f86
COPY --chmod=0644 deploy/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
