// Firebase integration for ArgusAI CashOut notifications
import { initializeApp } from 'firebase/app';
import { getMessaging, getToken, onMessage } from 'firebase/messaging';

// Your Firebase configuration
const firebaseConfig = {
  apiKey: "AIzaSyDXsZWHiHAhWxZz4TNmonxbG2RD2WNBoqU",
  authDomain: "cashoutai-notifications.firebaseapp.com",
  projectId: "cashoutai-notifications",
  storageBucket: "cashoutai-notifications.firebasestorage.app",
  messagingSenderId: "1077671941650",
  appId: "1:1077671941650:web:a48c3dce4bffa8e897aacb"
};

// VAPID key for push notifications
const VAPID_KEY = "BCFwFhta05moYQ1dkY6Q1YjWCkGoOOCopnT19IwCzMP62X7RTKIPXUSV4ZQvWAq93QNJKUpV_1yjt42htBcfLvg";

// Initialize Firebase
const app = initializeApp(firebaseConfig);
const messaging = getMessaging(app);

class NotificationService {
  constructor() {
    this.token = null;
    this.isSupported = this.checkSupport();
  }

  // Check if push notifications are supported
  checkSupport() {
    return 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window;
  }

  // Request notification permission
  async requestPermission() {
    if (!this.isSupported) {
      console.log('Push notifications not supported');
      return false;
    }

    try {
      const permission = await Notification.requestPermission();
      console.log('Notification permission:', permission);
      return permission === 'granted';
    } catch (error) {
      console.error('Error requesting notification permission:', error);
      return false;
    }
  }

  // Register service worker
  async registerServiceWorker() {
    if (!this.isSupported) return false;

    try {
      const registration = await navigator.serviceWorker.register('/firebase-messaging-sw.js');
      console.log('Service Worker registered:', registration);
      return registration;
    } catch (error) {
      console.error('Service Worker registration failed:', error);
      return false;
    }
  }

  // Get FCM token
  async getNotificationToken() {
    if (!this.isSupported) return null;

    try {
      // Register service worker first
      const registration = await this.registerServiceWorker();
      if (!registration) return null;

      // Request permission
      const hasPermission = await this.requestPermission();
      if (!hasPermission) return null;

      // Get token
      const token = await getToken(messaging, {
        vapidKey: VAPID_KEY,
        serviceWorkerRegistration: registration
      });

      if (token) {
        console.log('FCM Token:', token);
        this.token = token;
        return token;
      } else {
        console.log('No registration token available');
        return null;
      }
    } catch (error) {
      console.error('Error getting FCM token:', error);
      return null;
    }
  }

  // Send token to backend
  async sendTokenToBackend(token, userId) {
    try {
      const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';
      const API_URL = BACKEND_URL ? `${BACKEND_URL}/api` : '/api';
      const response = await fetch(`${API_URL}/fcm/register-token`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          token: token,
          user_id: userId
        })
      });

      if (response.ok) {
        console.log('Token registered with backend');
        return true;
      } else {
        console.error('Failed to register token with backend');
        return false;
      }
    } catch (error) {
      console.error('Error sending token to backend:', error);
      return false;
    }
  }

  // Initialize notifications for a user
  async initializeForUser(userId) {
    if (!this.isSupported) {
      console.log('Push notifications not supported');
      return false;
    }

    try {
      // Get FCM token
      const token = await this.getNotificationToken();
      if (!token) return false;

      // Send token to backend
      const success = await this.sendTokenToBackend(token, userId);
      if (!success) return false;

      // Listen for foreground messages
      this.setupForegroundListener();

      console.log('Notifications initialized successfully');
      return true;
    } catch (error) {
      console.error('Error initializing notifications:', error);
      return false;
    }
  }

  // Setup listener for foreground messages
  setupForegroundListener() {
    onMessage(messaging, (payload) => {
      console.log('Message received in foreground:', payload);

      // Play WhatsApp-like sound
      this.playNotificationSound();

      // Show custom notification or use browser's
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

        // Handle notification click
        notification.onclick = () => {
          window.focus();
          notification.close();
          // You can add custom logic here based on payload.data
        };

        // Auto-close after 5 seconds
        setTimeout(() => {
          notification.close();
        }, 5000);
      }
    });
  }

  // Play WhatsApp-like notification sound
  playNotificationSound() {
    try {
      // Create audio context
      const audioContext = new (window.AudioContext || window.webkitAudioContext)();
      
      // WhatsApp-like notification sound (double beep)
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
      
      // Play double beep like WhatsApp
      createBeep(800, 0.15).then(() => {
        createBeep(600, 0.15);
      });
      
    } catch (error) {
      console.log('Could not play notification sound:', error);
    }
  }

  // Test notification
  async testNotification() {
    if (this.token) {
      try {
        const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';
        const API_URL = BACKEND_URL ? `${BACKEND_URL}/api` : '/api';
        const response = await fetch(`${API_URL}/fcm/test-notification`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            token: this.token
          })
        });

        if (response.ok) {
          console.log('Test notification sent');
          return true;
        } else {
          console.error('Failed to send test notification');
          return false;
        }
      } catch (error) {
        console.error('Error sending test notification:', error);
        return false;
      }
    }
    return false;
  }
}

// Create global instance
const notificationService = new NotificationService();

// Export for use in React components
export default notificationService;

// Export individual functions
export const {
  initializeForUser,
  testNotification,
  playNotificationSound,
  requestPermission
} = notificationService;