# ROSCA Financial Dashboard API - FastAPI Backend

This is a refactored FastAPI backend for the ROSCA (Rotating Savings and Credit Association) Financial Dashboard, designed for use with Flutter frontend and deployment on Render.

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Setup & Installation](#setup--installation)
- [Running Locally](#running-locally)
- [API Endpoints](#api-endpoints)
- [Deployment on Render](#deployment-on-render)
- [Flutter Integration](#flutter-integration)
- [Troubleshooting](#troubleshooting)

## 🎯 Overview

This FastAPI backend replaces the original Streamlit application, providing a REST API suitable for:
- ✅ Flutter mobile applications
- ✅ Web frontends
- ✅ Multiple concurrent clients
- ✅ Scalable production deployment
- ✅ Easy integration with cloud services

## ✨ Features

- **JWT Authentication**: Secure token-based authentication
- **RESTful API**: Clean, standard REST endpoints
- **Google Sheets Integration**: Direct data access from Google Sheets
- **CORS Support**: Ready for cross-origin requests from Flutter
- **Caching Layer**: In-memory caching to reduce Google Sheets API calls
- **Comprehensive Logging**: Built-in logging for debugging
- **Pydantic Models**: Type-safe request/response validation
- **Render-Ready**: Pre-configured for Render.com deployment

## 🏗️ Architecture

```
┌─────────────────┐
│  Flutter App    │
└────────┬────────┘
         │ HTTP/REST
         ▼
┌─────────────────────────────────────┐
│     FastAPI Backend (main.py)       │
├─────────────────────────────────────┤
│  Routes Layer (api/routes/*.py)    │
│  - Auth, Dashboard, Loans,         │
│    Collections, Users              │
├─────────────────────────────────────┤
│  Services Layer (services/*.py)    │
│  - Data Loading, Processing,       │
│    Metrics, Authentication         │
├─────────────────────────────────────┤
│  Core Layer (core/*.py)            │
│  - Security, Config, Database      │
└─────────────────────────────────────┘
         │ Google Sheets API
         ▼
┌─────────────────────────────────────┐
│     Google Sheets (Data Source)    │
└─────────────────────────────────────┘
```

## 📁 Project Structure

```
rj-rosca-main/
├── main.py                     # FastAPI application entry point
├── requirements.txt            # Python dependencies
├── render.yaml                 # Render.com deployment config
├── .env.example               # Environment variables template
│
├── core/
│   ├── __init__.py
│   ├── config.py              # Settings management
│   ├── security.py            # JWT and password handling
│   ├── database.py            # Google Sheets client
│   └── cache.py               # In-memory caching
│
├── api/
│   ├── __init__.py
│   └── routes/
│       ├── __init__.py
│       ├── auth.py            # Authentication endpoints
│       ├── dashboard.py       # Dashboard metrics endpoints
│       ├── loans.py           # Loan management endpoints
│       ├── collections.py     # Collection summary endpoints
│       └── users.py           # User management endpoints
│
├── services/
│   ├── __init__.py
│   ├── data_loader.py         # Google Sheets data loading
│   ├── data_processor.py      # Data cleaning and processing
│   ├── metrics.py             # Metrics calculation
│   ├── loan_services.py       # Loan calculations
│   └── auth_service.py        # Authentication logic
│
├── schemas/
│   ├── __init__.py
│   └── models.py              # Pydantic request/response models
│
└── credentials.json           # Google Service Account (gitignored)
```

## 🚀 Setup & Installation

### Prerequisites

- Python 3.8+
- pip (Python package manager)
- Google Cloud credentials (service account JSON)
- Git

### 1. Clone the Repository

```bash
cd rj-rosca-main
```

### 2. Create Virtual Environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Setup Google Sheets Credentials

1. Create a Google Cloud project
2. Enable Google Sheets API and Google Drive API
3. Create a Service Account
4. Download the JSON key file
5. Place it in the project root as `credentials.json`
6. Share your Google Sheet with the service account email

### 5. Configure Environment Variables

```bash
# Copy the example file
cp .env.example .env

# Edit .env with your settings
```

Key environment variables:
```bash
SECRET_KEY=your-secure-key-here
SHEET_NAME=RJ_ROSCA_General_July23
DEBUG=True  # Set to False in production
```

## 🏃 Running Locally

### Start the Development Server

```bash
# Using uvicorn directly
uvicorn main:app --reload

# Or using Python
python main.py
```

Server runs at: **http://localhost:8000**

### Access Interactive API Documentation

- Swagger UI: **http://localhost:8000/docs**
- ReDoc: **http://localhost:8000/redoc**

### Test with cURL

```bash
# Health check
curl http://localhost:8000/health

# Login
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"your_username","password":"your_password"}'

# Get metrics
curl -X GET http://localhost:8000/api/dashboard/metrics \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

## 📡 API Endpoints

### Authentication (`/api/auth`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/login` | Login and get JWT token |
| POST | `/logout` | Logout (client-side: discard token) |
| GET | `/me` | Get current user info |
| POST | `/verify-token` | Verify token validity |

**Login Request:**
```json
{
  "username": "user123",
  "password": "password123"
}
```

**Login Response:**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer",
  "expires_in": 86400,
  "user": {
    "user_id": "user123",
    "username": "user123",
    "member_name": "John Doe",
    "role": "member",
    "team_lead": "Team Lead Name"
  }
}
```

### Dashboard (`/api/dashboard`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/metrics` | Get financial metrics |
| GET | `/summary` | Get complete dashboard summary |

**Query Parameters:**
- `year`: Year (default: current year)
- `month`: Month 1-12 (default: current month)

**Metrics Response:**
```json
{
  "total_collection": 50000.00,
  "total_emi": 15000.00,
  "total_share": 20000.00,
  "total_loans": 100000.00,
  "loan_processed": 5,
  "loan_cleared": 2,
  "balance_available": -50000.00,
  "month": "1",
  "year": 2024
}
```

### Loans (`/api/loans`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/active` | Get user's active loans |
| GET | `/all` | Get all loans (paginated) |
| GET | `/{loan_id}` | Get specific loan details |

**Query Parameters:**
- `/all`: `status_filter` (all/disbursed/closed), `limit`, `offset`

### Collections (`/api/collections`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/team/{team_lead}` | Get team collection summary |
| GET | `/all-teams` | Get all teams collections |

### Users (`/api/users`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/profile` | Get current user profile |
| GET | `/` | List all users (paginated) |

## 🚀 Deployment on Render

### Prerequisites

- Render.com account
- GitHub repository with code
- Google Sheets credentials

### Step 1: Push Code to GitHub

```bash
git add .
git commit -m "Refactor to FastAPI"
git push origin main
```

### Step 2: Create Render Service

1. Go to [https://render.com](https://render.com)
2. Click "New +"
3. Select "Web Service"
4. Connect your GitHub repository
5. Configure:
   - **Name**: `rosca-api`
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`

### Step 3: Set Environment Variables

In Render dashboard, add:

```
ENVIRONMENT=production
DEBUG=false
SECRET_KEY=<generate-secure-key>
SHEET_NAME=RJ_ROSCA_General_July23
CORS_ORIGINS=https://your-flutter-app.com
```

### Step 4: Add Google Credentials

**Option A: Upload File (Simpler)**
1. Encode `credentials.json` to base64
2. Set as env variable `CREDENTIALS_FILE_BASE64`
3. In startup, decode and create file

**Option B: Environment Variable (Secure)**
1. Copy entire JSON content
2. Set as `CREDENTIALS_JSON` env variable
3. Code reads from env variable

### Step 5: Deploy

Push to GitHub and Render auto-deploys. Check logs in dashboard.

## 📱 Flutter Integration

### Setup

1. Add HTTP package to Flutter:
```bash
flutter pub add http
```

2. Create API client class:
```dart
class RoscaApiClient {
  static const String baseUrl = 'https://your-render-app.onrender.com/api';
  static late String _token;

  static Future<void> login(String username, String password) async {
    final response = await http.post(
      Uri.parse('$baseUrl/auth/login'),
      headers: {'Content-Type': 'application/json'},
      body: json.encode({
        'username': username,
        'password': password,
      }),
    );

    if (response.statusCode == 200) {
      final data = json.decode(response.body);
      _token = data['access_token'];
    } else {
      throw Exception('Login failed');
    }
  }

  static Future<Map<String, dynamic>> getMetrics({
    required int year,
    required int month,
  }) async {
    final response = await http.get(
      Uri.parse('$baseUrl/dashboard/metrics?year=$year&month=$month'),
      headers: {'Authorization': 'Bearer $_token'},
    );

    if (response.statusCode == 200) {
      return json.decode(response.body);
    } else {
      throw Exception('Failed to fetch metrics');
    }
  }

  // Add other methods for loans, collections, etc.
}
```

### Usage in Flutter

```dart
// Login
await RoscaApiClient.login('username', 'password');

// Get metrics
final metrics = await RoscaApiClient.getMetrics(year: 2024, month: 1);
```

## 🔒 Security Notes

1. **JWT Token**: Keep tokens secure, store in secure storage
2. **HTTPS**: Always use HTTPS in production
3. **CORS**: Configure CORS_ORIGINS to your frontend domain only
4. **Credentials**: Never commit credentials.json to Git
5. **Environment Variables**: Use Render's secure variable storage
6. **Password Hashing**: Update security.py to use bcrypt for production

## 🐛 Troubleshooting

### Issue: "Database client not initialized"

**Solution**: Ensure credentials.json exists and is valid

### Issue: Google Sheets authentication fails

**Solution**: 
1. Verify service account has access to sheet
2. Check credentials.json path
3. Ensure Sheet name matches config

### Issue: CORS errors from Flutter

**Solution**: Add Flutter app URL to CORS_ORIGINS in .env

### Issue: Token expired

**Solution**: Token expires after 24 hours. User must login again.

### View Logs

```bash
# Local development
# Logs print to console

# Render deployment
# View in Render dashboard > Logs tab
```

## 📚 Documentation Links

- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [Pydantic Docs](https://docs.pydantic.dev/)
- [Render Docs](https://render.com/docs)
- [Google Sheets API](https://developers.google.com/sheets/api)
- [JWT Authentication](https://jwt.io/)

## 🤝 Contributing

1. Create feature branch
2. Make changes
3. Test locally
4. Push and create Pull Request

## 📝 License

MIT License - See LICENSE file

---

**Need Help?** Check [DEPLOYMENT.md](./DEPLOYMENT.md) for more detailed deployment instructions.
