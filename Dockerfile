FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# system deps needed for some Python packages (asyncpg, pillow, lxml, etc.)
RUN apt-get update \
	&& apt-get install -y --no-install-recommends \
	   build-essential \
	   gcc \
	   libpq-dev \
	   libffi-dev \
	   libssl-dev \
	   libjpeg-dev \
	   zlib1g-dev \
	   curl \
	&& rm -rf /var/lib/apt/lists/*

# Copy only requirements first to leverage Docker layer cache
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy the rest of the project
COPY . /app

# Create an unprivileged user for running the bot
RUN useradd --create-home --home-dir /home/chronix chronix \
	&& chown -R chronix:chronix /app

USER chronix

EXPOSE 8080
ENV PORT=8080

CMD ["python", "run.py"]
