FROM python:3.12-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258 AS build
ENV PIP_NO_CACHE_DIR=1
RUN --mount=type=secret,id=enterprise_ca,target=/usr/local/share/ca-certificates/enterprise-ca.crt update-ca-certificates --fresh && sed -i s,http://deb.debian.org,https://deb.debian.org,g /etc/apt/sources.list.d/debian.sources && apt-get update && apt-get install -y --no-install-recommends build-essential default-libmysqlclient-dev pkg-config && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY backend/requirements.lock backend/requirements.lock
RUN python -m venv /venv && /venv/bin/pip --cert /etc/ssl/certs/ca-certificates.crt install --require-hashes -r backend/requirements.lock
FROM python:3.12-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258
RUN --mount=type=secret,id=enterprise_ca,target=/usr/local/share/ca-certificates/enterprise-ca.crt update-ca-certificates --fresh && sed -i s,http://deb.debian.org,https://deb.debian.org,g /etc/apt/sources.list.d/debian.sources && apt-get update && apt-get install -y --no-install-recommends libmariadb3 && rm -rf /var/lib/apt/lists/* && useradd --uid 10001 --create-home app
COPY --from=build /venv /venv
ENV PATH=/venv/bin:$PATH PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
WORKDIR /app
COPY --chown=app:app VERSION VERSION
COPY --chown=app:app backend backend
USER app
EXPOSE 8000
CMD ["gunicorn","--umask","0077","--no-control-socket","--chdir","backend","config.wsgi:application","--bind","0.0.0.0:8000","--workers","2","--worker-class","gthread","--threads","4","--timeout","120","--access-logfile","-"]
