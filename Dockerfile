FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

# Install deps (better cache)
COPY api/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Copy the backend as a package at /app/api
COPY api /app/api

# In case __init__.py is missing, make it a package anyway
RUN [ -f /app/api/__init__.py ] || touch /app/api/__init__.py

# Render assigns $PORT; default to 10000 for local runs
EXPOSE 10000
CMD ["sh","-c","gunicorn -k uvicorn.workers.UvicornWorker -b 0.0.0.0:${PORT:-10000} api.app:app --timeout 120"]
