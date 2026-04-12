# CashOutAi / ArgusAI CashOut - PRD

## Original Problem Statement
Build "CashOutAi – Trade Together, Win Together" — a lightweight, private team chat app for traders.

## Core Features (Implemented)
- Team Chat with WebSocket real-time messaging, reply-to, image/GIF uploads
- Smart Message Highlights ($TSLA stock tickers in blue)
- Bold Admin messages, push notifications for admin messages
- Profile & Performance Tracking, XP/Levels/Achievements
- Favorites Tab (watchlist), Practice Tab (paper trading with stop-loss/take-profit)
- Admin Panel (user approvals, roles, online status, kick/ban)
- Dark/Light themes, message search, reactions
- Real stock price API (FMP) with mock fallback
- Email service (Resend API) for notifications, password reset emails, welcome emails
- Loading screen with Matrix-style animation
- Mobile-optimized layout (Capacitor ready)

## What Was Fixed (April 12, 2026)
1. **Forgot Password** — Simplified to email-only (no username needed). 3 fields: Email, New Password, Confirm. Backend: `POST /api/users/reset-password-direct`
2. **Chat Reply + Image** — text_content sent alongside image messages, text input stays enabled, reply-to cleared after send
3. **Login Page Background** — Added Matrix code rain animation (matching the intro screen) behind the login form with backdrop-blur glass effect

## Backlog
- App Store / Google Play packaging (Capacitor)
