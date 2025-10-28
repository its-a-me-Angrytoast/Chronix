FROM python:3.11-slim
WORKDIR /app

# Install dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . /app

ENV PYTHONUNBUFFERED=1
ENV PORT=8080

CMD ["python", "run.py"]
