FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY main.py manage_users.py export_model.py ./
COPY artifacts ./artifacts
RUN useradd -r -u 10001 api && mkdir -p /srv/data && chown api /srv/data
USER api
EXPOSE 8000
# --proxy-headers: trust X-Forwarded-* from the TLS reverse proxy in front (Caddy/nginx)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
