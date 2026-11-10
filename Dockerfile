# Small official Python image. "slim" leaves out compilers and docs.
FROM python:3.12-slim

# No .pyc files, and logs appear immediately instead of being buffered.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install packages first: Docker caches this layer until requirements.txt changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY leavedesk ./leavedesk

# Don't run as root inside the container.
RUN useradd --create-home appuser
USER appuser

EXPOSE 8000
CMD ["uvicorn", "leavedesk.api.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
