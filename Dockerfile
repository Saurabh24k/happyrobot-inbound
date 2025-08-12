# api/Dockerfile
FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

# deps
COPY api/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# app code as a proper package
COPY api /app/api
# include data directory!
COPY data /app/data

# ensure package import works
RUN [ -f /app/api/__init__.py ] || touch /app/api/__init__.py

# point search service to the CSV in the image
ENV LOADS_CSV_PATH=/app/data/loads.csv

EXPOSE 10000
# NOTE: app import path uses the package now
CMD ["gunicorn","-k","uvicorn.workers.UvicornWorker","-b","0.0.0.0:10000","api.app:app","--timeout","120"]
