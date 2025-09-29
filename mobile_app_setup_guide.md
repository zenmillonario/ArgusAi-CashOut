# 📱 ArgusAI CashOut Mobile App Setup Guide
## Google Play Store with Capacitor

### Phase 1: Setup Capacitor (15 minutes)

#### Step 1: Install Capacitor
```bash
cd /app/frontend
npm install @capacitor/core @capacitor/cli
npm install @capacitor/android
npx cap init "ArgusAI CashOut" "com.argusai.cashout"
```

#### Step 2: Build your React app for production
```bash
npm run build
```

#### Step 3: Add Android platform
```bash
npx cap add android
```

#### Step 4: Sync your web assets
```bash
npx cap sync
```

### Phase 2: Configure Android App (20 minutes)

#### Step 5: Update capacitor.config.ts
```typescript
import { CapacitorConfig } from '@capacitor/core';

const config: CapacitorConfig = {
  appId: 'com.argusai.cashout',
  appName: 'ArgusAI CashOut',
  webDir: 'build',
  server: {
    androidScheme: 'https'
  },
  plugins: {
    SplashScreen: {
      launchShowDuration: 3000,
      backgroundColor: "#1f2937",
      showSpinner: false
    }
  }
};

export default config;
```

#### Step 6: Configure Android permissions
Edit `android/app/src/main/AndroidManifest.xml`:
```xml
<uses-permission android:name="android.permission.INTERNET" />
<uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />
<uses-permission android:name="android.permission.WAKE_LOCK" />
```

### Phase 3: Build APK (10 minutes)

#### Step 7: Open in Android Studio
```bash
npx cap open android
```

#### Step 8: Build APK in Android Studio
1. Click "Build" → "Generate Signed Bundle/APK"
2. Choose "APK" 
3. Create new keystore (SAVE THIS FILE - YOU'LL NEED IT FOR UPDATES!)
4. Build release APK

### Phase 4: Google Play Store Setup (30 minutes)

#### Step 9: Create Google Play Console Account
1. Go to https://play.google.com/console
2. Pay $25 registration fee
3. Complete developer profile

#### Step 10: Prepare App Store Assets
You'll need:
- App icon (512x512px)
- Feature graphic (1024x500px)
- Screenshots (at least 2, up to 8)
- App description
- Privacy policy URL

#### Step 11: Create App Listing
1. "Create app" in Play Console
2. Upload APK to "Internal testing" first
3. Fill out store listing
4. Set content rating
5. Submit for review

### Phase 5: Required Configurations for Trading App

#### Step 12: Handle WebSocket connections
Update your React app to detect mobile:
```javascript
// In App.js
const isMobile = window.Capacitor?.isNative;
const wsUrl = isMobile 
  ? 'wss://your-backend-url.com/api/ws' 
  : `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/api/ws`;
```

#### Step 13: Add mobile-specific features
```bash
npm install @capacitor/status-bar @capacitor/keyboard @capacitor/device
```

### Expected Timeline:
- **Setup & Development**: 2-3 hours
- **Testing**: 1-2 days
- **Google Play Review**: 1-3 days
- **Total**: ~1 week to go live

### Estimated Costs:
- Google Play registration: $25 (one-time)
- Android Studio: Free
- Total startup cost: $25

### Next Steps:
1. Install Android Studio on your development machine
2. Follow steps 1-6 to set up Capacitor
3. Test the app on Android device/emulator
4. Create Google Play Console account
5. Submit for review

Would you like me to help you start with Step 1?