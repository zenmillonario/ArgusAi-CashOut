# ArgusAI CashOut - Trading Platform

## Setup Instructions

### Firebase Push Notifications Setup

To enable Firebase push notifications:

1. **Create Firebase Project**: Go to [Firebase Console](https://console.firebase.google.com/) and create a new project

2. **Generate Service Account**: 
   - Go to Project Settings > Service Accounts
   - Click "Generate new private key"
   - Download the JSON file

3. **Setup Credentials**:
   - Copy the downloaded JSON file to `backend/firebase-admin.json`
   - Update `frontend/src/firebase-config.js` with your Firebase web app config

4. **Environment Variables**: The app uses these configurations:
   - Backend: `backend/firebase-admin.json` (service account key)
   - Frontend: Firebase config in `frontend/src/firebase-config.js`

### Features
- Real-time chat with WebSocket support
- Paper trading with portfolio management
- Admin-only push notifications with WhatsApp-style sounds
- User authentication and approval system
- Mobile-responsive design

### Security Notes
- Never commit `firebase-admin.json` to version control
- The template file `firebase-admin.json.template` shows the required structure
