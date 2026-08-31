# Production Deployment Guide for Twilio SMS Integration

This guide covers deploying the Twilio SMS integration to production environments.

## Prerequisites

- A Twilio account with a phone number
- Python 3.8+
- A production-grade WSGI/ASGI server
- (Recommended) Redis or Firestore for session storage
- (Recommended) A domain name and HTTPS certificate

## Option 1: AWS Lambda + API Gateway

### Setup

1. **Install Serverless Framework**:
   ```bash
   npm install -g serverless
   ```

2. **Create serverless.yml**:
   ```yaml
   service: orchestrator-sms

   provider:
     name: aws
     runtime: python3.11
     region: us-east-1
     environment:
       TWILIO_ACCOUNT_SID: ${env:TWILIO_ACCOUNT_SID}
       TWILIO_AUTH_TOKEN: ${env:TWILIO_AUTH_TOKEN}
       TWILIO_PHONE_NUMBER: ${env:TWILIO_PHONE_NUMBER}
       REDIS_URL: ${env:REDIS_URL}

   functions:
     sms:
       handler: twilio_integration_v2.app
       events:
         - http:
             path: sms
             method: post
       layers:
         - arn:aws:lambda:us-east-1:ACCOUNT:layer:python-dependencies

   plugins:
     - serverless-python-requirements
   ```

3. **Deploy**:
   ```bash
   serverless deploy --env TWILIO_ACCOUNT_SID=xxx TWILIO_AUTH_TOKEN=xxx TWILIO_PHONE_NUMBER=xxx
   ```

4. **Update Twilio webhook**: Use the API Gateway URL returned by Serverless

## Option 2: Google Cloud Run

### Setup

1. **Create Cloud Run service**:
   ```bash
   gcloud run deploy orchestrator-sms \
     --source . \
     --platform managed \
     --region us-central1 \
     --allow-unauthenticated \
     --set-env-vars TWILIO_ACCOUNT_SID=xxx,TWILIO_AUTH_TOKEN=xxx,TWILIO_PHONE_NUMBER=xxx,GOOGLE_CLOUD_PROJECT=your-project
   ```

2. **Set up Firestore for sessions** (built-in to GCP):
   ```bash
   gcloud firestore databases create --location=us-central1
   ```

3. **Update Twilio webhook**: Use the Cloud Run URL

### Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements-twilio.txt .
RUN pip install --no-cache-dir -r requirements-twilio.txt

COPY . .

CMD ["gunicorn", "-w", "1", "--worker-class", "eventlet", "-b", "0.0.0.0:8080", "twilio_integration_v2:app"]
```

## Option 3: Heroku

### Setup

1. **Create Procfile**:
   ```
   web: gunicorn -w 1 --worker-class eventlet -b 0.0.0.0:$PORT twilio_integration_v2:app
   release: python -c "import asyncio; from session_manager import SessionManager; asyncio.run(SessionManager.create().cleanup_expired_sessions())"
   ```

2. **Add Redis add-on** (for production sessions):
   ```bash
   heroku addons:create heroku-redis:premium-0
   ```

3. **Deploy**:
   ```bash
   heroku create orchestrator-sms
   heroku config:set TWILIO_ACCOUNT_SID=xxx TWILIO_AUTH_TOKEN=xxx TWILIO_PHONE_NUMBER=xxx
   git push heroku main
   ```

4. **Update Twilio webhook**: Use the Heroku app URL

## Option 4: DigitalOcean App Platform

### Setup

1. **Create app.yaml**:
   ```yaml
   name: orchestrator-sms
   services:
   - name: api
     github:
       repo: your-username/agentic_hackathon
       branch: main
     build_command: pip install -r requirements-twilio.txt
     run_command: gunicorn -w 1 --worker-class eventlet -b 0.0.0.0:8080 twilio_integration_v2:app
     http_port: 8080
     envs:
     - key: TWILIO_ACCOUNT_SID
       value: ${TWILIO_ACCOUNT_SID}
     - key: TWILIO_AUTH_TOKEN
       value: ${TWILIO_AUTH_TOKEN}
     - key: TWILIO_PHONE_NUMBER
       value: ${TWILIO_PHONE_NUMBER}
   ```

2. **Deploy via DigitalOcean dashboard** or CLI

## Option 5: Traditional VPS (AWS EC2, Linode, DigitalOcean Droplet)

### Setup

1. **SSH into your VPS**:
   ```bash
   ssh root@your-vps-ip
   ```

2. **Install dependencies**:
   ```bash
   apt update && apt install -y python3.11 python3-pip nginx supervisor redis-server
   ```

3. **Clone the repo**:
   ```bash
   cd /opt
   git clone https://github.com/your-username/agentic_hackathon.git
   cd agentic_hackathon
   ```

4. **Install Python dependencies**:
   ```bash
   pip install -r requirements-twilio.txt
   ```

5. **Create .env file**:
   ```bash
   cat > /opt/agentic_hackathon/.env << EOF
   TWILIO_ACCOUNT_SID=xxx
   TWILIO_AUTH_TOKEN=xxx
   TWILIO_PHONE_NUMBER=xxx
   REDIS_URL=redis://localhost:6379/0
   EOF
   chmod 600 /opt/agentic_hackathon/.env
   ```

6. **Set up Supervisor** (process manager):
   ```bash
   cat > /etc/supervisor/conf.d/orchestrator-sms.conf << EOF
   [program:orchestrator-sms]
   directory=/opt/agentic_hackathon
   command=gunicorn -w 4 --worker-class eventlet -b 127.0.0.1:5000 twilio_integration_v2:app
   user=nobody
   autostart=true
   autorestart=true
   redirect_stderr=true
   stdout_logfile=/var/log/orchestrator-sms.log
   environment=PATH="/usr/local/bin",USER="nobody"
   
   [include]
   files = /etc/supervisor/conf.d/*.conf
   EOF
   ```

7. **Start the service**:
   ```bash
   supervisorctl reread
   supervisorctl update
   supervisorctl start orchestrator-sms
   ```

8. **Configure Nginx** (reverse proxy):
   ```bash
   cat > /etc/nginx/sites-available/orchestrator-sms << EOF
   server {
       listen 80;
       server_name your-domain.com;
       
       location / {
           proxy_pass http://127.0.0.1:5000;
           proxy_set_header Host \$host;
           proxy_set_header X-Real-IP \$remote_addr;
           proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
       }
   }
   EOF
   ```

9. **Enable SSL with Certbot**:
   ```bash
   apt install -y certbot python3-certbot-nginx
   certbot --nginx -d your-domain.com
   ```

10. **Enable Nginx site**:
    ```bash
    ln -s /etc/nginx/sites-available/orchestrator-sms /etc/nginx/sites-enabled/
    nginx -t && systemctl restart nginx
    ```

11. **Set up automated cleanup** (cron):
    ```bash
    crontab -e
    # Add this line to run cleanup every hour:
    0 * * * * curl -X POST https://your-domain.com/sessions/cleanup
    ```

## Session Storage for Production

### Redis (Recommended for most deployments)

1. **Install Redis**:
   ```bash
   # Ubuntu
   sudo apt install redis-server
   
   # macOS
   brew install redis
   ```

2. **Start Redis**:
   ```bash
   redis-server
   ```

3. **Set REDIS_URL**:
   ```bash
   export REDIS_URL=redis://localhost:6379/0
   ```

### Firestore (Recommended for GCP deployments)

1. **Create Firestore database**:
   ```bash
   gcloud firestore databases create --location=us-central1
   ```

2. **Set up authentication**:
   ```bash
   gcloud auth application-default login
   ```

3. **Set GOOGLE_CLOUD_PROJECT**:
   ```bash
   export GOOGLE_CLOUD_PROJECT=your-project-id
   ```

## Monitoring and Logging

### CloudWatch (AWS)
```python
import watchtower
logging.basicConfig(
    handlers=[
        watchtower.CloudWatchLogHandler(
            log_group="orchestrator-sms"
        )
    ]
)
```

### Stackdriver (GCP)
```python
from google.cloud import logging as cloud_logging
cloud_logging.Client().setup_logging()
```

### Sentry (Error tracking)
```bash
pip install sentry-sdk
```

```python
import sentry_sdk
sentry_sdk.init("your-sentry-dsn", traces_sample_rate=1.0)
```

## Security Checklist

- [ ] Twilio credentials stored securely (environment variables, not in code)
- [ ] HTTPS enabled (Certbot/ACM)
- [ ] Firewall rules restrict access to necessary ports
- [ ] Rate limiting enabled on Twilio SMS
- [ ] Request validation enabled (verify X-Twilio-Signature)
- [ ] Session data encrypted in Redis/Firestore
- [ ] Regular backups of session/registration data
- [ ] Security headers set (HSTS, X-Content-Type-Options, etc.)
- [ ] SQL injection prevented (N/A here, but check if you add DB)
- [ ] CORS properly configured if frontend exists

## Performance Tuning

1. **Enable connection pooling** in Redis
2. **Increase Gunicorn workers** based on CPU count:
   ```bash
   gunicorn -w $(nproc) --worker-class eventlet
   ```
3. **Enable Gzip compression** in Nginx
4. **Set appropriate timeouts** for Twilio API calls
5. **Monitor response times** and adjust worker count accordingly

## Troubleshooting

### "Invalid Twilio request signature"
- Verify TWILIO_AUTH_TOKEN is correct
- Ensure webhook URL is exactly as configured in Twilio console
- Check that X-Twilio-Signature header is being sent

### Sessions not persisting
- Verify Redis/Firestore is running and accessible
- Check connection string (REDIS_URL or GOOGLE_CLOUD_PROJECT)
- Look for network firewall issues

### High latency responses
- Check Google ADK agent response times
- Monitor sub-agent (tournament, hotel, flight) performance
- Verify no rate limiting from Twilio/Google APIs
- Scale to more workers if CPU is bottleneck

### Out of memory
- Implement session cleanup more frequently
- Reduce SESSION_TTL_HOURS if sessions aren't needed long-term
- Monitor Redis memory usage
