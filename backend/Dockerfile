FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all backend code
COPY *.py ./
COPY clients/ ./clients/
COPY models/ ./models/
COPY utils/ ./utils/

EXPOSE 8000

# Default command is Flask app
CMD ["python", "app.py"]
