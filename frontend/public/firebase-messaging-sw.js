// Firebase messaging service worker for background notifications
/* global importScripts, firebase, self, clients */

// Import Firebase scripts - must match installed package version
importScripts('https://www.gstatic.com/firebasejs/11.10.0/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/11.10.0/firebase-messaging-compat.js');

// Firebase configuration (must be hardcoded - SW cannot access process.env)
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

  return self.registration.showNotification(notificationTitle, notificationOptions);
});

// Handle notification click events
self.addEventListener('notificationclick', (event) => {
  console.log('[firebase-messaging-sw.js] Notification click received.');

  event.notification.close();

  if (event.action === 'close') {
    return;
  }

  const url = event.notification.data?.url || '/';
  
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
      for (const client of clientList) {
        if (client.url.includes(self.location.origin) && 'focus' in client) {
          client.focus();
          if (url !== '/') {
            client.navigate(url);
          }
          return;
        }
      }
      
      if (clients.openWindow) {
        return clients.openWindow(self.location.origin + url);
      }
    })
  );
});

// Service Worker activation
self.addEventListener('activate', (event) => {
  console.log('[firebase-messaging-sw.js] Service Worker activated');
  event.waitUntil(self.clients.claim());
});

// Service Worker installation  
self.addEventListener('install', (event) => {
  console.log('[firebase-messaging-sw.js] Service Worker installed');
  self.skipWaiting();
});
