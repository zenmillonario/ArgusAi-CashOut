// Service Worker for CashoutAI notifications
/* global self, caches, clients, fetch */

const CACHE_NAME = 'cashoutai-v1';
const urlsToCache = [
  '/',
  '/static/js/bundle.js',
  '/static/css/main.css',
  '/manifest.json'
];

// Install service worker
self.addEventListener('install', (event) => {
  console.log('Service Worker installing...');
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => {
        console.log('Opened cache');
        return cache.addAll(urlsToCache);
      })
  );
});

// Activate service worker
self.addEventListener('activate', (event) => {
  console.log('Service Worker activating...');
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheName !== CACHE_NAME) {
            console.log('Deleting old cache:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
});

// Fetch interceptor for offline support
self.addEventListener('fetch', (event) => {
  event.respondWith(
    caches.match(event.request)
      .then((response) => {
        // Return cached version or fetch from network
        return response || fetch(event.request);
      }
    )
  );
});

// Push notification listener
self.addEventListener('push', (event) => {
  console.log('Push message received:', event);
  
  const options = {
    body: 'You have a new admin message!',
    icon: 'https://i.imgur.com/ZPYCiyg.png',
    badge: 'https://i.imgur.com/ZPYCiyg.png',
    vibrate: [300, 200, 300, 200, 300],
    data: {
      dateOfArrival: Date.now(),
      primaryKey: 1
    },
    actions: [
      {
        action: 'view',
        title: 'View Message',
        icon: 'https://i.imgur.com/ZPYCiyg.png'
      },
      {
        action: 'close',
        title: 'Close',
        icon: 'https://i.imgur.com/ZPYCiyg.png'
      }
    ],
    tag: 'cashoutai-admin',
    renotify: true,
    requireInteraction: true,
    silent: false
  };

  if (event.data) {
    const data = event.data.json();
    options.body = data.message || options.body;
    options.title = data.title || '💰 CashoutAI - Admin Message';
    
    if (data.adminName) {
      options.body = `${data.adminName}: ${options.body}`;
    }
  }

  event.waitUntil(
    self.registration.showNotification('💰 CashoutAI - Admin Message', options)
  );
});

// Notification click handler
self.addEventListener('notificationclick', (event) => {
  console.log('Notification click received:', event);
  
  event.notification.close();
  
  if (event.action === 'view') {
    // Open the app
    event.waitUntil(
      clients.openWindow('/')
    );
  } else if (event.action === 'close') {
    // Just close the notification
    event.notification.close();
  } else {
    // Default action - open the app
    event.waitUntil(
      clients.openWindow('/')
    );
  }
});

// Background sync for offline message sending
self.addEventListener('sync', (event) => {
  console.log('Background sync:', event.tag);
  
  if (event.tag === 'admin-message-check') {
    event.waitUntil(checkForAdminMessages());
  }
});

// Check for new admin messages when app is in background
async function checkForAdminMessages() {
  try {
    const response = await fetch('/api/messages/admin/latest');
    if (response.ok) {
      const data = await response.json();
      if (data.hasNewAdminMessage) {
        self.registration.showNotification('💰 CashoutAI - New Admin Message', {
          body: data.message,
          icon: 'https://i.imgur.com/ZPYCiyg.png',
          badge: 'https://i.imgur.com/ZPYCiyg.png',
          vibrate: [300, 200, 300, 200, 300],
          tag: 'cashoutai-admin',
          requireInteraction: true
        });
      }
    }
  } catch (error) {
    console.error('Error checking for admin messages:', error);
  }
}

// Message listener for communication with main app
self.addEventListener('message', (event) => {
  console.log('Service Worker received message:', event.data);
  
  if (event.data && event.data.type === 'SHOW_ADMIN_NOTIFICATION') {
    const { title, message, adminName } = event.data;
    
    self.registration.showNotification(title || '💰 CashoutAI - Admin Message', {
      body: adminName ? `${adminName}: ${message}` : message,
      icon: 'https://i.imgur.com/ZPYCiyg.png',
      badge: 'https://i.imgur.com/ZPYCiyg.png',
      vibrate: [300, 200, 300, 200, 300],
      tag: 'cashoutai-admin',
      requireInteraction: true,
      silent: false
    });
  }
});