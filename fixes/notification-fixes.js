// Push Notification Fixes - Only Admin Messages
// Add these functions to your App.js

// Enhanced WebSocket with Admin-Only Notifications
const setupWebSocketWithAdminNotifications = (currentUser, setIsConnected, setMessages, playNotificationSound) => {
  if (!currentUser || wsRef.current) return;

  const wsProtocol = BACKEND_URL.startsWith('https://') ? 'wss://' : 'ws://';
  const wsHost = BACKEND_URL.replace('https://', '').replace('http://', '');
  const wsUrl = `${wsProtocol}${wsHost}/ws/${currentUser.id}`;
  
  console.log('Connecting to WebSocket:', wsUrl);
  const ws = new WebSocket(wsUrl);
  
  ws.onopen = () => {
    setIsConnected(true);
    console.log('WebSocket connected successfully');
    ws.send(JSON.stringify({ type: 'heartbeat', message: 'ping' }));
  };

  ws.onmessage = (event) => {
    console.log('WebSocket message received:', event.data);
    setIsConnected(true);
    
    try {
      const data = JSON.parse(event.data);
      
      if (data.type === 'connection' || data.type === 'heartbeat') {
        setIsConnected(true);
        console.log('WebSocket connection confirmed');
      } else if (data.type === 'message') {
        setMessages(prev => [...prev, data.data]);
        
        // ONLY PLAY SOUND AND NOTIFY FOR ADMIN MESSAGES
        if (data.data.is_admin && currentUser.id !== data.data.user_id) {
          // Play sound notification
          playNotificationSound();
          
          // Show browser push notification
          if (Notification.permission === 'granted') {
            const notification = new Notification(`👑 Admin: ${data.data.username}`, {
              body: data.data.content.length > 100 ? data.data.content.substring(0, 100) + '...' : data.data.content,
              icon: data.data.avatar_url || '/favicon.ico',
              badge: 'https://i.imgur.com/ZPYCiyg.png',
              tag: 'admin-message',
              requireInteraction: true, // Keep notification visible until user interacts
              silent: false
            });
            
            // Auto close after 10 seconds
            setTimeout(() => notification.close(), 10000);
            
            // Handle notification click
            notification.onclick = () => {
              window.focus();
              notification.close();
            };
          }
          
          // Mobile vibration for admin messages (if supported)
          if (navigator.vibrate) {
            navigator.vibrate([200, 100, 200]); // Vibration pattern
          }
        }
      } else if (data.type === 'new_registration' && currentUser.is_admin) {
        // Admin notifications for new registrations
        if (Notification.permission === 'granted') {
          new Notification('🔔 New User Registration', {
            body: data.message,
            icon: 'https://i.imgur.com/ZPYCiyg.png',
            tag: 'admin-registration'
          });
        }
        loadPendingUsers();
      } else if (data.type === 'user_approval' && currentUser.is_admin) {
        if (Notification.permission === 'granted') {
          new Notification('✅ User Status Updated', {
            body: data.message,
            icon: 'https://i.imgur.com/ZPYCiyg.png',
            tag: 'admin-approval'
          });
        }
        loadPendingUsers();
      }
    } catch (error) {
      console.log('WebSocket message (raw):', event.data);
      setIsConnected(true);
    }
    
    // Send periodic heartbeat to keep connection alive
    setTimeout(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'heartbeat', message: 'ping' }));
      }
    }, 30000);
  };

  ws.onerror = (error) => {
    console.error('WebSocket error:', error);
    setIsConnected(false);
  };

  ws.onclose = (event) => {
    console.log('WebSocket closed:', event.code, event.reason);
    setIsConnected(false);
    wsRef.current = null;
    
    // Auto-reconnect after 3 seconds if not manual close
    if (event.code !== 1000 && currentUser) {
      setTimeout(() => {
        console.log('Attempting to reconnect WebSocket...');
        setupWebSocketWithAdminNotifications(currentUser, setIsConnected, setMessages, playNotificationSound);
      }, 3000);
    }
  };

  wsRef.current = ws;
  return ws;
};

// Enhanced notification sound with admin-specific tone
const playAdminNotificationSound = () => {
  try {
    const audioContext = new (window.AudioContext || window.webkitAudioContext)();
    
    // Create a more distinctive sound for admin messages
    const oscillator1 = audioContext.createOscillator();
    const oscillator2 = audioContext.createOscillator();
    const gainNode = audioContext.createGain();
    
    oscillator1.connect(gainNode);
    oscillator2.connect(gainNode);
    gainNode.connect(audioContext.destination);
    
    // Admin notification: Higher pitch, more urgent
    oscillator1.frequency.setValueAtTime(1000, audioContext.currentTime);
    oscillator1.frequency.setValueAtTime(800, audioContext.currentTime + 0.1);
    oscillator1.frequency.setValueAtTime(1200, audioContext.currentTime + 0.2);
    
    oscillator2.frequency.setValueAtTime(600, audioContext.currentTime);
    oscillator2.frequency.setValueAtTime(500, audioContext.currentTime + 0.1);
    oscillator2.frequency.setValueAtTime(700, audioContext.currentTime + 0.2);
    
    gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
    gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.8);
    
    oscillator1.start(audioContext.currentTime);
    oscillator1.stop(audioContext.currentTime + 0.8);
    oscillator2.start(audioContext.currentTime);
    oscillator2.stop(audioContext.currentTime + 0.8);
  } catch (error) {
    console.log('Audio not supported:', error);
  }
};

// Enhanced notification permission request
const requestNotificationPermission = async () => {
  if ('Notification' in window) {
    if (Notification.permission === 'default') {
      const permission = await Notification.requestPermission();
      if (permission === 'granted') {
        // Show test notification
        new Notification('🦚 CashOutAi Notifications Enabled', {
          body: 'You will now receive notifications when admins post messages',
          icon: 'https://i.imgur.com/ZPYCiyg.png',
          tag: 'notification-test'
        });
        return true;
      }
    }
    return Notification.permission === 'granted';
  }
  return false;
};

// Service Worker for background notifications (optional enhancement)
const registerServiceWorker = async () => {
  if ('serviceWorker' in navigator) {
    try {
      const registration = await navigator.serviceWorker.register('/sw.js');
      console.log('Service Worker registered:', registration);
      return registration;
    } catch (error) {
      console.log('Service Worker registration failed:', error);
    }
  }
};

// Check if notifications are supported and enabled
const checkNotificationSupport = () => {
  const support = {
    notifications: 'Notification' in window,
    serviceWorker: 'serviceWorker' in navigator,
    vibration: 'vibrate' in navigator,
    permission: Notification.permission
  };
  
  console.log('Notification support:', support);
  return support;
};

export {
  setupWebSocketWithAdminNotifications,
  playAdminNotificationSound,
  requestNotificationPermission,
  registerServiceWorker,
  checkNotificationSupport
};