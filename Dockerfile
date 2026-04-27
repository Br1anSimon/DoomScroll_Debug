FROM python:3.11-slim

WORKDIR /app

# Install the Flask backend dependencies first so Docker can cache this layer.
COPY backend/requirements.txt .
RUN pip install -r requirements.txt

# Copy the Flask app and the frontend files it serves.
COPY backend/ ./backend/
COPY frontend/ ./frontend/

EXPOSE 8000
CMD ["python", "backend/backend.py"]
