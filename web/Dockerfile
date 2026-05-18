FROM python:3.12-slim AS tailwind

WORKDIR /build

RUN apt-get update \
 && apt-get install -y --no-install-recommends curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

ARG TAILWIND_VERSION=v3.4.17
RUN curl -fL -o /usr/local/bin/tailwindcss \
      "https://github.com/tailwindlabs/tailwindcss/releases/download/${TAILWIND_VERSION}/tailwindcss-linux-x64" \
 && chmod +x /usr/local/bin/tailwindcss

COPY tailwind.config.js ./
COPY static_src/ static_src/
COPY ipam/ ipam/

RUN tailwindcss \
      -c tailwind.config.js \
      -i static_src/tailwind.css \
      -o /out/tailwind.css \
      --minify


FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

COPY --from=tailwind /out/tailwind.css /srv/tailwind/static/css/tailwind.css

RUN chmod +x /app/entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["gunicorn", "subnetly.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
