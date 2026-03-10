# CashOutAI (ArgusAI CashOut) - Product Requirements Document

## Problem Statement
CashOutAI is a trading community platform with real-time chat, portfolio tracking, and social features. Originally deployed on Render with a custom domain `cashoutai.app`.

## Core Tech Stack
- **Frontend**: React (served via `serve` on Render)
- **Backend**: FastAPI (Python)
- **Database**: MongoDB Atlas (free tier)
- **Deployment**: Render (2 services: frontend + backend)
- **DNS**: GoDaddy (`cashoutai.app`)
- **Integrations**: FMP (stock prices), Gmail SMTP (emails), Firebase (notifications)

## Architecture
```
/app/
├── backend/
│   ├── server.py          # Monolithic FastAPI (~4900 lines)
│   ├── email_service.py   # Gmail SMTP
│   ├── cash_prize.py      # Cash prize logic
│   └── fcm_service.py     # Firebase push notifications
├── frontend/
│   └── src/
│       ├── App.js         # Main app (~3800 lines)
│       ├── ChatTab.js     # Chat UI with date separators
│       ├── ProfileCustomization.js
│       ├── PublicProfile.js
│       └── ...
```

## Key Credentials
- **Test login**: admin / admin123
- **FMP API Key**: In backend/.env
- **Custom domain**: cashoutai.app

## What's Been Implemented
### Session 1 (Previous)
- Admin email notifications for new signups
- Remember Me session persistence
- Firebase mobile error fix
- Custom domain setup on GoDaddy/Render
- Multiple deployment fixes (env vars, circular imports, MongoDB robustness)

### Session 2 (Current - March 10, 2026)
- **Fixed Render deployment**: Frontend was running `npm start` (dev mode) instead of production build. Changed start command to `npx serve -s build -p $PORT`
- **Fixed MongoDB auth**: Corrected MONGO_URL format on Render (removed angle brackets, added database name)
- **Fixed FMP stock API**: Updated from deprecated `/api/v3/quote/` to new `/stable/quote?symbol=` endpoint
- **Profile tab redesign**: Twitter/X style with banner, avatar overlay, followers/following, achievements, stats cards
- **Chat history**: Increased from 50 to 500 messages using MongoDB aggregation with `allowDiskUse=True`
- **Daily date separators**: "Today", "Yesterday", or full date (e.g., "Friday, October 24, 2025")
- **Fixed chat timestamps**: Timestamps were 4 hours off because UTC timestamps lacked 'Z' suffix. Added `parseUTC()` helper

## Backlog
### P1
- **Mobile App**: Capacitor/Expo approach abandoned. Consider hiring specialist with "Mobile Developer Brief"

### P2
- **Backend refactoring**: server.py is ~4900 lines, needs to be split into modular routers
- **Email env vars on Render**: MAIL_USERNAME, MAIL_PASSWORD etc. should be added for email notifications to work on production

### P3
- **Chat history pagination**: Currently loads all 500 at once. Consider infinite scroll/pagination for better performance
