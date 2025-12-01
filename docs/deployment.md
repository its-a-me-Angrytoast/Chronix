# Chronix Bot Deployment Guide

This guide covers deploying Chronix to production using Docker and includes information on security, monitoring, and scalability.

## Quick Start with Docker Compose

1. Clone the repository:
```bash
git clone https://github.com/its-a-me-Angrytoast/Chronix.git
cd Chronix
```

2. Copy and configure environment:
```bash
cp .env.example .env
# Edit .env with your Discord token and other settings
```

3. Build and start services:
```bash
docker-compose up -d --build
```

## Manual Deployment Steps

### Prerequisites

- Python 3.9+
- PostgreSQL 13+
- Redis (optional, for caching)
- Lavalink for music features

### Environment Setup

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
.\venv\Scripts\activate   # Windows
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment variables in `.env`:
```env
# Required
TOKEN=your_discord_bot_token
OWNER_ID=your_discord_id
DATABASE_URL=postgresql://user:pass@localhost:5432/chronix

# Optional
DEV_MODE=false
DASHBOARD_PORT=8080
OPEN_DASHBOARD=false
```

4. Initialize database:
```bash
python -m scripts.run_migrations
```

### Security Considerations

1. API Key and CSRF Protection:
   - Set a strong `DASHBOARD_API_KEY`
   - Enable CSRF protection with `DASHBOARD_CSRF_SECRET`
   - Use HTTPS in production

2. Rate Limiting:
   - Configure `DASHBOARD_RATE_LIMIT`
   - Use a reverse proxy like Nginx for additional protection

3. Database Security:
   - Use SSL for database connections
   - Keep database credentials secure
   - Regular backups

### Docker Deployment

Use Docker Compose for easy deployment of all services:

```yaml
version: '3.8'

services:
  bot:
    build: .
    restart: unless-stopped
    env_file: .env
    volumes:
      - ./data:/app/data
    depends_on:
      - db
      - lavalink

  db:
    image: postgres:13-alpine
    restart: unless-stopped
    environment:
      POSTGRES_USER: chronix
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: chronix
    volumes:
      - postgres_data:/var/lib/postgresql/data

  lavalink:
    image: fredboat/lavalink:latest
    restart: unless-stopped
    volumes:
      - ./lavalink/application.yml:/opt/Lavalink/application.yml

volumes:
  postgres_data:
```

### Kubernetes Deployment

For scaling and high availability, use Kubernetes:

1. Create Kubernetes manifests:
```yaml
# bot-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: chronix-bot
spec:
  replicas: 1
  selector:
    matchLabels:
      app: chronix-bot
  template:
    metadata:
      labels:
        app: chronix-bot
    spec:
      containers:
      - name: chronix
        image: chronix:latest
        envFrom:
        - secretRef:
            name: chronix-secrets
```

2. Create secrets:
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: chronix-secrets
type: Opaque
data:
  TOKEN: <base64-encoded-token>
  DATABASE_URL: <base64-encoded-url>
```

3. Deploy:
```bash
kubectl apply -f k8s/
```

### Monitoring & Metrics

1. Health Checks:
   - Use `/health` endpoint for liveness probe
   - Use `/ready` endpoint for readiness probe

2. Metrics:
   - Enable Prometheus metrics
   - Configure alerts for critical conditions
   - Monitor memory, CPU, and API usage

3. Logging:
   - Use structured logging
   - Configure log retention
   - Set up log aggregation (ELK, Datadog, etc.)

### Backup & Recovery

1. Database Backups:
```bash
# Automated backup script
#!/bin/bash
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
pg_dump -U chronix -h localhost chronix > backup_$TIMESTAMP.sql
```

2. Data Backups:
```bash
# Backup data directory
tar -czf data_backup_$TIMESTAMP.tar.gz data/
```

3. Recovery:
```bash
# Restore database
psql -U chronix -h localhost chronix < backup.sql

# Restore data
tar -xzf data_backup.tar.gz
```

### Scaling & High Availability

1. Database Scaling:
   - Use connection pooling
   - Consider read replicas for heavy workloads
   - Monitor query performance

2. Bot Sharding:
   - Enable sharding for large servers
   - Configure shard count properly
   - Monitor shard health

### CI/CD Pipeline

Use GitHub Actions for automated testing and deployment:

```yaml
name: CI/CD

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.9'
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
    - name: Run tests
      run: |
        python -m pytest tests/

  build:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
    - uses: actions/checkout@v3
    - name: Build Docker image
      run: docker build -t chronix .
    - name: Push to registry
      run: |
        docker tag chronix ghcr.io/${{ github.repository }}/chronix:latest
        docker push ghcr.io/${{ github.repository }}/chronix:latest
```

### Troubleshooting

1. Common Issues:
   - Database connection errors
   - Discord API rate limits
   - Memory leaks
   - Shard connection issues

2. Debug Tools:
   - Enable debug logging
   - Use performance profiling
   - Monitor resource usage

3. Recovery Steps:
   - Check logs for errors
   - Verify connectivity
   - Restart services if needed
   - Restore from backup if necessary

### Security Hardening

1. Network Security:
   - Use firewall rules
   - Enable SSL/TLS
   - Restrict port access

2. Application Security:
   - Keep dependencies updated
   - Regular security audits
   - Enable security headers

3. Authentication:
   - Use strong API keys
   - Implement role-based access
   - Monitor failed attempts

### Performance Optimization

1. Database:
   - Optimize queries
   - Index important columns
   - Regular maintenance

2. Application:
   - Cache frequent operations
   - Optimize API calls
   - Monitor memory usage

3. Network:
   - Use CDN for assets
   - Enable compression
   - Optimize payloads

### Maintenance

1. Regular Tasks:
   - Update dependencies
   - Backup data
   - Clean old logs
   - Monitor disk space

2. Upgrades:
   - Plan maintenance windows
   - Test upgrades in staging
   - Have rollback plan

3. Documentation:
   - Keep deployment docs updated
   - Document configuration changes
   - Maintain runbooks