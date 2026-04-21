# Deployment Guide for Render.com

This guide walks through deploying the ROSCA FastAPI backend to Render.com.

## 📋 Prerequisites

- [ ] Render.com account (free tier available)
- [ ] GitHub account with code pushed
- [ ] Google Cloud project with Sheets API enabled
- [ ] Service account credentials JSON file
- [ ] Google Sheet shared with service account email

## 🚀 Step-by-Step Deployment

### Step 1: Prepare Your Repository

```bash
# Ensure all files are committed
git status
git add .
git commit -m "Prepare for Render deployment"
git push origin main
```

Verify these files exist:
- ✅ `main.py`
- ✅ `requirements.txt`
- ✅ `render.yaml`
- ✅ `.env.example`
- ✅ `credentials.json` (will be added via environment)

### Step 2: Create Render Service

1. **Log in to Render**: https://render.com
2. **Create New Service**:
   - Click "New +"
   - Select "Web Service"
   - Click "Connect Repository" or "Deploy from Git"
   - Select your GitHub repository
   - Click "Connect"

3. **Configure Service**:
   - **Name**: `rosca-api`
   - **Runtime**: Select `Python 3`
   - **Region**: Select nearest to you
   - **Branch**: `main` (or your branch)
   - **Build Command**: 
     ```
     pip install -r requirements.txt
     ```
   - **Start Command**: 
     ```
     uvicorn main:app --host 0.0.0.0 --port $PORT
     ```

4. **Select Plan**: 
   - Free tier is fine for development/testing
   - Upgrade to paid for production

5. **Click "Create Web Service"**

### Step 3: Add Environment Variables

After service is created (or while creating):

1. Go to service settings
2. Find "Environment" section
3. Add these variables:

```
ENVIRONMENT=production
DEBUG=false
SECRET_KEY=<GENERATE_A_SECURE_KEY>
PORT=8000
SHEET_NAME=RJ_ROSCA_General_July23
CORS_ORIGINS=<YOUR_FLUTTER_APP_URL>
USER_CREDENTIALS_SHEET=user_credentails
MAIN_SHEET=Main_Calculations
LOAN_SHEET=loan_waterfall_c2
LOAN_REQUIREMENTS_SHEET=loan_requirements
MISCELLANEOUS_SHEET=miscellaneous
EMI_CUTOFF_DAY=5
CACHE_TTL_SECONDS=3600
```

### Step 4: Handle Google Credentials

**Option A: Environment Variable (Recommended)**

1. Open your `credentials.json` file
2. Copy the entire JSON content
3. In Render dashboard, add variable:
   ```
   GOOGLE_CREDENTIALS_JSON=<paste-entire-json-here>
   ```
4. Update `core/database.py` to read from env:

```python
import os
import json
from google.oauth2.service_account import Credentials

def init_gsheet_client():
    """Initialize Google Sheets client"""
    try:
        # Try reading from environment first
        creds_json = os.getenv('GOOGLE_CREDENTIALS_JSON')
        if creds_json:
            creds_dict = json.loads(creds_json)
        else:
            # Fall back to file
            with open(settings.CREDENTIALS_FILE, 'r') as f:
                creds_dict = json.load(f)
        
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = gspread.authorize(creds)
        logger.info("✓ Google Sheets client initialized")
        return client
    except Exception as e:
        logger.error(f"✗ Error initializing Google Sheets client: {str(e)}")
        raise
```

**Option B: Upload as File**

1. In Render, use "Sync Deployment" feature
2. Or add pre-deployment script to install credentials

### Step 5: Generate Secure Key

Generate a secure SECRET_KEY:

```bash
# Linux/macOS
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Windows PowerShell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Copy the output and set as SECRET_KEY in Render environment.

### Step 6: Deploy

1. **Manual Deploy**:
   - In Render dashboard, click "Deploy latest commit"
   - Monitor the deployment process in "Logs" tab

2. **Auto Deploy**:
   - Render automatically deploys on each GitHub push
   - Configure in service settings

3. **Wait for Deployment**:
   - First deployment takes 2-5 minutes
   - Subsequent deployments are faster

### Step 7: Verify Deployment

Once deployment completes:

```bash
# Replace YOUR_SERVICE_NAME with your Render service name
# Get from Render dashboard - it's your-service-name.onrender.com

# Health check
curl https://your-service-name.onrender.com/health

# Login test
curl -X POST https://your-service-name.onrender.com/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"test_user","password":"test_password"}'
```

Expected responses:
- Health: `{"status":"ok","timestamp":"..."}`
- Login: Token response or 401 (expected if credentials don't exist)

### Step 8: Update Flutter App Configuration

Update your Flutter app with the production API URL:

```dart
class RoscaApiClient {
  static const String baseUrl = 'https://your-service-name.onrender.com/api';
  // Rest of the client code...
}
```

## 🔍 Monitoring & Debugging

### View Logs

1. Open Render dashboard
2. Select your service
3. Click "Logs" tab
4. View real-time logs

### Common Issues

#### Issue: 503 Service Unavailable

**Cause**: Deployment still in progress
**Solution**: Wait 2-3 minutes and refresh

#### Issue: 500 Internal Server Error

**Cause**: Usually Google credentials issue
**Solution**: 
- Check logs for error details
- Verify GOOGLE_CREDENTIALS_JSON is valid JSON
- Verify Google Sheet is shared with service account

#### Issue: 401 Unauthorized

**Cause**: Database not initialized or credentials wrong
**Solution**:
- Verify credentials.json/GOOGLE_CREDENTIALS_JSON
- Check Google Sheets API is enabled
- Verify user exists in credentials sheet

#### Issue: CORS Error from Flutter

**Cause**: CORS_ORIGINS not configured for your app
**Solution**: 
- Get your Flutter app domain
- Add to CORS_ORIGINS env variable
- Re-deploy

### View Metrics

- CPU usage
- Memory usage
- Request count
- Response time

Available in Render dashboard under "Metrics" tab.

## 📊 Performance Tips

1. **Enable Caching**: Set CACHE_TTL_SECONDS appropriately
   - Reduce Google Sheets API calls
   - Improve response times

2. **Database Optimization**:
   - Reduce data ranges if possible
   - Consider pagination for large datasets

3. **Monitor & Scale**:
   - Watch Render metrics
   - Upgrade plan if needed

## 🔐 Security Checklist

- [ ] DEBUG=false in production
- [ ] SECRET_KEY is strong and random
- [ ] GOOGLE_CREDENTIALS_JSON is secure (not committed to Git)
- [ ] CORS_ORIGINS configured for your domain only
- [ ] HTTPS only (Render provides free SSL)
- [ ] Regular password updates for Google credentials
- [ ] Implement rate limiting (optional)

## 🔄 Continuous Deployment

### Auto-Deploy on Git Push

1. Connect GitHub repo
2. Enable auto-deploy in Render settings
3. Any push to `main` branch auto-deploys

### Manual Deploy

```bash
# In Render dashboard, click "Redeploy"
# or push to your connected branch
```

### Rollback

If deployment fails:
1. Previous version still runs
2. Fix the issue
3. Push again to re-deploy
4. Or manually click "Redeploy" on previous commit

## 📈 Upgrade Path

### Free Tier Limitations

- Cold starts (sleeps after 15 min inactivity)
- Shared resources
- No fixed IP

### Paid Tier Benefits

- Always running (no cold starts)
- Dedicated resources
- Better performance
- Priority support

Upgrade in Render dashboard > Service Settings > Plan

## 📞 Support

### Render Support
- Docs: https://render.com/docs
- Status: https://status.render.com
- Help: support@render.com

### ROSCA Project Help
- Check logs for error messages
- Review FASTAPI_README.md
- Check GitHub Issues

## ✅ Deployment Checklist

- [ ] Code pushed to GitHub
- [ ] `main.py` works locally
- [ ] `requirements.txt` has all dependencies
- [ ] Render service created
- [ ] Environment variables set
- [ ] Google credentials configured
- [ ] Deployment complete
- [ ] Health check passes
- [ ] Flutter app connects successfully
- [ ] Test login endpoint
- [ ] Monitor logs for errors

## 🎉 Success!

Your ROSCA FastAPI backend is now live on Render!

**API URL**: `https://your-service-name.onrender.com`
**Docs**: `https://your-service-name.onrender.com/docs`
**Health**: `https://your-service-name.onrender.com/health`

Share this URL with your Flutter team to integrate!

---

**Next Steps**:
1. Update Flutter app with API URL
2. Test all endpoints
3. Monitor performance
4. Configure alerts (optional)
