import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import ChatTab from './ChatTab';
import NotificationsTab from './NotificationsTab';
import UserList from './UserList';
import PortfolioTab from './PortfolioTab';
import FavoritesTab from './FavoritesTab';
import AchievementsTab from './AchievementsTab';
import ProfileCustomization from './ProfileCustomization';
import XPProgressBar from './XPProgressBar';
import AssetAllocationWheel from './AssetAllocationWheel';
import LoadingScreen from './LoadingScreen';
import { formatPrice, formatPnL, formatCurrency } from './utils';
import notificationService from './firebase-config';
import './App.css';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

function App() {
  const [showLoadingScreen, setShowLoadingScreen] = useState(true);
  const [currentUser, setCurrentUser] = useState(null);
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [messages, setMessages] = useState([]);
  const [newMessage, setNewMessage] = useState('');
  const [isConnected, setIsConnected] = useState(false);
  const [connectionMode, setConnectionMode] = useState('disconnected'); // 'websocket', 'polling', 'disconnected'
  const [showLogin, setShowLogin] = useState(true);
  const [loginForm, setLoginForm] = useState({ username: '', email: '', password: '', real_name: '', membership_plan: '' });
  const [isRegistering, setIsRegistering] = useState(false);
  const [pendingUsers, setPendingUsers] = useState([]);
  const [allUsers, setAllUsers] = useState([]);
  const [showAdminPanel, setShowAdminPanel] = useState(false);
  const [activeTab, setActiveTab] = useState('chat');
  const [userTrades, setUserTrades] = useState([]);
  const [userPerformance, setUserPerformance] = useState(null);
  const [openPositions, setOpenPositions] = useState([]);
  const [favorites, setFavorites] = useState([]);
  const [isDarkTheme, setIsDarkTheme] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [showSearch, setShowSearch] = useState(false);
  const [filteredMessages, setFilteredMessages] = useState([]);
  const [showEditProfile, setShowEditProfile] = useState(false);
  const [showChangePassword, setShowChangePassword] = useState(false);
  const [showForgotPassword, setShowForgotPassword] = useState(false);
  const [resetPasswordForm, setResetPasswordForm] = useState({ email: '' });
  const [resetTokenForm, setResetTokenForm] = useState({ token: '', new_password: '', confirm_password: '' });
  const [editProfileForm, setEditProfileForm] = useState({
    username: '',
    email: '',
    real_name: '',
    screen_name: ''
  });
  const [passwordForm, setPasswordForm] = useState({
    current_password: '',
    new_password: '',
    confirm_password: ''
  });
  const [avatarFile, setAvatarFile] = useState(null);
  const [avatarPreview, setAvatarPreview] = useState(null);
  const [imageFile, setImageFile] = useState(null);
  const [imagePreview, setImagePreview] = useState(null);
  const [showMobileMenu, setShowMobileMenu] = useState(false);
  const [audioContext, setAudioContext] = useState(null);
  const [serviceWorker, setServiceWorker] = useState(null);
  const [pushSubscription, setPushSubscription] = useState(null);
  const [tradeForm, setTradeForm] = useState({
    symbol: '',
    action: 'BUY',
    quantity: '',
    price: '',
    notes: '',
    stop_loss: '',
    take_profit: ''
  });
  const [currentStockPrice, setCurrentStockPrice] = useState(null);
  const [priceLoading, setPriceLoading] = useState(false);
  const [replyToMessage, setReplyToMessage] = useState(null);
  const [notifications, setNotifications] = useState([]);
  const [messageReactions, setMessageReactions] = useState({});
  const [onlineUsers, setOnlineUsers] = useState([]);
  const [showUserList, setShowUserList] = useState(true);
  const [userXP, setUserXP] = useState({ experience_points: 0, level: 1 });
  const [showProfileCustomization, setShowProfileCustomization] = useState(false);
  const wsRef = useRef(null);
  const messagesEndRef = useRef(null);

  // Filter messages based on search query
  useEffect(() => {
    if (searchQuery.trim() === '') {
      setFilteredMessages(messages);
    } else {
      const filtered = messages.filter(message =>
        message.content.toLowerCase().includes(searchQuery.toLowerCase()) ||
        message.username.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (message.real_name && message.real_name.toLowerCase().includes(searchQuery.toLowerCase())) ||
        message.highlighted_tickers.some(ticker => 
          ticker.toLowerCase().includes(searchQuery.toLowerCase())
        )
      );
      setFilteredMessages(filtered);
    }
  }, [messages, searchQuery]);

  // Load saved user on app start
  useEffect(() => {
    const initializeUser = async () => {
      // Check if this is a request for the widget page
      if (window.location.pathname === '/cashoutai-button-widget.html') {
        // Redirect to the actual widget page
        window.location.href = '/cashoutai-button-widget.html';
        return;
      }
      
      const savedUser = localStorage.getItem('cashoutai_user');
      if (savedUser) {
        try {
          const user = JSON.parse(savedUser);
          // Check if session is still valid (not older than 24 hours)
          const sessionAge = user.session_created_at ? 
            (Date.now() - new Date(user.session_created_at).getTime()) / (1000 * 60 * 60) : 
            25; // Default to expired if no session timestamp
          
          if (sessionAge < 24 && user.active_session_id) {
            setCurrentUser(user);
            setShowLogin(false);
            
            // Initialize Firebase push notifications for saved user
            try {
              console.log('Initializing Firebase notifications for saved user:', user.id);
              const notificationSuccess = await notificationService.initializeForUser(user.id);
              if (notificationSuccess) {
                console.log('✅ Firebase notifications initialized successfully for saved user');
              } else {
                console.log('⚠️ Firebase notifications failed to initialize for saved user');
              }
            } catch (error) {
              console.error('Error initializing Firebase notifications for saved user:', error);
            }
          } else {
            // Session expired, clear storage
            localStorage.removeItem('cashoutai_user');
          }
        } catch (error) {
          console.error('Error loading saved user:', error);
          localStorage.removeItem('cashoutai_user');
        }
      }
      setIsLoading(false);
    };
    
    initializeUser();
  }, []);

  // Load theme preference
  useEffect(() => {
    const savedTheme = localStorage.getItem('cashoutai_theme');
    if (savedTheme) {
      setIsDarkTheme(savedTheme === 'dark');
    }
  }, []);

  // Load favorites
  useEffect(() => {
    if (currentUser) {
      const savedFavorites = localStorage.getItem(`cashoutai_favorites_${currentUser.id}`);
      if (savedFavorites) {
        setFavorites(JSON.parse(savedFavorites));
      }
    }
  }, [currentUser]);

  const toggleTheme = () => {
    const newTheme = !isDarkTheme;
    setIsDarkTheme(newTheme);
    localStorage.setItem('cashoutai_theme', newTheme ? 'dark' : 'light');
  };

  const addToFavorites = (symbol) => {
    if (!favorites.includes(symbol.toUpperCase())) {
      const newFavorites = [...favorites, symbol.toUpperCase()];
      setFavorites(newFavorites);
      localStorage.setItem(`cashoutai_favorites_${currentUser.id}`, JSON.stringify(newFavorites));
    }
  };

  const removeFromFavorites = (symbol) => {
    const newFavorites = favorites.filter(fav => fav !== symbol.toUpperCase());
    setFavorites(newFavorites);
    localStorage.setItem(`cashoutai_favorites_${currentUser.id}`, JSON.stringify(newFavorites));
  };

  // Initialize audio context after user interaction
  const initializeAudio = () => {
    if (!audioContext) {
      try {
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        setAudioContext(ctx);
        console.log('🔊 Audio context initialized');
      } catch (error) {
        console.error('Failed to initialize audio context:', error);
      }
    }
  };

  // Simple admin notification sound - no complex audio context
  const playSimpleAdminSound = () => {
    try {
      // Create a simple audio beep
      const audio = new Audio();
      audio.src = 'data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAAABAAABACAAAQCQAAAABAAEAGGV0YQoGAAAaFBUVFRUVFRUVFRUVFRUVFRUVFRUVFRUVFRUVFRUVFRUVFRUVFRUVFRUVFRUVFRUVFRUVFRUVFRUVFRUVFRUVFRUVFRUVFRU';
      audio.volume = 0.5;
      audio.play().then(() => {
        console.log('🔔 Simple admin sound played successfully');
      }).catch((error) => {
        console.log('Sound play failed:', error);
        // Fallback - try a different approach
        try {
          const context = new (window.AudioContext || window.webkitAudioContext)();
          const oscillator = context.createOscillator();
          const gainNode = context.createGain();
          
          oscillator.connect(gainNode);
          gainNode.connect(context.destination);
          
          oscillator.frequency.setValueAtTime(800, context.currentTime);
          gainNode.gain.setValueAtTime(0.3, context.currentTime);
          gainNode.gain.exponentialRampToValueAtTime(0.01, context.currentTime + 0.5);
          
          oscillator.start(context.currentTime);
          oscillator.stop(context.currentTime + 0.5);
          
          console.log('🔔 Fallback admin sound played');
        } catch (e) {
          console.log('All sound methods failed');
        }
      });
    } catch (error) {
      console.error('Error playing admin sound:', error);
    }
  };

  const playNotificationSound = async () => {
    try {
      // Try to initialize audio context if not already done
      if (!audioContext) {
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        setAudioContext(ctx);
        
        // Resume if suspended
        if (ctx.state === 'suspended') {
          await ctx.resume();
        }
        
        // Create sound with new context
        const oscillator = ctx.createOscillator();
        const gainNode = ctx.createGain();
        
        oscillator.connect(gainNode);
        gainNode.connect(ctx.destination);
        
        oscillator.frequency.setValueAtTime(800, ctx.currentTime);
        oscillator.frequency.setValueAtTime(1000, ctx.currentTime + 0.1);
        oscillator.frequency.setValueAtTime(800, ctx.currentTime + 0.2);
        oscillator.frequency.setValueAtTime(1200, ctx.currentTime + 0.3);
        
        gainNode.gain.setValueAtTime(0.3, ctx.currentTime);
        gainNode.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.6);
        
        oscillator.start(ctx.currentTime);
        oscillator.stop(ctx.currentTime + 0.6);
        
        console.log('🔔 Notification sound played successfully (new context)');
        return;
      }

      // Resume audio context if suspended
      if (audioContext.state === 'suspended') {
        await audioContext.resume();
      }

      const oscillator = audioContext.createOscillator();
      const gainNode = audioContext.createGain();
      
      oscillator.connect(gainNode);
      gainNode.connect(audioContext.destination);
      
      // Create a more attention-grabbing sound pattern
      oscillator.frequency.setValueAtTime(800, audioContext.currentTime);
      oscillator.frequency.setValueAtTime(1000, audioContext.currentTime + 0.1);
      oscillator.frequency.setValueAtTime(800, audioContext.currentTime + 0.2);
      oscillator.frequency.setValueAtTime(1200, audioContext.currentTime + 0.3);
      
      gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
      gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.6);
      
      oscillator.start(audioContext.currentTime);
      oscillator.stop(audioContext.currentTime + 0.6);
      
      console.log('🔔 Notification sound played successfully');
    } catch (error) {
      console.error('Error playing notification sound:', error);
      // Fallback: try HTML5 audio
      try {
        const audio = new Audio();
        audio.src = 'data:audio/wav;base64,UklGRtoBAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YdYBAAC4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4uLi4';
        audio.volume = 0.3;
        await audio.play();
        console.log('🔔 Fallback notification sound played');
      } catch (e) {
        console.log('All audio methods failed:', e);
      }
    }
  };

  const showServiceWorkerNotification = async (title, message, adminName = null) => {
    try {
      if ('serviceWorker' in navigator) {
        const registration = await navigator.serviceWorker.ready;
        
        await registration.showNotification(title, {
          body: adminName ? `${adminName}: ${message}` : message,
          icon: 'https://i.imgur.com/ZPYCiyg.png',
          badge: 'https://i.imgur.com/ZPYCiyg.png',
          vibrate: [300, 200, 300, 200, 300],
          tag: 'cashoutai-admin',
          requireInteraction: true,
          silent: false,
          actions: [
            {
              action: 'view',
              title: 'View Message'
            },
            {
              action: 'close',
              title: 'Close'
            }
          ],
          data: {
            url: '/',
            timestamp: Date.now()
          }
        });
        
        console.log('🔔 Service Worker notification shown with actions');
        return true;
      }
    } catch (error) {
      console.error('Service Worker notification failed:', error);
    }
    return false;
  };

  const showBrowserNotification = async (title, message, isAdmin = false) => {
    // Check if notifications are supported
    if (!("Notification" in window)) {
      console.log("This browser does not support notifications");
      return;
    }

    // Only show notifications for admin messages
    if (!isAdmin) {
      return;
    }

    // Check notification permission
    if (Notification.permission === "granted") {
      
      // Try to use Service Worker for rich notifications first
      const swSuccess = await showServiceWorkerNotification(
        title, 
        message, 
        currentUser?.real_name || currentUser?.username
      );
      
      if (swSuccess) {
        return; // Service Worker notification successful
      }
      
      // Fallback to basic notification without actions
      console.log('Using basic notification fallback');
      const notification = new Notification(title, {
        body: message,
        icon: "https://i.imgur.com/ZPYCiyg.png",
        badge: "https://i.imgur.com/ZPYCiyg.png",
        tag: "cashoutai-admin",
        requireInteraction: true,
        silent: false,
        vibrate: [300, 200, 300, 200, 300]
        // NOTE: No actions here - only supported in Service Worker notifications
      });

      // Auto close after 8 seconds (longer for admin messages)
      setTimeout(() => {
        notification.close();
      }, 8000);

      // Handle notification clicks
      notification.onclick = () => {
        window.focus();
        notification.close();
      };

      console.log('🔔 Basic browser notification shown (fallback)');
      
    } else if (Notification.permission !== "denied") {
      // Request permission
      const permission = await Notification.requestPermission();
      if (permission === "granted") {
        showBrowserNotification(title, message, isAdmin);
      }
    }
  };

  // Reset document title when user focuses on the app
  useEffect(() => {
    const handleFocus = () => {
      document.title = '💰 CashoutAI - Trading Platform';
    };

    const handleBlur = () => {
      // Keep title as is when user leaves the app
    };

    window.addEventListener('focus', handleFocus);
    window.addEventListener('blur', handleBlur);

    return () => {
      window.removeEventListener('focus', handleFocus);
      window.removeEventListener('blur', handleBlur);
    };
  }, []);

  // Initialize audio on first user interaction
  useEffect(() => {
    const handleFirstInteraction = () => {
      initializeAudio();
      document.removeEventListener('click', handleFirstInteraction);
      document.removeEventListener('keydown', handleFirstInteraction);
      document.removeEventListener('touchstart', handleFirstInteraction);
    };

    document.addEventListener('click', handleFirstInteraction);
    document.addEventListener('keydown', handleFirstInteraction);
    document.addEventListener('touchstart', handleFirstInteraction);

    return () => {
      document.removeEventListener('click', handleFirstInteraction);
      document.removeEventListener('keydown', handleFirstInteraction);
      document.removeEventListener('touchstart', handleFirstInteraction);
    };
  }, []);

  // Request notification permission on app load
  useEffect(() => {
    if ("Notification" in window && Notification.permission === "default") {
      Notification.requestPermission().then((permission) => {
        console.log('Notification permission:', permission);
      });
    }
  }, []);

  // Service Worker registration and push notification setup
  useEffect(() => {
    const registerServiceWorker = async () => {
      if ('serviceWorker' in navigator) {
        try {
          const registration = await navigator.serviceWorker.register('/firebase-messaging-sw.js');
          console.log('Service Worker registered successfully:', registration);
          
          // Wait for service worker to be ready
          await navigator.serviceWorker.ready;
          
          // Get the active service worker
          const worker = registration.active || registration.waiting || registration.installing;
          if (worker) {
            setServiceWorker(worker);
            console.log('Service Worker set:', worker.state);
          }
          
          // Listen for service worker state changes
          if (registration.installing) {
            registration.installing.addEventListener('statechange', (e) => {
              if (e.target.state === 'activated') {
                setServiceWorker(e.target);
                console.log('Service Worker activated');
              }
            });
          }
          
          // Listen for service worker updates
          registration.addEventListener('updatefound', () => {
            const newWorker = registration.installing;
            if (newWorker) {
              newWorker.addEventListener('statechange', (e) => {
                if (e.target.state === 'activated') {
                  setServiceWorker(e.target);
                  console.log('Service Worker updated and activated');
                }
              });
            }
          });
          
          // Request notification permission if not already granted
          if (Notification.permission === 'default') {
            const permission = await Notification.requestPermission();
            console.log('Notification permission result:', permission);
          }
          
          // Set up push notifications if supported
          if ('PushManager' in window && registration.pushManager) {
            try {
              const subscription = await registration.pushManager.getSubscription();
              if (subscription) {
                setPushSubscription(subscription);
                console.log('Existing push subscription found');
              } else {
                // Create new subscription (you would need VAPID keys for production)
                console.log('No existing push subscription found');
              }
            } catch (error) {
              console.error('Push subscription error:', error);
            }
          }
          
        } catch (error) {
          console.error('Service Worker registration failed:', error);
        }
      }
    };

    registerServiceWorker();
  }, []);

  // Background sync for admin message checking
  useEffect(() => {
    if (serviceWorker && currentUser) {
      const handleVisibilityChange = () => {
        if (document.hidden) {
          // App went to background, register background sync
          if ('serviceWorker' in navigator && 'sync' in window.ServiceWorkerRegistration.prototype) {
            navigator.serviceWorker.ready.then((registration) => {
              return registration.sync.register('admin-message-check');
            }).catch((error) => {
              console.error('Background sync registration failed:', error);
            });
          }
        }
      };

      document.addEventListener('visibilitychange', handleVisibilityChange);
      
      return () => {
        document.removeEventListener('visibilitychange', handleVisibilityChange);
      };
    }
  }, [serviceWorker, currentUser]);

  const addReaction = (messageId, reaction) => {
    console.log(`Adding reaction ${reaction} to message ${messageId}`);
    
    // Find the message to get its author
    const message = messages.find(msg => msg.id === messageId);
    if (!message) return;
    
    setMessageReactions(prev => {
      const messageReacts = prev[messageId] || {};
      const currentCount = messageReacts[reaction] || 0;
      
      // Create notification if it's someone else's message
      if (message.user_id !== currentUser?.id) {
        const newNotification = {
          type: 'reaction',
          from: currentUser?.screen_name || currentUser?.username,
          to: message.user_id,
          originalMessage: message.content_type === 'image' ? '📷 Image' : message.content.substring(0, 50),
          reaction: reaction,
          timestamp: new Date().toLocaleTimeString(),
          messageId: messageId
        };
        
        setNotifications(prev => [newNotification, ...prev.slice(0, 49)]); // Keep last 50 notifications
      }
      
      return {
        ...prev,
        [messageId]: {
          ...messageReacts,
          [reaction]: currentCount + 1
        }
      };
    });
  };

  const scrollToBottom = () => {
    try {
      // Add a small delay and check if element exists to prevent mobile scroll issues
      setTimeout(() => {
        if (messagesEndRef.current && !document.hidden) {
          messagesEndRef.current.scrollIntoView({ 
            behavior: "smooth",
            block: "nearest" // Less aggressive scrolling
          });
        }
      }, 100);
    } catch (error) {
      console.log('Scroll error (non-critical):', error);
    }
  };

  // Fetch stock price when symbol changes
  const fetchCurrentPrice = async (symbol) => {
    if (!symbol || symbol.length < 1) {
      setCurrentStockPrice(null);
      return;
    }
    
    try {
      setPriceLoading(true);
      const response = await axios.get(`${API}/stock/${symbol}`);
      setCurrentStockPrice(response.data.price);
      // Auto-fill price in form
      setTradeForm(prev => ({
        ...prev,
        price: response.data.price.toString()
      }));
    } catch (error) {
      console.error('Error fetching stock price:', error);
      setCurrentStockPrice(null);
    } finally {
      setPriceLoading(false);
    }
  };

  // Auto-fetch price when symbol changes
  useEffect(() => {
    const debounceTimer = setTimeout(() => {
      if (tradeForm.symbol && tradeForm.symbol.length >= 1) {
        fetchCurrentPrice(tradeForm.symbol);
      }
    }, 500); // Debounce for 500ms

    return () => clearTimeout(debounceTimer);
  }, [tradeForm.symbol]);

  // Auto-scroll when messages change AND on initial load - with mobile optimization
  useEffect(() => {
    // Only auto-scroll if user is actively viewing chat tab and app is visible
    if (activeTab === 'chat' && !document.hidden && filteredMessages.length > 0) {
      scrollToBottom();
    }
  }, [filteredMessages, activeTab]);

  // WebSocket connection
  useEffect(() => {
    if (currentUser && !wsRef.current && currentUser.active_session_id) {
      // Build WebSocket URL correctly for different deployment environments
      let wsUrl;
      
      if (BACKEND_URL.includes('onrender.com')) {
        // For Render deployment, use the backend URL directly with /api prefix
        const wsProtocol = BACKEND_URL.startsWith('https://') ? 'wss://' : 'ws://';
        const wsHost = BACKEND_URL.replace('https://', '').replace('http://', '');
        wsUrl = `${wsProtocol}${wsHost}/api/ws/${currentUser.id}/${currentUser.active_session_id}`;
      } else {
        // For other deployments (Emergent, etc.) with /api prefix
        const wsProtocol = BACKEND_URL.startsWith('https://') ? 'wss://' : 'ws://';
        const wsHost = BACKEND_URL.replace('https://', '').replace('http://', '');
        wsUrl = `${wsProtocol}${wsHost}/api/ws/${currentUser.id}/${currentUser.active_session_id}`;
      }
      
      console.log('Connecting to WebSocket:', wsUrl);
      const ws = new WebSocket(wsUrl);
      
      ws.onopen = () => {
        setIsConnected(true);
        setConnectionMode('websocket');
        console.log('WebSocket connected successfully');
        // Send a heartbeat to establish connection
        ws.send(JSON.stringify({ type: 'heartbeat', message: 'Hello' }));
      };
      
      ws.onmessage = async (event) => {
        try {
          const data = JSON.parse(event.data);
          console.log('WebSocket message received:', data);
          
          if (data.type === 'session_invalidated') {
            // Session has been invalidated by login from another location
            alert('🔒 Your session has been terminated due to login from another location.');
            logout();
          } else if (data.type === 'message') {
            const message = data.data;
            setMessages(prev => [...prev, message]);
            
            console.log('📝 Message received:', {
              content: message.content.substring(0, 50),
              is_admin: message.is_admin,
              user_id: message.user_id,
              current_user_id: currentUser.id,
              sender: message.screen_name || message.username
            });
            
            // Check if this is an admin message and current user is not the sender
            if (message.is_admin && message.user_id !== currentUser.id) {
              console.log('🔔 ADMIN MESSAGE DETECTED!');
              console.log('- From:', message.screen_name || message.username);
              console.log('- Message:', message.content.substring(0, 100));
              
              // Play simple admin sound
              playSimpleAdminSound();
              
              // Visual notification in app title
              setTimeout(() => {
                if (document.hidden) {
                  document.title = `🔔 New Admin Message - CashoutAI`;
                }
              }, 100);
            }
          } else if (data.type === 'admin_notification') {
            // New admin notification handling
            console.log('🔔 Admin notification received:', data);
            
            playSimpleAdminSound();
            
          } else if (data.type === 'user_joined') {
            // User joined chat
            setOnlineUsers(prev => {
              if (!prev.find(user => user.id === data.user.id)) {
                return [...prev, data.user];
              }
              return prev;
            });
          } else if (data.type === 'user_left') {
            // User left chat
            setOnlineUsers(prev => prev.filter(user => user.id !== data.user_id));
          } else if (data.type === 'online_users') {
            // Initial list of online users
            setOnlineUsers(data.users || []);
          } else if (data.type === 'admin_message') {
            // Legacy admin message handling
            console.log('🔔 Legacy admin message notification');
            playSimpleAdminSound();
            
            // Visual notification in app
            if (document.hidden) {
              document.title = `🔔 ${data.admin_real_name || data.admin_username} - CashoutAI`;
            }
          }
        } catch (e) {
          console.error('Error parsing WebSocket message:', e);
        }
      };
      
      ws.onclose = (event) => {
        setIsConnected(false);
        setConnectionMode('disconnected');
        console.log('WebSocket disconnected', event);
        wsRef.current = null;
        
        // Handle session invalidation close codes
        if (event.code === 4002 || event.code === 4003) {
          alert('🔒 Your session has expired or been invalidated. Please log in again.');
          logout();
        }
      };
      
      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        setIsConnected(false);
        
        // Add fallback mechanism for session validation when WebSocket fails
        if (currentUser?.active_session_id) {
          console.log('WebSocket failed, falling back to polling mode...');
          
          // Set connected status to show as "Polling" instead of "Disconnected"
          setTimeout(() => {
            if (!wsRef.current || wsRef.current.type === 'polling') {
              setIsConnected(true); // Show as connected since polling works
              setConnectionMode('polling');
            }
          }, 1000);
          
          const sessionCheckInterval = setInterval(async () => {
            try {
              const response = await axios.get(`${API}/users/${currentUser.id}/session-status?session_id=${currentUser.active_session_id}`);
              if (!response.data.valid) {
                console.log('Session invalidated via polling, logging out...');
                alert('🔒 Your session has been terminated due to login from another location.');
                logout();
                clearInterval(sessionCheckInterval);
              }
            } catch (error) {
              console.error('Session validation error:', error);
              setIsConnected(false);
              setConnectionMode('disconnected');
            }
          }, 10000); // Check every 10 seconds
          
          // Also check for new messages periodically when WebSocket is down
          const messageCheckInterval = setInterval(async () => {
            try {
              const response = await axios.get(`${API}/messages?limit=10`);
              const latestMessages = response.data;
              
              setMessages(prev => {
                const existingIds = prev.map(m => m.id);
                const newMessages = latestMessages.filter(m => !existingIds.includes(m.id));
                
                // Check for admin messages in new messages
                newMessages.forEach(message => {
                  if (message.is_admin && message.user_id !== currentUser.id) {
                    console.log('🔔 Admin message detected via polling:', message.screen_name || message.username);
                    playSimpleAdminSound();
                  }
                });
                
                return [...prev, ...newMessages];
              });
            } catch (error) {
              console.error('Message polling error:', error);
            }
          }, 8000); // Check for new messages every 8 seconds
          
          // Store interval IDs to clean up later
          wsRef.current = { 
            type: 'polling', 
            sessionInterval: sessionCheckInterval,
            messageInterval: messageCheckInterval
          };
        }
      };
      
      wsRef.current = ws;
    }
    
    return () => {
      if (wsRef.current) {
        if (wsRef.current.type === 'polling') {
          clearInterval(wsRef.current.sessionInterval);
          clearInterval(wsRef.current.messageInterval);
        } else {
          wsRef.current.close();
        }
        wsRef.current = null;
      }
    };
  }, [currentUser]);

  const loadMessages = async () => {
    try {
      const response = await axios.get(`${API}/messages`);
      setMessages(response.data);
    } catch (error) {
      console.error('Error loading messages:', error);
    }
  };

  const loadPendingUsers = async () => {
    if (currentUser?.is_admin) {
      try {
        const response = await axios.get(`${API}/users/pending`);
        setPendingUsers(response.data);
      } catch (error) {
        console.error('Error loading pending users:', error);
      }
    }
  };

  const loadAllUsers = async () => {
    if (currentUser?.is_admin) {
      try {
        const response = await axios.get(`${API}/users`);
        setAllUsers(response.data);
      } catch (error) {
        console.error('Error loading all users:', error);
      }
    }
  };

  const loadUserData = async () => {
    if (!currentUser) return;
    
    try {
      // Load trades
      const tradesResponse = await axios.get(`${API}/trades/${currentUser.id}`);
      setUserTrades(tradesResponse.data);
      
      // Load performance
      const performanceResponse = await axios.get(`${API}/users/${currentUser.id}/performance`);
      setUserPerformance(performanceResponse.data);
      
      // Load positions
      const positionsResponse = await axios.get(`${API}/positions/${currentUser.id}`);
      setOpenPositions(positionsResponse.data);
    } catch (error) {
      console.error('Error loading user data:', error);
    }
  };

  useEffect(() => {
    if (currentUser) {
      loadMessages();
      loadUserData();
      loadPendingUsers();
      loadAllUsers();
      fetchUserXPData(); // Fetch XP data when user loads
    }
  }, [currentUser]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    
    try {
      if (isRegistering) {
        // Registration
        const response = await axios.post(`${API}/users/register`, {
          username: loginForm.username,
          email: loginForm.email,
          real_name: loginForm.real_name,
          membership_plan: loginForm.membership_plan,
          password: loginForm.password
        });
        
        alert('Registration successful! Please wait for admin approval. You will be approved within 5 minutes.');
        setIsRegistering(false);
        setLoginForm({ username: '', email: '', password: '', real_name: '', membership_plan: '' });
      } else {
        // Login
        const response = await axios.post(`${API}/users/login`, {
          username: loginForm.username,
          password: loginForm.password
        });
        
        setCurrentUser(response.data);
        setShowLogin(false);
        setLoginForm({ username: '', email: '', password: '', real_name: '', membership_plan: '' });
        
        // Save user to localStorage for persistence
        localStorage.setItem('cashoutai_user', JSON.stringify(response.data));
        
        // Initialize Firebase push notifications
        try {
          console.log('Initializing Firebase notifications for user:', response.data.id);
          const notificationSuccess = await notificationService.initializeForUser(response.data.id);
          if (notificationSuccess) {
            console.log('✅ Firebase notifications initialized successfully');
          } else {
            console.log('⚠️ Firebase notifications failed to initialize (may not be supported)');
          }
        } catch (error) {
          console.error('Error initializing Firebase notifications:', error);
        }
      }
    } catch (error) {
      console.error('Authentication error:', error);
      const errorMessage = error.response?.data?.detail || 'An error occurred during authentication';
      setError(errorMessage);
    }
  };

  const handleApproval = async (userId, approved) => {
    try {
      await axios.post(`${API}/users/approve`, {
        user_id: userId,
        approved: approved,
        admin_id: currentUser.id,
        role: "member"
      });
      
      // Reload pending users
      loadPendingUsers();
      loadAllUsers();
      
      alert(`User ${approved ? 'approved' : 'rejected'} successfully`);
    } catch (error) {
      alert(error.response?.data?.detail || 'Error processing approval');
    }
  };

  const handleUserRoleChange = async (userId, newRole) => {
    try {
      await axios.post(`${API}/users/change-role`, {
        user_id: userId,
        new_role: newRole,
        admin_id: currentUser.id
      });
      
      loadAllUsers();
      alert('User role updated successfully');
    } catch (error) {
      alert(error.response?.data?.detail || 'Error updating user role');
    }
  };

  const handleUserRemoval = async (userId) => {
    if (!window.confirm('Are you sure you want to remove this user?')) return;
    
    try {
      await axios.delete(`${API}/users/${userId}?admin_id=${currentUser.id}`);
      loadAllUsers();
      alert('User removed successfully');
    } catch (error) {
      alert(error.response?.data?.detail || 'Error removing user');
    }
  };

  const sendMessage = async (e) => {
    e.preventDefault();
    
    // Check if we have an image to send
    if (imageFile && imagePreview) {
      try {
        console.log('Sending image message...');
        await axios.post(`${API}/messages`, {
          content: imagePreview, // Send the base64 data URL
          content_type: "image",
          user_id: currentUser.id,
          reply_to_id: replyToMessage?.id || null
        });
        
        // Create notification for reply
        if (replyToMessage && replyToMessage.user_id !== currentUser?.id) {
          const newNotification = {
            type: 'reply',
            from: currentUser?.screen_name || currentUser?.username,
            to: replyToMessage.user_id,
            originalMessage: replyToMessage.content_type === 'image' ? '📷 Image' : replyToMessage.content.substring(0, 50),
            replyMessage: '📷 Image',
            replyImage: imagePreview,
            timestamp: new Date().toLocaleTimeString(),
            messageId: replyToMessage.id
          };
          
          setNotifications(prev => [newNotification, ...prev.slice(0, 49)]);
        }
        
        // Clear image and reply after sending
        setImageFile(null);
        setImagePreview(null);
        setReplyToMessage(null);
        console.log('Image message sent successfully');
      } catch (error) {
        console.error('Error sending image:', error);
        alert('Error sending image');
      }
      return;
    }
    
    // Send text message
    if (!newMessage.trim()) return;

    try {
      console.log('Sending text message...');
      await axios.post(`${API}/messages`, {
        content: newMessage,
        content_type: "text",
        user_id: currentUser.id,
        reply_to_id: replyToMessage?.id || null
      });
      
      // Create notification for reply
      if (replyToMessage && replyToMessage.user_id !== currentUser?.id) {
        const newNotification = {
          type: 'reply',
          from: currentUser?.screen_name || currentUser?.username,
          to: replyToMessage.user_id,
          originalMessage: replyToMessage.content_type === 'image' ? '📷 Image' : replyToMessage.content.substring(0, 50),
          replyMessage: newMessage.substring(0, 100),
          timestamp: new Date().toLocaleTimeString(),
          messageId: replyToMessage.id
        };
        
        setNotifications(prev => [newNotification, ...prev.slice(0, 49)]);
      }
      
      setNewMessage('');
      setReplyToMessage(null); // Clear reply after sending
      console.log('Text message sent successfully');
    } catch (error) {
      console.error('Error sending message:', error);
      alert('Error sending message');
    }
  };

  const submitTrade = async (e) => {
    e.preventDefault();
    
    try {
      await axios.post(`${API}/trades?user_id=${currentUser.id}`, {
        symbol: tradeForm.symbol,
        action: tradeForm.action,
        quantity: parseInt(tradeForm.quantity),
        price: parseFloat(tradeForm.price),
        notes: tradeForm.notes,
        stop_loss: tradeForm.stop_loss ? parseFloat(tradeForm.stop_loss) : null,
        take_profit: tradeForm.take_profit ? parseFloat(tradeForm.take_profit) : null
      });
      
      // Reset form
      setTradeForm({
        symbol: '',
        action: 'BUY',
        quantity: '',
        price: '',
        notes: '',
        stop_loss: '',
        take_profit: ''
      });
      
      // Reload user data
      loadUserData();
      
      alert('Trade recorded successfully!');
    } catch (error) {
      console.error('Error submitting trade:', error);
      alert('Error submitting trade');
    }
  };

  const closePosition = async (positionId, symbol) => {
    if (!window.confirm(`Close position for ${symbol}?`)) return;
    
    try {
      const response = await axios.post(`${API}/positions/${positionId}/close?user_id=${currentUser.id}`);
      alert(`Position closed. P&L: $${response.data.realized_pnl}`);
      loadUserData();
    } catch (error) {
      console.error('Error closing position:', error);
      alert('Error closing position');
    }
  };

  const handlePositionAction = async (positionId, action, quantity = null, price = null) => {
    try {
      const response = await axios.post(`${API}/positions/${positionId}/action?user_id=${currentUser.id}`, {
        action: action,
        quantity: quantity,
        price: price
      });
      
      alert(response.data.message);
      loadUserData();
    } catch (error) {
      console.error('Error with position action:', error);
      alert('Error processing action');
    }
  };

  const fetchAllUsers = async () => {
    try {
      const response = await axios.get(`${API}/all-users`);
      setAllUsers(response.data.users || []);
    } catch (error) {
      console.error('Error fetching all users:', error);
    }
  };

  const fetchUserXPData = async () => {
    try {
      if (currentUser?.id) {
        const response = await axios.get(`${API}/api/users/${currentUser.id}/profile`);
        setUserXP({
          experience_points: response.data.experience_points || 0,
          level: response.data.level || 1
        });
      }
    } catch (error) {
      console.error('Error fetching user XP data:', error);
    }
  };

  const formatMessageContent = (content, tickers) => {
    let formattedContent = content;
    
    // Highlight stock tickers
    tickers.forEach(ticker => {
      const regex = new RegExp(`\\$${ticker}`, 'gi');
      formattedContent = formattedContent.replace(regex, `<span class="ticker-highlight">$${ticker}</span>`);
    });
    
    return formattedContent;
  };

  const openEditProfile = () => {
    setEditProfileForm({
      username: currentUser.username,
      email: currentUser.email,
      real_name: currentUser.real_name || '',
      screen_name: currentUser.screen_name || ''
    });
    setShowEditProfile(true);
  };

  const handleFileSelect = (e) => {
    const file = e.target.files[0];
    if (file) {
      setAvatarFile(file);
      
      // Create preview
      const reader = new FileReader();
      reader.onload = (e) => {
        setAvatarPreview(e.target.result);
      };
      reader.readAsDataURL(file);
    }
  };

  const uploadAvatarFile = async (file) => {
    try {
      const formData = new FormData();
      formData.append('file', file);
      
      const response = await axios.post(`${API}/users/${currentUser.id}/avatar-upload`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      });
      
      // Update current user with new avatar
      setCurrentUser(prev => ({
        ...prev,
        avatar_url: response.data.avatar_url
      }));
      
      setAvatarFile(null);
      setAvatarPreview(null);
      
      alert('Profile picture updated successfully!');
    } catch (error) {
      console.error('Error uploading avatar:', error);
      alert('Error uploading profile picture');
    }
  };

  const updateProfile = async (e) => {
    e.preventDefault();
    
    try {
      const response = await axios.put(`${API}/users/${currentUser.id}/profile`, editProfileForm);
      
      setCurrentUser(response.data);
      setShowEditProfile(false);
      
      alert('Profile updated successfully!');
    } catch (error) {
      console.error('Error updating profile:', error);
      alert(error.response?.data?.detail || 'Error updating profile');
    }
  };

  const changePassword = async (e) => {
    e.preventDefault();
    
    if (passwordForm.new_password !== passwordForm.confirm_password) {
      alert('New passwords do not match');
      return;
    }
    
    try {
      await axios.post(`${API}/users/change-password?user_id=${currentUser.id}`, {
        current_password: passwordForm.current_password,
        new_password: passwordForm.new_password
      });
      
      setShowChangePassword(false);
      setPasswordForm({
        current_password: '',
        new_password: '',
        confirm_password: ''
      });
      
      alert('Password changed successfully!');
    } catch (error) {
      console.error('Error changing password:', error);
      alert(error.response?.data?.detail || 'Error changing password');
    }
  };

  const requestPasswordReset = async (e) => {
    e.preventDefault();
    
    try {
      await axios.post(`${API}/users/reset-password-request`, {
        email: resetPasswordForm.email
      });
      
      alert('If an account with that email exists, you will receive a password reset link.');
      setShowForgotPassword(false);
      setResetPasswordForm({ email: '' });
    } catch (error) {
      console.error('Error requesting password reset:', error);
      alert('Error requesting password reset. Please try again.');
    }
  };

  const confirmPasswordReset = async (e) => {
    e.preventDefault();
    
    if (resetTokenForm.new_password !== resetTokenForm.confirm_password) {
      alert('New passwords do not match');
      return;
    }
    
    try {
      await axios.post(`${API}/users/reset-password-confirm`, {
        token: resetTokenForm.token,
        new_password: resetTokenForm.new_password
      });
      
      alert('Password reset successfully! You can now log in with your new password.');
      setResetTokenForm({ token: '', new_password: '', confirm_password: '' });
      // Could redirect to login or close modal here
    } catch (error) {
      console.error('Error resetting password:', error);
      alert(error.response?.data?.detail || 'Error resetting password');
    }
  };

  const logout = async () => {
    try {
      await axios.post(`${API}/users/logout?user_id=${currentUser.id}`);
    } catch (error) {
      console.error('Error during logout:', error);
    }
    
    // Clear persisted user data
    localStorage.removeItem('cashoutai_user');
    
    setCurrentUser(null);
    setShowLogin(true);
    setMessages([]);
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
  };

  // Show loading screen while checking authentication
  if (isLoading) {
    return (
      <div className={`min-h-screen flex items-center justify-center ${isDarkTheme ? 'bg-gradient-to-br from-gray-900 via-gray-800 to-black' : 'bg-gradient-to-br from-blue-50 via-white to-indigo-50'}`}>
        <div className="text-center">
          <div className="w-16 h-16 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
          <h2 className={`text-xl font-semibold ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
            Loading CashoutAI...
          </h2>
          <p className={`mt-2 ${isDarkTheme ? 'text-gray-300' : 'text-gray-600'}`}>
            Trade Together, Win Together
          </p>
        </div>
      </div>
    );
  }

  // If showing loading screen, return early with loading screen
  if (showLoadingScreen) {
    return (
      <LoadingScreen 
        onComplete={() => setShowLoadingScreen(false)}
        isDarkTheme={isDarkTheme}
      />
    );
  }

  if (showLogin) {
    return (
      <div className={`min-h-screen ${isDarkTheme ? 'bg-gradient-to-br from-gray-900 via-gray-800 to-black' : 'bg-gradient-to-br from-blue-50 via-white to-indigo-50'}`}>
        <div className="flex items-center justify-center min-h-screen p-4">
          <div className={`w-full max-w-md backdrop-blur-lg rounded-2xl border p-8 ${
            isDarkTheme 
              ? 'bg-white/10 border-white/20' 
              : 'bg-white/90 border-gray-200 shadow-xl'
          }`}>
            <div className="text-center mb-8">
              {/* Team Logo */}
              <div className="flex justify-center mb-6">
                <div className="w-32 h-32 rounded-xl overflow-hidden border-4 border-blue-500/30 shadow-2xl bg-gradient-to-br from-blue-900 to-purple-900">
                  <img 
                    src="https://i.imgur.com/ZPYCiyg.png" 
                    alt="CashoutAI Team Logo" 
                    className="w-full h-full object-cover"
                    onError={(e) => {
                      e.target.style.display = 'none';
                      e.target.nextSibling.style.display = 'flex';
                    }}
                  />
                  <div className="w-full h-full bg-gradient-to-br from-blue-600 to-purple-600 flex items-center justify-center text-white font-bold text-4xl hidden">
                    💰
                  </div>
                </div>
              </div>
              
              <h1 className={`text-3xl font-bold ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
                💰 CashoutAI
              </h1>
              <p className={`mt-2 ${isDarkTheme ? 'text-gray-300' : 'text-gray-600'}`}>
                Trading Community Chat
              </p>
              <p className={`text-lg font-semibold mt-3 bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent`}>
                "Trade Together, Win Together"
              </p>
              <p className={`text-sm mt-1 ${isDarkTheme ? 'text-gray-400' : 'text-gray-500'}`}>
                Professional Trading Team Platform
              </p>
            </div>
            
            <form onSubmit={handleSubmit} className="space-y-6">
              {/* Error Display */}
              {error && (
                <div className={`p-3 rounded-lg border ${
                  isDarkTheme 
                    ? 'bg-red-500/10 border-red-500/30 text-red-400' 
                    : 'bg-red-50 border-red-200 text-red-600'
                }`}>
                  <p className="text-sm">{error}</p>
                </div>
              )}
              
              <div>
                <label className={`block mb-2 ${isDarkTheme ? 'text-gray-300' : 'text-gray-700'}`}>
                  Username
                </label>
                <input
                  type="text"
                  className={`w-full px-4 py-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                    isDarkTheme 
                      ? 'bg-white/10 border border-white/20 text-white placeholder-gray-400' 
                      : 'bg-white border border-gray-200 text-gray-900 placeholder-gray-500'
                  }`}
                  value={loginForm.username}
                  onChange={(e) => setLoginForm({...loginForm, username: e.target.value})}
                  required
                />
              </div>
              
              {isRegistering && (
                <>
                  <div>
                    <label className={`block mb-2 ${isDarkTheme ? 'text-gray-300' : 'text-gray-700'}`}>
                      Real Name
                    </label>
                    <input
                      type="text"
                      className={`w-full px-4 py-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                        isDarkTheme 
                          ? 'bg-white/10 border border-white/20 text-white placeholder-gray-400' 
                          : 'bg-white border border-gray-200 text-gray-900 placeholder-gray-500'
                      }`}
                      value={loginForm.real_name}
                      onChange={(e) => setLoginForm({...loginForm, real_name: e.target.value})}
                      required
                    />
                  </div>
                  
                  <div>
                    <label className={`block mb-2 ${isDarkTheme ? 'text-gray-300' : 'text-gray-700'}`}>
                      Email
                    </label>
                    <input
                      type="email"
                      className={`w-full px-4 py-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                        isDarkTheme 
                          ? 'bg-white/10 border border-white/20 text-white placeholder-gray-400' 
                          : 'bg-white border border-gray-200 text-gray-900 placeholder-gray-500'
                      }`}
                      value={loginForm.email}
                      onChange={(e) => setLoginForm({...loginForm, email: e.target.value})}
                      required
                    />
                  </div>
                  <div>
                    <label className={`block mb-2 ${isDarkTheme ? 'text-gray-300' : 'text-gray-700'}`}>
                      Membership Plan *
                    </label>
                    <select
                      className={`w-full px-4 py-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                        isDarkTheme 
                          ? 'bg-white/10 border border-white/20 text-white' 
                          : 'bg-white border border-gray-200 text-gray-900'
                      }`}
                      value={loginForm.membership_plan}
                      onChange={(e) => setLoginForm({...loginForm, membership_plan: e.target.value})}
                      required
                    >
                      <option value="">Select Membership Plan</option>
                      <option value="Monthly">Monthly</option>
                      <option value="Yearly">Yearly</option>
                      <option value="Lifetime">Lifetime</option>
                    </select>
                  </div>
                </>
              )}
              
              <div>
                <label className={`block mb-2 ${isDarkTheme ? 'text-gray-300' : 'text-gray-700'}`}>
                  Password
                </label>
                <input
                  type="password"
                  className={`w-full px-4 py-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                    isDarkTheme 
                      ? 'bg-white/10 border border-white/20 text-white placeholder-gray-400' 
                      : 'bg-white border border-gray-200 text-gray-900 placeholder-gray-500'
                  }`}
                  value={loginForm.password}
                  onChange={(e) => setLoginForm({...loginForm, password: e.target.value})}
                  required
                />
              </div>
              
              {isRegistering && (
                <div className={`p-3 rounded-lg border ${
                  isDarkTheme 
                    ? 'bg-blue-500/10 border-blue-500/30 text-blue-400' 
                    : 'bg-blue-50 border-blue-200 text-blue-600'
                }`}>
                  <p className="text-sm">
                    📝 Your account will be approved within 5 minutes after registration.
                  </p>
                </div>
              )}
              
              <button
                type="submit"
                className="w-full bg-gradient-to-r from-blue-600 to-purple-600 text-white py-3 rounded-lg font-semibold hover:from-blue-700 hover:to-purple-700 transition-all duration-200"
              >
                {isRegistering ? 'Register' : 'Login'}
              </button>

              {!isRegistering && (
                <div className="text-center">
                  <button
                    type="button"
                    onClick={() => setShowForgotPassword(true)}
                    className={`text-sm ${isDarkTheme ? 'text-gray-400 hover:text-gray-300' : 'text-gray-600 hover:text-gray-700'} transition-colors`}
                  >
                    Forgot your password?
                  </button>
                </div>
              )}
              
              <div className="text-center">
                <button
                  type="button"
                  onClick={() => setIsRegistering(!isRegistering)}
                  className={`${isDarkTheme ? 'text-blue-400 hover:text-blue-300' : 'text-blue-600 hover:text-blue-700'} transition-colors`}
                >
                  {isRegistering ? 'Already have an account? Login' : "Don't have an account? Register"}
                </button>
              </div>
            </form>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={`min-h-screen ${isDarkTheme ? 'bg-gradient-to-br from-gray-900 via-gray-800 to-black' : 'bg-gradient-to-br from-blue-50 via-white to-indigo-50'}`}>
      {/* Header - Fixed/Sticky */}
      <div className={`sticky top-0 z-50 border-b ${isDarkTheme ? 'border-white/10 bg-black/30' : 'border-gray-200 bg-white/80'} backdrop-blur-lg`}>
        <div className="max-w-6xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className="flex items-center space-x-3">
                {/* Mobile Menu Button */}
                <button
                  onClick={() => setShowMobileMenu(!showMobileMenu)}
                  className={`md:hidden p-2 rounded-lg transition-colors ${
                    isDarkTheme 
                      ? 'bg-white/10 text-gray-300 hover:bg-white/20' 
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                  </svg>
                </button>

                {/* Team Logo in Header */}
                <div className="w-12 h-12 rounded-lg overflow-hidden border-2 border-blue-500/30 bg-gradient-to-br from-blue-900 to-purple-900 shadow-lg">
                  <img 
                    src="https://i.imgur.com/ZPYCiyg.png" 
                    alt="CashoutAI Logo" 
                    className="w-full h-full object-cover"
                    onError={(e) => {
                      e.target.style.display = 'none';
                      e.target.nextSibling.style.display = 'flex';
                    }}
                  />
                  <div className="w-full h-full bg-gradient-to-br from-blue-600 to-purple-600 flex items-center justify-center text-white font-bold text-sm hidden">
                    💰
                  </div>
                </div>
                
                <div>
                  <h1 className={`text-2xl font-bold ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
                    CashoutAI
                  </h1>
                  <span className={`text-xs italic ${isDarkTheme ? 'text-blue-400' : 'text-blue-600'}`}>
                    Trade Together, Win Together
                  </span>
                </div>
              </div>
              
              <div className="flex items-center space-x-2">
                <div className={`w-2 h-2 rounded-full ${
                  isConnected ? 
                    (connectionMode === 'websocket' ? 'bg-green-400' : 'bg-yellow-400') 
                    : 'bg-red-400'
                }`}></div>
                <span className={`text-sm ${isDarkTheme ? 'text-gray-300' : 'text-gray-600'}`}>
                  {isConnected ? 
                    (connectionMode === 'websocket' ? 'Connected' : 'Polling') 
                    : 'Disconnected'
                  }
                </span>
              </div>
            </div>
            
            {/* Desktop Navigation Tabs - Hidden on Mobile */}
            <div className="hidden md:flex space-x-1">
              {['chat', 'notifications', 'achievements', 'portfolio', 'practice', 'favorites', 'profile'].map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={`px-4 py-2 rounded-lg font-medium capitalize transition-colors ${
                    activeTab === tab
                      ? isDarkTheme 
                        ? 'bg-blue-600 text-white' 
                        : 'bg-blue-600 text-white'
                      : isDarkTheme 
                        ? 'text-gray-300 hover:bg-white/10' 
                        : 'text-gray-700 hover:bg-gray-100 border border-gray-200'
                  }`}
                >
                  {tab}
                </button>
              ))}
              {currentUser?.is_admin && (
                <button
                  onClick={() => setActiveTab('admin')}
                  className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                    activeTab === 'admin'
                      ? isDarkTheme 
                        ? 'bg-yellow-600 text-white' 
                        : 'bg-yellow-600 text-white'
                      : isDarkTheme 
                        ? 'text-yellow-400 hover:bg-white/10' 
                        : 'text-yellow-600 hover:bg-yellow-50 border border-yellow-200'
                  }`}
                >
                  Admin
                </button>
              )}
            </div>
            
            {/* Action Buttons - Hide logout on mobile */}
            <div className="flex items-center space-x-4">
              {activeTab === 'chat' && (
                <>
                  <button
                    onClick={() => setShowSearch(!showSearch)}
                    className={`p-2 rounded-lg transition-colors ${
                      isDarkTheme 
                        ? 'bg-white/10 text-gray-300 hover:bg-white/20' 
                        : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                    }`}
                    title="Search messages"
                  >
                    🔍
                  </button>
                </>
              )}
              
              <button
                onClick={toggleTheme}
                className={`p-2 rounded-lg transition-colors ${
                  isDarkTheme 
                    ? 'bg-white/10 text-gray-300 hover:bg-white/20' 
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
                title="Toggle theme"
              >
                {isDarkTheme ? '☀️' : '🌙'}
              </button>
              
              {/* User info - Hide on small screens */}
              <div className="text-right hidden sm:block">
                <div className={`font-semibold ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
                  {currentUser?.real_name || currentUser?.username}
                </div>
                <div className="text-xs text-gray-400">
                  {currentUser?.screen_name && `@${currentUser.screen_name} • `}
                  {currentUser?.is_admin ? 'Admin' : currentUser?.role || 'Member'}
                </div>
              </div>

              {/* XP Progress Bar - Desktop */}
              <div className="hidden lg:block w-48">
                <XPProgressBar 
                  currentXP={userXP.experience_points} 
                  level={userXP.level} 
                  isDarkTheme={isDarkTheme} 
                />
              </div>
              
              {/* Logout - Only on desktop */}
              <button
                onClick={logout}
                className="hidden md:block px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
              >
                Logout
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content - Fixed height with proper scrolling accounting for header */}
      <div className="max-w-6xl mx-auto flex flex-col" style={{ height: 'calc(100vh - 80px)' }}>
        {/* Content area that takes remaining height */}
        <div className="flex-1 p-4 pb-20 overflow-hidden">{/* This constrains the content */}

        {/* Mobile Navigation Dropdown */}
        {showMobileMenu && (
          <div className={`md:hidden fixed top-16 left-4 right-4 border rounded-lg shadow-lg z-50 ${
            isDarkTheme ? 'border-white/10 bg-black/90' : 'border-gray-200 bg-white/90'
          } backdrop-blur-lg`}>
            <div className="p-4">
              {/* User Info at top of mobile menu */}
              <div className={`mb-4 p-3 rounded-lg border-b ${
                isDarkTheme ? 'border-white/10' : 'border-gray-200'
              }`}>
                <div className={`font-semibold ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
                  {currentUser?.real_name || currentUser?.username}
                </div>
                <div className={`text-sm ${isDarkTheme ? 'text-gray-400' : 'text-gray-600'}`}>
                  {currentUser?.screen_name && `@${currentUser.screen_name} • `}
                  {currentUser?.is_admin ? 'Admin' : currentUser?.role || 'Member'}
                </div>
              </div>

              <div className="grid grid-cols-3 gap-2 mb-4">
                {/* Chat Tab */}
                <button
                  onClick={() => {
                    setActiveTab('chat');
                    setShowMobileMenu(false);
                  }}
                  className={`flex flex-col items-center p-2 rounded-lg transition-colors ${
                    activeTab === 'chat'
                      ? isDarkTheme 
                        ? 'bg-blue-600 text-white' 
                        : 'bg-blue-600 text-white'
                      : isDarkTheme 
                        ? 'text-gray-300 hover:bg-white/10' 
                        : 'text-gray-700 hover:bg-gray-100'
                  }`}
                >
                  <span className="text-xl mb-1">💬</span>
                  <span className="text-xs font-medium">Chat</span>
                </button>

                {/* Notifications Tab */}
                <button
                  onClick={() => {
                    setActiveTab('notifications');
                    setShowMobileMenu(false);
                  }}
                  className={`flex flex-col items-center p-2 rounded-lg transition-colors relative ${
                    activeTab === 'notifications'
                      ? isDarkTheme 
                        ? 'bg-blue-600 text-white' 
                        : 'bg-blue-600 text-white'
                      : isDarkTheme 
                        ? 'text-gray-300 hover:bg-white/10' 
                        : 'text-gray-700 hover:bg-gray-100'
                  }`}
                >
                  <span className="text-xl mb-1">🔔</span>
                  <span className="text-xs font-medium">Alerts</span>
                  {notifications.length > 0 && (
                    <span className="absolute -top-1 -right-1 bg-red-500 text-white rounded-full text-xs w-4 h-4 flex items-center justify-center">
                      {notifications.length}
                    </span>
                  )}
                </button>

                {/* Achievements Tab */}
                <button
                  onClick={() => {
                    setActiveTab('achievements');
                    setShowMobileMenu(false);
                  }}
                  className={`flex flex-col items-center p-2 rounded-lg transition-colors ${
                    activeTab === 'achievements'
                      ? isDarkTheme 
                        ? 'bg-blue-600 text-white' 
                        : 'bg-blue-600 text-white'
                      : isDarkTheme 
                        ? 'text-gray-300 hover:bg-white/10' 
                        : 'text-gray-700 hover:bg-gray-100'
                  }`}
                >
                  <span className="text-xl mb-1">🏆</span>
                  <span className="text-xs font-medium">Wins</span>
                </button>

                {/* Portfolio Tab */}
                <button
                  onClick={() => {
                    setActiveTab('portfolio');
                    setShowMobileMenu(false);
                  }}
                  className={`flex flex-col items-center p-3 rounded-lg transition-colors ${
                    activeTab === 'portfolio'
                      ? isDarkTheme 
                        ? 'bg-blue-600 text-white' 
                        : 'bg-blue-600 text-white'
                      : isDarkTheme 
                        ? 'text-gray-300 hover:bg-white/10' 
                        : 'text-gray-700 hover:bg-gray-100'
                  }`}
                >
                  <span className="text-2xl mb-1">📊</span>
                  <span className="text-sm font-medium">Portfolio</span>
                </button>

                {/* Practice Tab */}
                <button
                  onClick={() => {
                    setActiveTab('practice');
                    setShowMobileMenu(false);
                  }}
                  className={`flex flex-col items-center p-3 rounded-lg transition-colors ${
                    activeTab === 'practice'
                      ? isDarkTheme 
                        ? 'bg-blue-600 text-white' 
                        : 'bg-blue-600 text-white'
                      : isDarkTheme 
                        ? 'text-gray-300 hover:bg-white/10' 
                        : 'text-gray-700 hover:bg-gray-100'
                  }`}
                >
                  <span className="text-2xl mb-1">📈</span>
                  <span className="text-sm font-medium">Practice</span>
                </button>

                {/* Favorites Tab */}
                <button
                  onClick={() => {
                    setActiveTab('favorites');
                    setShowMobileMenu(false);
                  }}
                  className={`flex flex-col items-center p-3 rounded-lg transition-colors ${
                    activeTab === 'favorites'
                      ? isDarkTheme 
                        ? 'bg-blue-600 text-white' 
                        : 'bg-blue-600 text-white'
                      : isDarkTheme 
                        ? 'text-gray-300 hover:bg-white/10' 
                        : 'text-gray-700 hover:bg-gray-100'
                  }`}
                >
                  <span className="text-2xl mb-1">⭐</span>
                  <span className="text-sm font-medium">Favorites</span>
                </button>

                {/* Profile Tab */}
                <button
                  onClick={() => {
                    setActiveTab('profile');
                    setShowMobileMenu(false);
                  }}
                  className={`flex flex-col items-center p-3 rounded-lg transition-colors ${
                    activeTab === 'profile'
                      ? isDarkTheme 
                        ? 'bg-blue-600 text-white' 
                        : 'bg-blue-600 text-white'
                      : isDarkTheme 
                        ? 'text-gray-300 hover:bg-white/10' 
                        : 'text-gray-700 hover:bg-gray-100'
                  }`}
                >
                  <span className="text-2xl mb-1">👤</span>
                  <span className="text-sm font-medium">Profile</span>
                </button>

                {/* Admin Tab (if admin) */}
                {currentUser?.is_admin && (
                  <button
                    onClick={() => {
                      setActiveTab('admin');
                      setShowMobileMenu(false);
                    }}
                    className={`flex flex-col items-center p-3 rounded-lg transition-colors ${
                      activeTab === 'admin'
                        ? isDarkTheme 
                          ? 'bg-yellow-600 text-white' 
                          : 'bg-yellow-600 text-white'
                        : isDarkTheme 
                          ? 'text-yellow-400 hover:bg-white/10' 
                          : 'text-yellow-600 hover:bg-yellow-50'
                    }`}
                  >
                    <span className="text-2xl mb-1">⚙️</span>
                    <span className="text-sm font-medium">Admin</span>
                  </button>
                )}
              </div>

              {/* Logout Button in Mobile Menu */}
              <button
                onClick={() => {
                  logout();
                  setShowMobileMenu(false);
                }}
                className="w-full flex items-center justify-center p-3 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors font-medium"
              >
                <span className="text-xl mr-2">🚪</span>
                Logout
              </button>
            </div>
          </div>
        )}

        {/* Close mobile menu when clicking outside */}
        {showMobileMenu && (
          <div 
            className="md:hidden fixed inset-0 z-40" 
            onClick={() => setShowMobileMenu(false)}
          />
        )}
        
        {/* Chat Tab */}
        {activeTab === 'chat' && (
          <div className="flex h-full">
            <ChatTab 
              messages={messages}
              filteredMessages={filteredMessages}
              showSearch={showSearch}
              searchQuery={searchQuery}
              setSearchQuery={setSearchQuery}
              formatMessageContent={formatMessageContent}
              addReaction={addReaction}
              messageReactions={messageReactions}
              addToFavorites={addToFavorites}
              favorites={favorites}
              messagesEndRef={messagesEndRef}
              sendMessage={sendMessage}
              newMessage={newMessage}
              setNewMessage={setNewMessage}
              imageFile={imageFile}
              setImageFile={setImageFile}
              imagePreview={imagePreview}
              setImagePreview={setImagePreview}
              isDarkTheme={isDarkTheme}
              replyToMessage={replyToMessage}
              setReplyToMessage={setReplyToMessage}
            />
            <UserList 
              onlineUsers={onlineUsers}
              allUsers={allUsers}
              currentUser={currentUser}
              isDarkTheme={isDarkTheme}
              showUserList={showUserList}
              setShowUserList={setShowUserList}
            />
          </div>
        )}

        {/* Notifications Tab */}
        {activeTab === 'notifications' && (
          <NotificationsTab 
            notifications={notifications}
            isDarkTheme={isDarkTheme}
            currentUser={currentUser}
          />
        )}

        {/* Achievements Tab */}
        {activeTab === 'achievements' && (
          <AchievementsTab 
            currentUser={currentUser}
            isDarkTheme={isDarkTheme}
          />
        )}

        {/* Portfolio Tab */}
        {activeTab === 'portfolio' && (
          <div className="space-y-6">
            {/* Asset Allocation Wheel */}
            <AssetAllocationWheel 
              positions={openPositions}
              isDarkTheme={isDarkTheme}
            />
            
            {/* Regular Portfolio Content */}
            <PortfolioTab 
              openPositions={openPositions}
              userPerformance={userPerformance}
              closePosition={closePosition}
              handlePositionAction={handlePositionAction}
              isDarkTheme={isDarkTheme}
              currentUser={currentUser}
            />
          </div>
        )}

        {/* Favorites Tab */}
        {activeTab === 'favorites' && (
          <FavoritesTab 
            favorites={favorites}
            addToFavorites={addToFavorites}
            removeFromFavorites={removeFromFavorites}
            isDarkTheme={isDarkTheme}
          />
        )}

        {/* Practice Tab with Recent Trades (Smaller/Log-like) */}
        {activeTab === 'practice' && (
          <div className="space-y-4">
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              {/* Enhanced Trade Form - COMPACT */}
              <div className={`lg:col-span-2 backdrop-blur-lg rounded-xl border p-4 ${
                isDarkTheme 
                  ? 'bg-white/5 border-white/10' 
                  : 'bg-white/80 border-gray-200'
              }`}>
                <h2 className={`text-lg font-bold mb-4 ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
                  📈 Paper Trading
                </h2>
                <form onSubmit={submitTrade} className="space-y-3">
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className={`block mb-1 text-sm ${isDarkTheme ? 'text-gray-300' : 'text-gray-700'}`}>
                        Stock Symbol
                      </label>
                      <input
                        type="text"
                        placeholder="TSLA"
                        className={`w-full px-3 py-2 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                          isDarkTheme 
                            ? 'bg-white/10 border border-white/20 text-white placeholder-gray-400' 
                            : 'bg-white border border-gray-200 text-gray-900 placeholder-gray-500'
                        }`}
                        value={tradeForm.symbol}
                        onChange={(e) => setTradeForm({...tradeForm, symbol: e.target.value.toUpperCase()})}
                        required
                      />
                      {/* Current Price Display */}
                      {tradeForm.symbol && (
                        <div className={`mt-1 text-sm ${isDarkTheme ? 'text-gray-400' : 'text-gray-600'}`}>
                          {priceLoading ? (
                            '🔄 Loading price...'
                          ) : currentStockPrice ? (
                            <span className="text-green-500 font-medium">
                              Current: ${currentStockPrice.toFixed(2)}
                            </span>
                          ) : (
                            <span className="text-red-500">
                              Price unavailable
                            </span>
                          )}
                        </div>
                      )}
                    </div>
                    
                    <div>
                      <label className={`block mb-1 text-sm ${isDarkTheme ? 'text-gray-300' : 'text-gray-700'}`}>
                        Action
                      </label>
                      <select
                        className={`w-full px-3 py-2 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                          isDarkTheme 
                            ? 'bg-white/10 border border-white/20 text-white' 
                            : 'bg-white border border-gray-200 text-gray-900'
                        }`}
                        value={tradeForm.action}
                        onChange={(e) => setTradeForm({...tradeForm, action: e.target.value})}
                      >
                        <option value="BUY">Buy</option>
                        <option value="SELL">Sell</option>
                      </select>
                    </div>
                  </div>
                  
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className={`block mb-1 text-sm ${isDarkTheme ? 'text-gray-300' : 'text-gray-700'}`}>
                        Quantity
                      </label>
                      <input
                        type="number"
                        placeholder="100"
                        className={`w-full px-3 py-2 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                          isDarkTheme 
                            ? 'bg-white/10 border border-white/20 text-white placeholder-gray-400' 
                            : 'bg-white border border-gray-200 text-gray-900 placeholder-gray-500'
                        }`}
                        value={tradeForm.quantity}
                        onChange={(e) => setTradeForm({...tradeForm, quantity: e.target.value})}
                        required
                      />
                    </div>
                    
                    <div>
                      <label className={`block mb-1 text-sm ${isDarkTheme ? 'text-gray-300' : 'text-gray-700'}`}>
                        Price
                      </label>
                      <input
                        type="number"
                        step="0.00000001"
                        placeholder="250.00"
                        className={`w-full px-3 py-2 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                          isDarkTheme 
                            ? 'bg-white/10 border border-white/20 text-white placeholder-gray-400' 
                            : 'bg-white border border-gray-200 text-gray-900 placeholder-gray-500'
                        }`}
                        value={tradeForm.price}
                        onChange={(e) => setTradeForm({...tradeForm, price: e.target.value})}
                        required
                      />
                    </div>
                  </div>
                  
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className={`block mb-1 text-sm ${isDarkTheme ? 'text-gray-300' : 'text-gray-700'}`}>
                        Stop Loss (Optional)
                      </label>
                      <input
                        type="number"
                        step="0.00000001"
                        placeholder="Auto-sell if price drops"
                        className={`w-full px-3 py-2 rounded-lg focus:outline-none focus:ring-2 focus:ring-red-500 ${
                          isDarkTheme 
                            ? 'bg-white/10 border border-white/20 text-white placeholder-gray-400' 
                            : 'bg-white border border-gray-200 text-gray-900 placeholder-gray-500'
                        }`}
                        value={tradeForm.stop_loss}
                        onChange={(e) => setTradeForm({...tradeForm, stop_loss: e.target.value})}
                      />
                    </div>
                    
                    <div>
                      <label className={`block mb-1 text-sm ${isDarkTheme ? 'text-gray-300' : 'text-gray-700'}`}>
                        Take Profit (Optional)
                      </label>
                      <input
                        type="number"
                        step="0.00000001"
                        placeholder="Auto-sell when profit reached"
                        className={`w-full px-3 py-2 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500 ${
                          isDarkTheme 
                            ? 'bg-white/10 border border-white/20 text-white placeholder-gray-400' 
                            : 'bg-white border border-gray-200 text-gray-900 placeholder-gray-500'
                        }`}
                        value={tradeForm.take_profit}
                        onChange={(e) => setTradeForm({...tradeForm, take_profit: e.target.value})}
                      />
                    </div>
                  </div>
                  
                  <div>
                    <label className={`block mb-1 text-sm ${isDarkTheme ? 'text-gray-300' : 'text-gray-700'}`}>
                      Notes (Optional)
                    </label>
                    <textarea
                      placeholder="Trade notes and strategy..."
                      className={`w-full px-3 py-2 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                        isDarkTheme 
                          ? 'bg-white/10 border border-white/20 text-white placeholder-gray-400' 
                          : 'bg-white border border-gray-200 text-gray-900 placeholder-gray-500'
                      }`}
                      value={tradeForm.notes}
                      onChange={(e) => setTradeForm({...tradeForm, notes: e.target.value})}
                    />
                  </div>
                  
                  <button
                    type="submit"
                    className="w-full bg-gradient-to-r from-blue-600 to-purple-600 text-white py-2 rounded-lg font-semibold hover:from-blue-700 hover:to-purple-700 transition-all duration-200"
                  >
                    Submit Trade
                  </button>
                </form>
              </div>
            </div>
          </div>
        )}

        {/* Profile Tab */}
        {activeTab === 'profile' && (
          <div className="space-y-6">
            {/* XP Progress - Mobile/Tablet */}
            <div className="lg:hidden">
              <XPProgressBar 
                currentXP={userXP.experience_points} 
                level={userXP.level} 
                isDarkTheme={isDarkTheme} 
              />
            </div>

            {/* Profile Header */}
            <div className={`backdrop-blur-lg rounded-xl border p-6 ${
              isDarkTheme 
                ? 'bg-white/5 border-white/10' 
                : 'bg-white/80 border-gray-200'
            }`}>
              <div className="flex items-center justify-between mb-6">
                <h2 className={`text-2xl font-bold ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
                  👤 My Profile
                </h2>
                <button
                  onClick={() => setShowProfileCustomization(!showProfileCustomization)}
                  className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors"
                >
                  {showProfileCustomization ? 'View Profile' : 'Customize Profile'}
                </button>
              </div>

              {!showProfileCustomization ? (
                <>
                  {/* User Stats Grid */}
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
                    <div className={`p-4 rounded-lg ${isDarkTheme ? 'bg-gray-800' : 'bg-gray-100'}`}>
                      <div className="text-2xl mb-1">⭐</div>
                      <div className={`text-lg font-bold ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
                        Level {userXP.level}
                      </div>
                      <div className={`text-sm ${isDarkTheme ? 'text-gray-400' : 'text-gray-600'}`}>
                        {userXP.experience_points.toLocaleString()} XP
                      </div>
                    </div>

                    <div className={`p-4 rounded-lg ${isDarkTheme ? 'bg-gray-800' : 'bg-gray-100'}`}>
                      <div className="text-2xl mb-1">💰</div>
                      <div className={`text-lg font-bold ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
                        ${formatCurrency(currentUser?.total_profit || 0)}
                      </div>
                      <div className={`text-sm ${isDarkTheme ? 'text-gray-400' : 'text-gray-600'}`}>
                        Total Profit
                      </div>
                    </div>

                    <div className={`p-4 rounded-lg ${isDarkTheme ? 'bg-gray-800' : 'bg-gray-100'}`}>
                      <div className="text-2xl mb-1">📈</div>
                      <div className={`text-lg font-bold ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
                        {currentUser?.win_percentage?.toFixed(1) || 0}%
                      </div>
                      <div className={`text-sm ${isDarkTheme ? 'text-gray-400' : 'text-gray-600'}`}>
                        Win Rate
                      </div>
                    </div>

                    <div className={`p-4 rounded-lg ${isDarkTheme ? 'bg-gray-800' : 'bg-gray-100'}`}>
                      <div className="text-2xl mb-1">🎯</div>
                      <div className={`text-lg font-bold ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
                        {currentUser?.trades_count || 0}
                      </div>
                      <div className={`text-sm ${isDarkTheme ? 'text-gray-400' : 'text-gray-600'}`}>
                        Total Trades
                      </div>
                    </div>
                  </div>

                  {/* Basic Profile Info */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div className="space-y-4">
                      <div>
                        <label className={`block mb-2 font-medium ${isDarkTheme ? 'text-gray-300' : 'text-gray-700'}`}>
                          Username
                        </label>
                        <div className={`p-3 rounded-lg border ${
                          isDarkTheme 
                            ? 'bg-white/5 border-white/10 text-white' 
                            : 'bg-white/70 border-gray-200 text-gray-900'
                        }`}>
                          {currentUser?.username}
                        </div>
                      </div>
                      
                      <div>
                        <label className={`block mb-2 font-medium ${isDarkTheme ? 'text-gray-300' : 'text-gray-700'}`}>
                          Real Name
                        </label>
                        <div className={`p-3 rounded-lg border ${
                          isDarkTheme 
                            ? 'bg-white/5 border-white/10 text-white' 
                            : 'bg-white/70 border-gray-200 text-gray-900'
                        }`}>
                          {currentUser?.real_name || 'Not set'}
                        </div>
                      </div>

                      <div>
                        <label className={`block mb-2 font-medium ${isDarkTheme ? 'text-gray-300' : 'text-gray-700'}`}>
                          Screen Name
                        </label>
                        <div className={`p-3 rounded-lg border ${
                          isDarkTheme 
                            ? 'bg-white/5 border-white/10 text-white' 
                            : 'bg-white/70 border-gray-200 text-gray-900'
                        }`}>
                          {currentUser?.screen_name || 'Not set'}
                        </div>
                      </div>
                    </div>

                    <div className="space-y-4">
                      <div>
                        <label className={`block mb-2 font-medium ${isDarkTheme ? 'text-gray-300' : 'text-gray-700'}`}>
                          Email
                        </label>
                        <div className={`p-3 rounded-lg border ${
                          isDarkTheme 
                            ? 'bg-white/5 border-white/10 text-white' 
                            : 'bg-white/70 border-gray-200 text-gray-900'
                        }`}>
                          {currentUser?.email}
                        </div>
                      </div>

                      <div>
                        <label className={`block mb-2 font-medium ${isDarkTheme ? 'text-gray-300' : 'text-gray-700'}`}>
                          Role
                        </label>
                        <div className={`p-3 rounded-lg border ${
                          isDarkTheme 
                            ? 'bg-white/5 border-white/10 text-white' 
                            : 'bg-white/70 border-gray-200 text-gray-900'
                        }`}>
                          {currentUser?.is_admin ? '👑 Admin' : currentUser?.role || 'Member'}
                        </div>
                      </div>

                      <div>
                        <label className={`block mb-2 font-medium ${isDarkTheme ? 'text-gray-300' : 'text-gray-700'}`}>
                          Member Since
                        </label>
                        <div className={`p-3 rounded-lg border ${
                          isDarkTheme 
                            ? 'bg-white/5 border-white/10 text-white' 
                            : 'bg-white/70 border-gray-200 text-gray-900'
                        }`}>
                          {currentUser?.created_at ? new Date(currentUser.created_at).toLocaleDateString() : 'Unknown'}
                        </div>
                      </div>
                    </div>
                  </div>
                </>
              ) : (
                <ProfileCustomization 
                  currentUser={currentUser}
                  isDarkTheme={isDarkTheme}
                  onUpdate={() => {
                    // Refresh user data after profile update
                    setShowProfileCustomization(false);
                  }}
                />
              )}
            </div>
          </div>
        )}

        {/* Admin Tab */}
        {activeTab === 'admin' && currentUser?.is_admin && (
          <div className="space-y-6">
            <div className={`backdrop-blur-lg rounded-xl border p-6 ${
              isDarkTheme 
                ? 'bg-white/5 border-white/10' 
                : 'bg-white/80 border-gray-200'
            }`}>
              <h2 className={`text-2xl font-bold mb-6 ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
                ⚙️ Admin Panel
              </h2>
              
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Pending Users */}
                <div>
                  <h3 className={`text-xl font-semibold mb-4 ${isDarkTheme ? 'text-yellow-400' : 'text-yellow-600'}`}>
                    Pending Approvals ({pendingUsers.length})
                  </h3>
                  <div className="space-y-3 max-h-96 overflow-y-auto">
                    {pendingUsers.map((user) => (
                      <div key={user.id} className={`p-4 rounded-lg border ${
                        isDarkTheme 
                          ? 'bg-white/5 border-white/10' 
                          : 'bg-white/70 border-gray-200'
                      }`}>
                        <div className="flex justify-between items-start">
                          <div>
                            <h4 className={`font-semibold ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
                              {user.real_name || user.username}
                            </h4>
                            <p className={`text-sm ${isDarkTheme ? 'text-gray-300' : 'text-gray-600'}`}>
                              @{user.username} • {user.email}
                            </p>
                            <p className={`text-xs ${isDarkTheme ? 'text-gray-400' : 'text-gray-500'}`}>
                              Membership: {user.membership_plan || 'Not specified'}
                            </p>
                          </div>
                          <div className="flex space-x-2">
                            <button
                              onClick={() => handleApproval(user.id, true)}
                              className="px-3 py-1 bg-green-600 text-white rounded text-sm hover:bg-green-700"
                            >
                              Approve
                            </button>
                            <button
                              onClick={() => handleApproval(user.id, false)}
                              className="px-3 py-1 bg-red-600 text-white rounded text-sm hover:bg-red-700"
                            >
                              Reject
                            </button>
                          </div>
                        </div>
                      </div>
                    ))}
                    {pendingUsers.length === 0 && (
                      <p className={`text-center ${isDarkTheme ? 'text-gray-400' : 'text-gray-500'}`}>
                        No pending users
                      </p>
                    )}
                  </div>
                </div>
                
                {/* All Users */}
                <div>
                  <h3 className={`text-xl font-semibold mb-4 ${isDarkTheme ? 'text-blue-400' : 'text-blue-600'}`}>
                    All Users ({allUsers.length})
                  </h3>
                  <div className="space-y-3 max-h-96 overflow-y-auto">
                    {allUsers.map((user) => (
                      <div key={user.id} className={`p-4 rounded-lg border ${
                        isDarkTheme 
                          ? 'bg-white/5 border-white/10' 
                          : 'bg-white/70 border-gray-200'
                      }`}>
                        <div className="flex justify-between items-start">
                          <div>
                            <h4 className={`font-semibold ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
                              {user.real_name || user.username}
                              {user.is_admin && ' 👑'}
                            </h4>
                            <p className={`text-sm ${isDarkTheme ? 'text-gray-300' : 'text-gray-600'}`}>
                              @{user.username} • {user.email}
                            </p>
                            <p className={`text-xs ${isDarkTheme ? 'text-gray-400' : 'text-gray-500'}`}>
                              Role: {user.is_admin ? 'Admin' : user.role || 'Member'} 
                              {user.id === currentUser.id ? ' (You)' : ''}
                              {user.id !== currentUser.id ? ' (Can Edit)' : ''}
                            </p>
                          </div>
                          {user.id !== currentUser.id && (
                            <div className="flex space-x-2">
                              {/* Role Management Dropdown - Shows for all users except current user */}
                              <select
                                onChange={(e) => handleUserRoleChange(user.id, e.target.value)}
                                value={user.is_admin ? 'admin' : (user.role || 'member')}
                                className={`text-xs px-2 py-1 rounded border focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                                  isDarkTheme 
                                    ? 'bg-gray-800 border-white/20 text-white' 
                                    : 'bg-white border-gray-300 text-gray-900'
                                }`}
                                style={{
                                  backgroundColor: isDarkTheme ? '#374151' : '#ffffff',
                                  color: isDarkTheme ? '#ffffff' : '#000000'
                                }}
                              >
                                {/* Role options for all users including admins - v2.1 */}
                                <option value="member" style={{
                                  backgroundColor: isDarkTheme ? '#374151' : '#ffffff',
                                  color: isDarkTheme ? '#ffffff' : '#000000'
                                }}>Member</option>
                                <option value="admin" style={{
                                  backgroundColor: isDarkTheme ? '#374151' : '#ffffff',
                                  color: isDarkTheme ? '#ffffff' : '#000000'
                                }}>Admin</option>
                                <option value="moderator" style={{
                                  backgroundColor: isDarkTheme ? '#374151' : '#ffffff',
                                  color: isDarkTheme ? '#ffffff' : '#000000'
                                }}>Moderator</option>
                              </select>
                              <button
                                onClick={() => handleUserRemoval(user.id)}
                                className="px-2 py-1 bg-red-600 text-white rounded text-xs hover:bg-red-700"
                                title="Remove user"
                              >
                                Remove
                              </button>
                            </div>
                          )}
                          {user.id === currentUser.id && (
                            <div className={`text-xs px-2 py-1 rounded ${isDarkTheme ? 'bg-gray-700 text-gray-300' : 'bg-gray-200 text-gray-600'}`}>
                              Your Account
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Edit Profile Modal */}
        {showEditProfile && (
          <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4 z-50">
            <div className={`backdrop-blur-lg rounded-2xl p-6 w-full max-w-md border ${
              isDarkTheme 
                ? 'bg-white/10 border-white/20' 
                : 'bg-white/90 border-gray-200'
            }`}>
              <h2 className={`text-2xl font-bold mb-6 ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
                Edit Profile
              </h2>
              
              <form onSubmit={updateProfile} className="space-y-4">
                <div>
                  <label className={`block mb-2 ${isDarkTheme ? 'text-gray-300' : 'text-gray-700'}`}>
                    Real Name
                  </label>
                  <input
                    type="text"
                    className={`w-full px-4 py-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                      isDarkTheme 
                        ? 'bg-white/10 border border-white/20 text-white placeholder-gray-400' 
                        : 'bg-white border border-gray-200 text-gray-900 placeholder-gray-500'
                    }`}
                    value={editProfileForm.real_name}
                    onChange={(e) => setEditProfileForm({...editProfileForm, real_name: e.target.value})}
                  />
                </div>
                
                <div>
                  <label className={`block mb-2 ${isDarkTheme ? 'text-gray-300' : 'text-gray-700'}`}>
                    Screen Name
                  </label>
                  <input
                    type="text"
                    className={`w-full px-4 py-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                      isDarkTheme 
                        ? 'bg-white/10 border border-white/20 text-white placeholder-gray-400' 
                        : 'bg-white border border-gray-200 text-gray-900 placeholder-gray-500'
                    }`}
                    value={editProfileForm.screen_name}
                    onChange={(e) => setEditProfileForm({...editProfileForm, screen_name: e.target.value})}
                  />
                </div>
                
                <div>
                  <label className={`block mb-2 ${isDarkTheme ? 'text-gray-300' : 'text-gray-700'}`}>
                    Username
                  </label>
                  <input
                    type="text"
                    className={`w-full px-4 py-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                      isDarkTheme 
                        ? 'bg-white/10 border border-white/20 text-white placeholder-gray-400' 
                        : 'bg-white border border-gray-200 text-gray-900 placeholder-gray-500'
                    }`}
                    value={editProfileForm.username}
                    onChange={(e) => setEditProfileForm({...editProfileForm, username: e.target.value})}
                    required
                  />
                </div>
                
                <div>
                  <label className={`block mb-2 ${isDarkTheme ? 'text-gray-300' : 'text-gray-700'}`}>
                    Email
                  </label>
                  <input
                    type="email"
                    className={`w-full px-4 py-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                      isDarkTheme 
                        ? 'bg-white/10 border border-white/20 text-white placeholder-gray-400' 
                        : 'bg-white border border-gray-200 text-gray-900 placeholder-gray-500'
                    }`}
                    value={editProfileForm.email}
                    onChange={(e) => setEditProfileForm({...editProfileForm, email: e.target.value})}
                    required
                  />
                </div>
                
                {/* Profile Picture Upload */}
                <div>
                  <label className={`block mb-2 ${isDarkTheme ? 'text-gray-300' : 'text-gray-700'}`}>
                    Profile Picture
                  </label>
                  
                  {/* Current/Preview Avatar */}
                  <div className="flex items-center space-x-4 mb-4">
                    <div className="w-20 h-20 rounded-full overflow-hidden border-2 border-white/20">
                      {avatarPreview ? (
                        <img src={avatarPreview} alt="Preview" className="w-full h-full object-cover" />
                      ) : currentUser?.avatar_url ? (
                        <img src={currentUser.avatar_url} alt="Current" className="w-full h-full object-cover" />
                      ) : (
                        <div className="w-full h-full bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center text-white font-bold text-lg">
                          {currentUser?.username?.charAt(0).toUpperCase()}
                        </div>
                      )}
                    </div>
                    
                    <div className="flex-1">
                      <input
                        type="file"
                        accept="image/*"
                        onChange={handleFileSelect}
                        className={`w-full px-3 py-2 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                          isDarkTheme 
                            ? 'bg-white/10 border border-white/20 text-white' 
                            : 'bg-white border border-gray-200 text-gray-900'
                        }`}
                      />
                      <p className={`text-xs mt-1 ${isDarkTheme ? 'text-gray-400' : 'text-gray-500'}`}>
                        Upload JPG, PNG, GIF (max 1MB)
                      </p>
                    </div>
                  </div>
                  
                  {/* Upload Button */}
                  {avatarFile && (
                    <button
                      type="button"
                      onClick={() => uploadAvatarFile(avatarFile)}
                      className="w-full bg-gradient-to-r from-purple-600 to-blue-600 text-white py-2 rounded-lg font-semibold hover:from-purple-700 hover:to-blue-700 transition-all duration-200 mb-4"
                    >
                      Upload New Picture
                    </button>
                  )}
                </div>
                
                <div className="flex space-x-4 pt-4">
                  <button
                    type="submit"
                    className="flex-1 bg-gradient-to-r from-blue-600 to-purple-600 text-white py-3 rounded-lg font-semibold hover:from-blue-700 hover:to-purple-700 transition-all duration-200"
                  >
                    Save Changes
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setShowEditProfile(false);
                      setAvatarFile(null);
                      setAvatarPreview(null);
                    }}
                    className="flex-1 bg-gray-600 text-white py-3 rounded-lg font-semibold hover:bg-gray-700 transition-colors"
                  >
                    Cancel
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* Change Password Modal */}
        {showChangePassword && (
          <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4 z-50">
            <div className={`backdrop-blur-lg rounded-2xl p-6 w-full max-w-md border ${
              isDarkTheme 
                ? 'bg-white/10 border-white/20' 
                : 'bg-white/90 border-gray-200'
            }`}>
              <h2 className={`text-2xl font-bold mb-6 ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
                Change Password
              </h2>
              
              <form onSubmit={changePassword} className="space-y-4">
                <div>
                  <label className={`block mb-2 ${isDarkTheme ? 'text-gray-300' : 'text-gray-700'}`}>
                    Current Password
                  </label>
                  <input
                    type="password"
                    className={`w-full px-4 py-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                      isDarkTheme 
                        ? 'bg-white/10 border border-white/20 text-white placeholder-gray-400' 
                        : 'bg-white border border-gray-200 text-gray-900 placeholder-gray-500'
                    }`}
                    value={passwordForm.current_password}
                    onChange={(e) => setPasswordForm({...passwordForm, current_password: e.target.value})}
                    required
                  />
                </div>
                
                <div>
                  <label className={`block mb-2 ${isDarkTheme ? 'text-gray-300' : 'text-gray-700'}`}>
                    New Password
                  </label>
                  <input
                    type="password"
                    className={`w-full px-4 py-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                      isDarkTheme 
                        ? 'bg-white/10 border border-white/20 text-white placeholder-gray-400' 
                        : 'bg-white border border-gray-200 text-gray-900 placeholder-gray-500'
                    }`}
                    value={passwordForm.new_password}
                    onChange={(e) => setPasswordForm({...passwordForm, new_password: e.target.value})}
                    required
                    minLength="6"
                  />
                </div>
                
                <div>
                  <label className={`block mb-2 ${isDarkTheme ? 'text-gray-300' : 'text-gray-700'}`}>
                    Confirm New Password
                  </label>
                  <input
                    type="password"
                    className={`w-full px-4 py-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                      isDarkTheme 
                        ? 'bg-white/10 border border-white/20 text-white placeholder-gray-400' 
                        : 'bg-white border border-gray-200 text-gray-900 placeholder-gray-500'
                    }`}
                    value={passwordForm.confirm_password}
                    onChange={(e) => setPasswordForm({...passwordForm, confirm_password: e.target.value})}
                    required
                    minLength="6"
                  />
                </div>
                
                <div className="flex space-x-4 pt-4">
                  <button
                    type="submit"
                    disabled={passwordForm.new_password !== passwordForm.confirm_password}
                    className="flex-1 bg-gradient-to-r from-green-600 to-blue-600 text-white py-3 rounded-lg font-semibold hover:from-green-700 hover:to-blue-700 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Change Password
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setShowChangePassword(false);
                      setPasswordForm({
                        current_password: '',
                        new_password: '',
                        confirm_password: ''
                      });
                    }}
                    className="flex-1 bg-gray-600 text-white py-3 rounded-lg font-semibold hover:bg-gray-700 transition-colors"
                  >
                    Cancel
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* Forgot Password Modal */}
        {showForgotPassword && (
          <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4 z-50">
            <div className={`backdrop-blur-lg rounded-2xl p-6 w-full max-w-md border ${
              isDarkTheme 
                ? 'bg-white/10 border-white/20' 
                : 'bg-white/90 border-gray-200'
            }`}>
              <h2 className={`text-2xl font-bold mb-6 ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
                Reset Password
              </h2>
              
              <form onSubmit={requestPasswordReset} className="space-y-4">
                <div>
                  <label className={`block mb-2 ${isDarkTheme ? 'text-gray-300' : 'text-gray-700'}`}>
                    Email Address
                  </label>
                  <input
                    type="email"
                    className={`w-full px-4 py-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                      isDarkTheme 
                        ? 'bg-white/10 border border-white/20 text-white placeholder-gray-400' 
                        : 'bg-white border border-gray-200 text-gray-900 placeholder-gray-500'
                    }`}
                    placeholder="Enter your email address"
                    value={resetPasswordForm.email}
                    onChange={(e) => setResetPasswordForm({...resetPasswordForm, email: e.target.value})}
                    required
                  />
                </div>
                
                <div className={`p-3 rounded-lg border ${
                  isDarkTheme 
                    ? 'bg-blue-500/10 border-blue-500/30 text-blue-400' 
                    : 'bg-blue-50 border-blue-200 text-blue-600'
                }`}>
                  <p className="text-sm">
                    📧 We'll send you a password reset link if an account with this email exists.
                  </p>
                </div>
                
                <div className="flex space-x-4 pt-4">
                  <button
                    type="submit"
                    className="flex-1 bg-gradient-to-r from-blue-600 to-purple-600 text-white py-3 rounded-lg font-semibold hover:from-blue-700 hover:to-purple-700 transition-all duration-200"
                  >
                    Send Reset Link
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setShowForgotPassword(false);
                      setResetPasswordForm({ email: '' });
                    }}
                    className="flex-1 bg-gray-600 text-white py-3 rounded-lg font-semibold hover:bg-gray-700 transition-colors"
                  >
                    Cancel
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* Password Reset with Token Modal */}
        {window.location.search.includes('token=') && (
          <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4 z-50">
            <div className={`backdrop-blur-lg rounded-2xl p-6 w-full max-w-md border ${
              isDarkTheme 
                ? 'bg-white/10 border-white/20' 
                : 'bg-white/90 border-gray-200'
            }`}>
              <h2 className={`text-2xl font-bold mb-6 ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
                Set New Password
              </h2>
              
              <form onSubmit={confirmPasswordReset} className="space-y-4">
                <div>
                  <label className={`block mb-2 ${isDarkTheme ? 'text-gray-300' : 'text-gray-700'}`}>
                    Reset Token
                  </label>
                  <input
                    type="text"
                    className={`w-full px-4 py-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                      isDarkTheme 
                        ? 'bg-white/10 border border-white/20 text-white placeholder-gray-400' 
                        : 'bg-white border border-gray-200 text-gray-900 placeholder-gray-500'
                    }`}
                    placeholder="Enter reset token from email"
                    value={resetTokenForm.token || new URLSearchParams(window.location.search).get('token') || ''}
                    onChange={(e) => setResetTokenForm({...resetTokenForm, token: e.target.value})}
                    required
                  />
                </div>
                
                <div>
                  <label className={`block mb-2 ${isDarkTheme ? 'text-gray-300' : 'text-gray-700'}`}>
                    New Password
                  </label>
                  <input
                    type="password"
                    className={`w-full px-4 py-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                      isDarkTheme 
                        ? 'bg-white/10 border border-white/20 text-white placeholder-gray-400' 
                        : 'bg-white border border-gray-200 text-gray-900 placeholder-gray-500'
                    }`}
                    value={resetTokenForm.new_password}
                    onChange={(e) => setResetTokenForm({...resetTokenForm, new_password: e.target.value})}
                    required
                    minLength="6"
                  />
                </div>
                
                <div>
                  <label className={`block mb-2 ${isDarkTheme ? 'text-gray-300' : 'text-gray-700'}`}>
                    Confirm New Password
                  </label>
                  <input
                    type="password"
                    className={`w-full px-4 py-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                      isDarkTheme 
                        ? 'bg-white/10 border border-white/20 text-white placeholder-gray-400' 
                        : 'bg-white border border-gray-200 text-gray-900 placeholder-gray-500'
                    }`}
                    value={resetTokenForm.confirm_password}
                    onChange={(e) => setResetTokenForm({...resetTokenForm, confirm_password: e.target.value})}
                    required
                    minLength="6"
                  />
                </div>
                
                <div className="flex space-x-4 pt-4">
                  <button
                    type="submit"
                    disabled={resetTokenForm.new_password !== resetTokenForm.confirm_password}
                    className="flex-1 bg-gradient-to-r from-green-600 to-blue-600 text-white py-3 rounded-lg font-semibold hover:from-green-700 hover:to-blue-700 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Reset Password
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setResetTokenForm({ token: '', new_password: '', confirm_password: '' });
                      window.location.href = window.location.pathname; // Remove token from URL
                    }}
                    className="flex-1 bg-gray-600 text-white py-3 rounded-lg font-semibold hover:bg-gray-700 transition-colors"
                  >
                    Cancel
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        </div> {/* End of content area */}
      </div> {/* End of main container */}
    </div>
  );
}

export default App;