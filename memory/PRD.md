# CashOutAi - Product Requirements Document

## Original Problem Statement
Build and maintain the CashOutAi trading platform - a full-stack application with real-time chat, stock data lookup, user management with admin approval flows, and email notifications.

## Architecture
- **Frontend**: React + Tailwind CSS (deployed on Render as static build)
- **Backend**: FastAPI (Python) with uvicorn (deployed on Render)
- **Database**: MongoDB Atlas (free tier)
- **Hosting**: Render (Starter plan) from GitHub
- **DNS**: GoDaddy → cashoutai.app
- **Email**: Resend API (noreply@cashoutai.app)
- **Integrations**: Financial Modeling Prep (FMP), Firebase Cloud Messaging (FCM), Zapier

## What's Been Implemented

### Authentication & Security
- User registration with admin manual approval (no auto-approve for any plan)
- Bcrypt password hashing (with auto-migration from legacy SHA-256)
- CORS locked to cashoutai.app domain only
- Rate limiting on registration (5/minute) to prevent abuse
- Sessions last 365 days (essentially permanent until device clear)

### Email System (Resend)
- Switched from SMTP (blocked on Render) to Resend HTTP API
- Domain verified: noreply@cashoutai.app
- Emails: registration confirmation, admin notification, trial welcome, upgrade prompts
- All plans show regular prices: Monthly $199, Yearly $1,296, Lifetime $3,969
- No promo codes/discounts
- Test endpoint: GET /api/email/test, GET /api/email/check

### Chat System
- Real-time chat via WebSocket
- Initial load: 50 messages (fast), "Load older messages" button for pagination
- Date separators (Today, Yesterday, specific dates)
- Admin can delete any message (trash icon on hover)
- Debug/bot messages no longer leak raw content to chat
- Image paste/upload support
- Scroll fixed: only scrolls chat container, not entire page

### Stock Data
- FMP API with penny stock fallback
- Zapier price alert integration

### Profile
- Twitter/X-style redesigned profile page

### Performance
- MongoDB indexes on: messages.timestamp, users.id, users.username, users.email, users.is_online
- Health check endpoint: GET /api/health
- Loading screen timer fix (useRef prevents re-render reset)
- Firebase init non-blocking (won't hang app startup)

### Firebase Push Notifications (Fixed 2026-03-22)
- Backend: FCM service via firebase-admin SDK (credentials from file or FIREBASE_ADMIN_CREDENTIALS env var)
- Backend endpoints: /api/fcm/register-token, /api/fcm/test-notification, /api/fcm/status (diagnostic)
- Frontend: Unified to single Service Worker (firebase-messaging-sw.js)
- Fixes applied:
  - Removed AudioContext from Service Worker (not available in SW scope)
  - Removed conflicting push event listener (was interfering with Firebase's onBackgroundMessage)
  - Eliminated dual Service Worker conflict (sw.js vs firebase-messaging-sw.js) — now only firebase-messaging-sw.js
  - Added SW lifecycle management (skipWaiting + clients.claim for immediate activation)
  - Improved FCM token acquisition with SW active state waiting
  - Added VAPID key validation before requesting token

### Render Environment Variables (Backend)
- MONGO_URL, DB_NAME
- RESEND_API_KEY, SENDER_EMAIL (noreply@cashoutai.app), ADMIN_EMAIL
- FMP_API_KEY
- FIREBASE_ADMIN_CREDENTIALS (JSON string for firebase-admin SDK)

## Backlog
- P2: Refactor backend/server.py (~4900 lines) into APIRouter modules
- P1 (Future): Mobile app for App Stores
- P3: WebSocket reconnection improvements
- P3: Add pytest test suite for critical endpoints
- P3: Add .env.example file
