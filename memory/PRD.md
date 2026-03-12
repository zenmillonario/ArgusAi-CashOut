# CashOutAi - Product Requirements Document

## Original Problem Statement
Build and maintain the ArgusAI-CashOut trading platform (now named "CashOutAi") - a full-stack application with real-time chat, stock data lookup, user management with admin approval flows, and email notifications.

## Architecture
- **Frontend**: React + Tailwind CSS (deployed on Render as static build)
- **Backend**: FastAPI (Python) with uvicorn (deployed on Render)
- **Database**: MongoDB Atlas (free tier)
- **Hosting**: Render (from GitHub)
- **DNS**: GoDaddy → cashoutai.app
- **Integrations**: Gmail SMTP, Financial Modeling Prep (FMP), Firebase Cloud Messaging (FCM)

## Core Features
- User authentication with admin approval workflow
- Real-time chat via WebSocket with 500+ message history
- Stock data lookup (supports penny stocks via FMP fallback)
- Social media-style profile pages (Twitter/X inspired)
- Trial user system (14-day auto-approved trials)
- Email notifications (registration, approval, trial welcome/upgrade)
- Achievement/XP system
- Paper trading

## What's Been Implemented

### Completed
- Authentication and domain fixes (login on cashoutai.app)
- Stock Price API with penny stock fallback
- Profile page redesign (Twitter/X-style)
- Chat history (500+ messages with DB indexing)
- Chat timestamps with UTC fix + date separators
- Chat UI/UX fixes (mobile input, gap, auto-scroll)
- Image/ticker paste functionality
- Deployment configuration (Firebase env vars, production build)
- **Email notification system** - Fixed and verified working (March 2026)
  - Added diagnostic endpoint `/api/email/test`
  - Better init logging in EmailService
  - Updated render.yaml with MAIL_* env var declarations
  - Trial welcome emails, admin notifications, registration confirmations all working

### Key Environment Variables (Render Backend)
- MONGO_URL, DB_NAME
- MAIL_USERNAME, MAIL_PASSWORD, MAIL_FROM, MAIL_PORT, MAIL_SERVER, MAIL_TLS
- FMP_API_KEY
- FIREBASE_* variables
- SECRET_KEY

## Backlog
- **P1**: Mobile app for App Stores (Google Play, Apple App Store)
- **P2**: Refactor backend/server.py (~4900 lines) into APIRouter modules

## Key Technical Notes
- `.env` files are gitignored; Render uses dashboard env vars
- MongoDB free tier needs indexes for large sorts (messages.timestamp index exists)
- Chat UI layout uses complex flexbox - test mobile + desktop after CSS changes
- Code deploys via: Emergent "Save to Github" → auto-deploy on Render
