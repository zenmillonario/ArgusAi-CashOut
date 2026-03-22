// Firebase integration for ArgusAI CashOut notifications
import { initializeApp } from 'firebase/app';
import { getMessaging, getToken, onMessage } from 'firebase/messaging';

// Firebase client config (public keys — safe to include in client code)
// These must match the config in firebase-messaging-sw.js
const firebaseConfig = {
  apiKey: process.env.REACT_APP_FIREBASE_API_KEY || "AIzaSyDXsZWHiHAhWxZz4TNmonxbG2RD2WNBoqU",
  authDomain: process.env.REACT_APP_FIREBASE_AUTH_DOMAIN || "cashoutai-notifications.firebaseapp.com",
  projectId: process.env.REACT_APP_FIREBASE_PROJECT_ID || "cashoutai-notifications",
  storageBucket: process.env.REACT_APP_FIREBASE_STORAGE_BUCKET || "cashoutai-notifications.firebasestorage.app",
  messagingSenderId: process.env.REACT_APP_FIREBASE_MESSAGING_SENDER_ID || "1077671941650",
  appId: process.env.REACT_APP_FIREBASE_APP_ID || "1:1077671941650:web:a48c3dce4bffa8e897aacb"
};

// VAPID key for push notifications
const VAPID_KEY = process.env.REACT_APP_FIREBASE_VAPID_KEY || "BCFwFhta05moYQ1dkY6Q1YjWCkGoOOCopnT19IwCzMP62X7RTKIPXUSV4ZQvWAq93QNJKUpV_1yjt42htBcfLvg";

// Mobile browser detection
const isMobileBrowser = () => {
  const userAgent = navigator.userAgent.toLowerCase();
  const mobileKeywords = ['android', 'iphone', 'ipad', 'ipod', 'blackberry', 'windows phone', 'mobile'];
  return mobileKeywords.some(keyword => userAgent.includes(keyword));
};

// Check if Firebase messaging is supported
const isFirebaseSupported = () => {
  if (isMobileBrowser()) {
    console.log('[FCM] Disabled on mobile browsers for compatibility');
    return false;
  }
  return 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window;
};

// Initialize Firebase app
let app = null;
try {
  app = initializeApp(firebaseConfig);
  console.log('[FCM] Firebase app initialized');
} catch (error) {
  console.error('[FCM] Firebase app init failed:', error.message);
}

// Initialize messaging only if supported and app was created
let messaging = null;
if (app && isFirebaseSupported()) {
  try {
    messaging = getMessaging(app);
    console.log('[FCM] Firebase messaging initialized');
  } catch (error) {
    console.warn('[FCM] Messaging initialization failed:', error.message);
    messaging = null;
  }
}

// Wait for service worker to become active
const waitForSWActive = (registration) => {
  return new Promise((resolve) => {
    if (registration.active) {
      resolve(registration);
      return;
    }
    const sw = registration.installing || registration.waiting;
    if (sw) {
      sw.addEventListener('statechange', () => {
        if (sw.state === 'activated') {
          resolve(registration);
        }
      });
    } else {
      resolve(registration);
    }
  });
};

class NotificationService {
  constructor() {
    this.token = null;
    this.isSupported = messaging !== null;
    this.messaging = messaging;
  }

  async requestPermission() {
    if (!this.isSupported) return false;
    try {
      const permission = await Notification.requestPermission();
      console.log('[FCM] Notification permission:', permission);
      return permission === 'granted';
    } catch (error) {
      console.error('[FCM] Error requesting permission:', error);
      return false;
    }
  }

  async registerServiceWorker() {
    if (!this.isSupported) return false;
    try {
      // Unregister stale service workers to ensure the latest version is used
      const existingRegistrations = await navigator.serviceWorker.getRegistrations();
      for (const reg of existingRegistrations) {
        if (reg.active && reg.active.scriptURL.includes('firebase-messaging-sw.js')) {
          await reg.update();
        }
      }
      
      const registration = await navigator.serviceWorker.register('/firebase-messaging-sw.js');
      console.log('[FCM] Service Worker registered, scope:', registration.scope);
      
      // Wait for SW to be active before returning
      await waitForSWActive(registration);
      console.log('[FCM] Service Worker is active');
      return registration;
    } catch (error) {
      console.error('[FCM] Service Worker registration failed:', error);
      return false;
    }
  }

  async getNotificationToken() {
    if (!this.isSupported) return null;

    try {
      const registration = await this.registerServiceWorker();
      if (!registration) return null;

      const hasPermission = await this.requestPermission();
      if (!hasPermission) return null;

      if (!this.messaging) {
        console.warn('[FCM] Messaging not available');
        return null;
      }
      
      if (!VAPID_KEY) {
        console.error('[FCM] VAPID key is missing — check REACT_APP_FIREBASE_VAPID_KEY');
        return null;
      }

      const token = await getToken(this.messaging, {
        vapidKey: VAPID_KEY,
        serviceWorkerRegistration: registration
      });

      if (token) {
        console.log('[FCM] Token obtained:', token.substring(0, 20) + '...');
        this.token = token;
        return token;
      } else {
        console.warn('[FCM] No registration token available');
        return null;
      }
    } catch (error) {
      console.error('[FCM] Error getting token:', error);
      return null;
    }
  }

  async sendTokenToBackend(token, userId) {
    try {
      const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';
      const API_URL = BACKEND_URL ? `${BACKEND_URL}/api` : '/api';
      const response = await fetch(`${API_URL}/fcm/register-token`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, user_id: userId })
      });

      if (response.ok) {
        console.log('[FCM] Token registered with backend');
        return true;
      } else {
        const errText = await response.text();
        console.error('[FCM] Failed to register token:', errText);
        return false;
      }
    } catch (error) {
      console.error('[FCM] Error sending token to backend:', error);
      return false;
    }
  }

  async initializeForUser(userId) {
    if (!this.isSupported) {
      console.log('[FCM] Push notifications not supported in this browser');
      return false;
    }

    try {
      const token = await this.getNotificationToken();
      if (!token) return false;

      const success = await this.sendTokenToBackend(token, userId);
      if (!success) return false;

      this.setupForegroundListener();
      console.log('[FCM] Notifications initialized for user:', userId);
      return true;
    } catch (error) {
      console.error('[FCM] Error initializing notifications:', error);
      return false;
    }
  }

  setupForegroundListener() {
    if (!this.messaging) return;
    
    onMessage(this.messaging, (payload) => {
      console.log('[FCM] Foreground message received:', payload);

      this.playNotificationSound();

      if (Notification.permission === 'granted') {
        const notification = new Notification(
          payload.notification?.title || 'ArgusAI CashOut',
          {
            body: payload.notification?.body || 'New notification',
            icon: '/icon-192x192.png',
            badge: '/badge-72x72.png',
            tag: 'argusai-notification',
            renotify: true,
            requireInteraction: true,
            data: payload.data
          }
        );

        notification.onclick = () => {
          window.focus();
          notification.close();
        };

        setTimeout(() => notification.close(), 5000);
      }
    });
  }

  playNotificationSound() {
    try {
      const audioContext = new (window.AudioContext || window.webkitAudioContext)();
      
      const createBeep = (frequency, duration, delay = 0) => {
        return new Promise((resolve) => {
          setTimeout(() => {
            const oscillator = audioContext.createOscillator();
            const gainNode = audioContext.createGain();
            oscillator.connect(gainNode);
            gainNode.connect(audioContext.destination);
            oscillator.frequency.value = frequency;
            oscillator.type = 'sine';
            gainNode.gain.setValueAtTime(0.1, audioContext.currentTime);
            gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + duration);
            oscillator.start(audioContext.currentTime);
            oscillator.stop(audioContext.currentTime + duration);
            setTimeout(resolve, duration * 1000);
          }, delay);
        });
      };
      
      createBeep(800, 0.15).then(() => createBeep(600, 0.15));
    } catch (error) {
      console.log('[FCM] Could not play notification sound:', error);
    }
  }

  async testNotification() {
    if (this.token) {
      try {
        const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';
        const API_URL = BACKEND_URL ? `${BACKEND_URL}/api` : '/api';
        const response = await fetch(`${API_URL}/fcm/test-notification`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ token: this.token })
        });

        if (response.ok) {
          console.log('[FCM] Test notification sent');
          return true;
        } else {
          console.error('[FCM] Test notification failed');
          return false;
        }
      } catch (error) {
        console.error('[FCM] Error sending test notification:', error);
        return false;
      }
    }
    console.warn('[FCM] No token available for test notification');
    return false;
  }
}

const notificationService = new NotificationService();

export default notificationService;

export const {
  initializeForUser,
  testNotification,
  playNotificationSound,
  requestPermission
} = notificationService;
