FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

# Copy and install deps first (better build cache)
COPY api/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Copy the backend source (puts api/app.py → /app/app.py)
COPY api/ /app

# Render will provide $PORT; default to 10000 locally
EXPOSE 10000
CMD ["sh","-c","gunicorn -k uvicorn.workers.UvicornWorker -b 0.0.0.0:${PORT:-10000} app:app --timeout 120"]
