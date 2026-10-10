FROM python:3.14-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /srv
COPY requirements.lock .
RUN pip install -r requirements.lock
COPY app ./app
RUN useradd -r -u 10001 noviqo && chown -R noviqo /srv
USER noviqo
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --retries=5 CMD python -c "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/api/health', timeout=2)"
# One worker on purpose: the reminder mailer and the in-memory rate limiter assume a single process (see docs/DEPLOYMENT.md)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--no-access-log"]
