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
- Loading screen with Matrix-style animation
- Mobile-optimized layout (Capacitor ready)

## What Was Fixed (April 12, 2026)
1. **Forgot Password Simplified** — Email-only reset (no username needed). User enters email + new password directly. Backend: `POST /api/users/reset-password-direct`
2. **Chat Reply + Image** — text_content sent alongside image messages, text input stays enabled, reply-to cleared after send, captions displayed in chat.

## Backlog
- App Store / Google Play packaging (Capacitor)
- Email service configuration for notification emails
