# 🚀 CashOutAi Deployment Guide

## Quick Deploy Options

### Option 1: Vercel (Recommended - Free)

1. **Create account**: https://vercel.com
2. **Download deployment files**: 
   - Frontend: `/app/frontend/` folder
   - Backend: `/app/backend/` folder

3. **Deploy Frontend**:
   - Drag `/frontend` folder to Vercel
   - Set build command: `npm run build`
   - Set output directory: `build`
   - Get URL: `https://yourapp.vercel.app`

4. **Deploy Backend**:
   - Drag `/backend` folder to Vercel
   - Add environment variable: `MONGO_URL` (get free MongoDB at mongodb.com/atlas)
   - Get URL: `https://yourapp-backend.vercel.app`

5. **Update Frontend Config**:
   - Update `REACT_APP_BACKEND_URL` in frontend `.env` file
   - Redeploy frontend

### Option 2: Netlify (Frontend) + Railway (Backend)

1. **Frontend on Netlify**:
   - Go to netlify.com
   - Drag `/frontend` folder
   - Get URL: `https://yourapp.netlify.app`

2. **Backend on Railway**:
   - Go to railway.app
   - Connect GitHub or upload `/backend`
   - Add MongoDB service
   - Get URL: `https://yourapp.railway.app`

### Option 3: Heroku (Both Together)

1. **Create Heroku app**
2. **Upload full `/app` folder**
3. **Set environment variables**
4. **Get URL**: `https://yourapp.herokuapp.com`

## 🎯 Environment Variables Needed

### Frontend (.env)
```
REACT_APP_BACKEND_URL=https://your-backend-url.com
```

### Backend (.env)
```
MONGO_URL=mongodb+srv://username:password@cluster.mongodb.net/cashoutai
DB_NAME=cashoutai
```

## 📧 Need Help?

If you need assistance with deployment, you can:
1. Use the automated deployment files included
2. Follow the step-by-step guides above
3. Use a deployment service like Vercel (easiest)

## 🔗 After Deployment

Once deployed, you'll get a URL like:
- `https://cashoutai-yourname.vercel.app`
- `https://magical-peacock-123.netlify.app`
- `https://yourapp.herokuapp.com`

Use this URL in your GoDaddy HTML embed code!