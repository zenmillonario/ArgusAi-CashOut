// Firebase messaging service worker for background notifications
/* global importScripts, firebase, self, clients */

// Import Firebase scripts - Updated to match package.json version
importScripts('https://www.gstatic.com/firebasejs/11.10.0/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/11.10.0/firebase-messaging-compat.js');

// Your Firebase configuration
const firebaseConfig = {
  apiKey: "AIzaSyDXsZWHiHAhWxZz4TNmonxbG2RD2WNBoqU",
  authDomain: "cashoutai-notifications.firebaseapp.com",
  projectId: "cashoutai-notifications",
  storageBucket: "cashoutai-notifications.firebasestorage.app",
  messagingSenderId: "1077671941650",
  appId: "1:1077671941650:web:a48c3dce4bffa8e897aacb"
};

// Initialize Firebase
firebase.initializeApp(firebaseConfig);

// Get messaging instance
const messaging = firebase.messaging();

// Handle background messages when app is not in focus
messaging.onBackgroundMessage((payload) => {
  console.log('[firebase-messaging-sw.js] Received background message:', payload);
  
  const notificationTitle = payload.notification?.title || 'ArgusAI CashOut';
  const notificationOptions = {
    body: payload.notification?.body || 'New notification',
    icon: '/icon-192x192.png',
    badge: '/badge-72x72.png',
    tag: 'argusai-notification',
    renotify: true,
    requireInteraction: true,
    data: {
      url: payload.fcmOptions?.link || '/',
      ...payload.data
    },
    actions: [
      {
        action: 'open',
        title: 'Open ArgusAI',
        icon: '/icon-192x192.png'
      },
      {
        action: 'close', 
        title: 'Dismiss'
      }
    ]
  };

  // Play WhatsApp-like notification sound
  playNotificationSound();

  // Show notification
  return self.registration.showNotification(notificationTitle, notificationOptions);
});

// Handle notification click events
self.addEventListener('notificationclick', (event) => {
  console.log('[firebase-messaging-sw.js] Notification click received.');

  event.notification.close();

  if (event.action === 'close') {
    return;
  }

  // Open the app when notification is clicked
  const url = event.notification.data?.url || '/';
  
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
      // Check if app is already open
      for (const client of clientList) {
        if (client.url.includes(self.location.origin) && 'focus' in client) {
          client.focus();
          if (url !== '/') {
            client.navigate(url);
          }
          return;
        }
      }
      
      // Open new window if app is not open
      if (clients.openWindow) {
        return clients.openWindow(self.location.origin + url);
      }
    })
  );
});

// Play WhatsApp-like notification sound
function playNotificationSound() {
  try {
    // Create audio context for playing sound
    const audioContext = new (self.AudioContext || self.webkitAudioContext)();
    
    // WhatsApp-like notification sound (simple beep sequence)
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
    
    // Play WhatsApp-like double beep
    createBeep(800, 0.15).then(() => {
      createBeep(600, 0.15);
    });
    
  } catch (error) {
    console.log('Could not play notification sound:', error);
  }
}

// Handle push events (for additional sound control)
self.addEventListener('push', (event) => {
  if (event.data) {
    try {
      const payload = event.data.json();
      console.log('[firebase-messaging-sw.js] Push event received:', payload);
      
      // Play sound for push notifications
      playNotificationSound();
    } catch (error) {
      console.log('Error parsing push data:', error);
    }
  }
});

// Service Worker activation
self.addEventListener('activate', (event) => {
  console.log('[firebase-messaging-sw.js] Service Worker activated');
});

// Service Worker installation  
self.addEventListener('install', (event) => {
  console.log('[firebase-messaging-sw.js] Service Worker installed');
  self.skipWaiting();
});