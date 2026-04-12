# CashOutAi / ArgusAI CashOut - PRD

## Original Problem Statement
Build "CashOutAi – Trade Together, Win Together" — a lightweight, private team chat app for traders. Think of it as a game-like WhatsApp for market-minded crews.

## Core Features (Implemented)
- Team Chat with WebSocket real-time messaging
- Smart Message Highlights ($TSLA stock tickers in blue)
- Bold Admin messages
- Profile & Performance Tracking (paper trades, avg gain, win %, total profit)
- Favorites Tab (watchlist)
- Practice Tab (paper trading with stop-loss/take-profit)
- Game-Like Elements (XP, levels, achievements)
- Admin Panel (user approvals, roles, online status, kick/ban)
- Dark/Light themes
- Message search, reactions, reply-to
- Image/GIF uploads in chat
- Loading screen with Matrix-style animation
- Remember me (30-day sessions)
- Push notifications for admin messages
- Mobile-optimized layout (Capacitor ready)

## Tech Stack
- Frontend: React, Tailwind CSS
- Backend: FastAPI, Motor (MongoDB async driver)
- Database: MongoDB
- Real-time: WebSockets
- Auth: bcrypt password hashing

## Key DB Collections
- users: {id, username, email, password_hash, is_admin, status, avatar_url, real_name, screen_name, experience_points, level, ...}
- messages: {id, user_id, username, content, content_type, text_content, reply_to_id, reply_to, highlighted_tickers, ...}
- paper_trades: {id, user_id, symbol, action, quantity, price, stop_loss, take_profit, ...}
- positions: {id, user_id, symbol, quantity, avg_price, current_price, unrealized_pnl, ...}

## What Was Fixed (April 12, 2026)
1. **Forgot Password** — Old flow relied on email service (not configured). Replaced with direct reset (username + email verification → set new password).
2. **Chat Reply + Image** — Fixed: (a) text input no longer disabled when image selected, (b) text_content sent alongside image messages, (c) reply-to cleared after send, (d) image captions displayed in chat.

## Backlog
- App Store / Google Play packaging (Capacitor)
- Real stock price API integration (currently mocked)
- Email service configuration for notification emails
- Leaderboard enhancements
