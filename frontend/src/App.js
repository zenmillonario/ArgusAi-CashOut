import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import ChatTab from './ChatTab';
import ChatInput from './ChatInput';
import PortfolioTab from './PortfolioTab';
import UserList from './UserList';
import FavoritesTab from './FavoritesTab';
import AchievementsTab from './AchievementsTab';
import NotificationsTab from './NotificationsTab';
import ProfileCustomization from './ProfileCustomization';
import PublicProfile from './PublicProfile';
import XPProgressBar from './XPProgressBar';
import AssetAllocationWheel from './AssetAllocationWheel';
import LoadingScreen from './LoadingScreen';
import { formatPrice, formatPnL, formatCurrency } from './utils';
import notificationService from './firebase-config';
import capacitorManager from './capacitor-utils';
import './App.css';

// Error Boundary Component for Mobile App
class MobileErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true };
  }

  componentDidCatch(error, errorInfo) {
    console.error('🚨 Mobile App Error Boundary Caught:', error);
    console.error('🚨 Error Info:', errorInfo);
    this.setState({
      error: error,
      errorInfo: errorInfo
    });
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-gray-900 text-white p-8 flex items-center justify-center">
          <div className="max-w-md w-full text-center">
            <h1 className="text-2xl font-bold mb-4 text-red-400">Mobile App Error</h1>
            <p className="text-gray-300 mb-4">Something went wrong with the mobile app interface.</p>
            <button 
              onClick={() => window.location.reload()} 
              className="bg-blue-600 hover:bg-blue-700 px-6 py-2 rounded-lg transition-colors"
            >
              Reload App
            </button>
            <details className="mt-4 text-left">
              <summary className="cursor-pointer text-sm text-gray-400">Technical Details</summary>
              <pre className="text-xs mt-2 p-2 bg-gray-800 rounded overflow-auto">
                {this.state.error && this.state.error.toString()}
                <br />
                {this.state.errorInfo.componentStack}
              </pre>
            </details>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';
const API = BACKEND_URL ? `${BACKEND_URL}/api` : '/api';

function App() {
  const [showLoadingScreen, setShowLoadingScreen] = useState(true);
  const [currentUser, setCurrentUser] = useState(null);
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  
  // PERFORMANCE OPTIMIZATION: Loading states for better UX
  const [isLoggingIn, setIsLoggingIn] = useState(false);
  const [messages, setMessages] = useState([]);
  // Expose setMessages for ChatTab's load-more feature
  window.__setMessages = setMessages;
  const [newMessage, setNewMessage] = useState('');
  const [isConnected, setIsConnected] = useState(false);
  const [connectionMode, setConnectionMode] = useState('disconnected'); // 'websocket', 'polling', 'disconnected'
  const [showLogin, setShowLogin] = useState(true);
  const [loginForm, setLoginForm] = useState({ username: '', email: '', password: '', real_name: '', membership_plan: '' });
  const [rememberMe, setRememberMe] = useState(false);
  const [isRegistering, setIsRegistering] = useState(false);
  const [showScrollButton, setShowScrollButton] = useState(false);
  const [mobileUserListOpen, setMobileUserListOpen] = useState(false); // Track mobile user list state
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
  const [resetPasswordForm, setResetPasswordForm] = useState({ email: '', new_password: '', confirm_password: '' });
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
  const [viewingUserId, setViewingUserId] = useState(null);
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
      // MOBILE OPTIMIZATION: Initialize Capacitor for mobile app
      console.log('🚀 App initializing...');
      console.log('Platform info:', {
        isNative: capacitorManager.isNative,
        platform: capacitorManager.platform,
        userAgent: navigator.userAgent
      });
      
      if (capacitorManager.isNative) {
        console.log('📱 Initializing mobile app features...');
        try {
          await capacitorManager.initializeApp();
          console.log('✅ Mobile app initialization complete');
        } catch (error) {
          console.error('❌ Mobile app initialization failed:', error);
        }
      }
      
      // Check if this is a request for the widget page
      if (window.location.pathname === '/cashoutai-button-widget.html') {
        // Redirect to the actual widget page
        window.location.href = '/cashoutai-button-widget.html';
        return;
      }
      
      console.log('🔍 Checking for saved user...');
      const savedUser = localStorage.getItem('cashoutai_user');
      if (savedUser) {
        try {
          const user = JSON.parse(savedUser);
          
          // Enhanced session validation with remember me support
          const sessionCreated = user.sessionCreated || user.session_created_at;
          const sessionDuration = user.sessionDuration || 365; // Default 365 days
          const maxSessionHours = sessionDuration * 24; // Convert days to hours
          
          const sessionAge = sessionCreated ? 
            (Date.now() - new Date(sessionCreated).getTime()) / (1000 * 60 * 60) : 
            maxSessionHours + 1; // Default to expired if no session timestamp
          
          console.log(`🕒 Session check: Age=${sessionAge.toFixed(1)}h, Max=${maxSessionHours}h, RememberMe=${user.rememberMe}`);
          
          if (sessionAge < maxSessionHours && user.active_session_id) {
            setCurrentUser(user);
            setShowLogin(false);
            
            // Initialize Firebase push notifications for saved user (non-blocking)
            if (!capacitorManager.isMobile()) {
              notificationService.initializeForUser(user.id)
                .then(success => console.log(success ? '✅ Firebase notifications initialized' : '⚠️ Firebase notifications unavailable'))
                .catch(err => console.log('⚠️ Firebase init skipped:', err.message));
            }
            
            // Set up automatic session refresh for remember me sessions
            if (user.rememberMe) {
              console.log('🔄 Setting up automatic session refresh for remember me session');
              setupSessionRefresh(user);
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
      
      // Load notifications for the user
      loadNotifications();
    }
  }, [currentUser]);

  const loadNotifications = async () => {
    if (!currentUser) return;
    
    try {
      const response = await axios.get(`${API}/users/${currentUser.id}/notifications`);
      setNotifications(response.data);
    } catch (error) {
      console.error('Error loading notifications:', error);
    }
  };

  const markNotificationAsRead = async (notificationId) => {
    try {
      await axios.put(`${API}/users/${currentUser.id}/notifications/${notificationId}/read`);
      setNotifications(prev => 
        prev.map(notification => 
          notification.id === notificationId 
            ? { ...notification, read: true }
            : notification
        )
      );
    } catch (error) {
      console.error('Error marking notification as read:', error);
    }
  };

  const deleteNotification = async (notificationId) => {
    try {
      await axios.delete(`${API}/users/${currentUser.id}/notifications/${notificationId}`);
      setNotifications(prev => prev.filter(notification => notification.id !== notificationId));
    } catch (error) {
      console.error('Error deleting notification:', error);
    }
  };

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

  // Mobile app initialization
  useEffect(() => {
    const initializeMobileApp = async () => {
      try {
        await capacitorManager.initializeApp();
        
        // Set up mobile-specific event listeners
        capacitorManager.addAppStateListeners({
          onResume: () => {
            console.log('🔄 App resumed - refreshing data...');
            if (currentUser) {
              loadMessages();
              loadUserData();
            }
          },
          onPause: () => {
            console.log('⏸️ App paused');
          }
        });
        
        console.log('✅ Mobile app initialization complete');
      } catch (error) {
        console.error('❌ Mobile app initialization error:', error);
      }
    };
    
    initializeMobileApp();
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
        
        setNotifications(prev => [newNotification, ...(prev || []).slice(0, 49)]); // Keep last 50 notifications
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

  // Simple scroll-to-bottom function using container scroll instead of scrollIntoView
  const scrollToBottom = () => {
    const chatContainer = document.querySelector('[data-chat-messages]');
    if (chatContainer) {
      chatContainer.scrollTop = chatContainer.scrollHeight;
      setShowScrollButton(false);
    }
  };

  // Simple scroll detection for showing/hiding scroll button - with delay for DOM readiness
  useEffect(() => {
    console.log('🎯 Scroll button useEffect running - activeTab:', activeTab);
    
    if (activeTab === 'chat') {
      // Add delay to wait for ChatTab DOM to render
      const setupScrollListener = () => {
        console.log('✅ Setting up scroll listener...');
        const chatContainer = document.querySelector('[data-chat-messages]');
        console.log('🔍 Scroll listener setup - container found:', !!chatContainer);
        
        if (chatContainer) {
          console.log('📦 Container classes:', chatContainer.className);
          console.log('📊 Container scroll info:', {
            scrollTop: chatContainer.scrollTop,
            scrollHeight: chatContainer.scrollHeight,
            clientHeight: chatContainer.clientHeight
          });
          
          const handleScroll = () => {
            const { scrollTop, scrollHeight, clientHeight } = chatContainer;
            const isNearBottom = scrollTop + clientHeight >= scrollHeight - 100;
            console.log('📏 Scroll event:', { scrollTop, scrollHeight, clientHeight, isNearBottom });
            setShowScrollButton(!isNearBottom);
            console.log('🔘 Button should show:', !isNearBottom);
          };
          
          chatContainer.addEventListener('scroll', handleScroll, { passive: true });
          console.log('✅ Scroll listener attached');
          
          return () => {
            chatContainer.removeEventListener('scroll', handleScroll);
            console.log('🧹 Scroll listener removed');
          };
        } else {
          console.log('❌ No container found, retrying in 500ms...');
          setTimeout(setupScrollListener, 500);
        }
      };
      
      // Start setup after delay
      setTimeout(setupScrollListener, 1000);
    } else {
      console.log('❌ activeTab is not chat, current value:', activeTab);
    }
  }, [activeTab]);

  // Simple auto-scroll to bottom when messages change - using container scroll
  useEffect(() => {
    if (activeTab === 'chat') {
      const chatContainer = document.querySelector('.overflow-y-auto');
      if (chatContainer) {
        chatContainer.scrollTop = chatContainer.scrollHeight;
      }
    }
  }, [filteredMessages, activeTab]);

  // Separate effect for initial page load - using container scroll
  useEffect(() => {
    if (activeTab === 'chat') {
      const initialScroll = () => {
        const chatContainer = document.querySelector('.overflow-y-auto');
        if (chatContainer) {
          chatContainer.scrollTop = chatContainer.scrollHeight;
        } else {
          // Retry if container not ready yet
          setTimeout(initialScroll, 500);
        }
      };
      // Start initial scroll attempt after short delay
      setTimeout(initialScroll, 1000);
    }
  }, [activeTab]); // Only run when tab becomes active (page load)





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
      
      // MOBILE OPTIMIZATION: Use mobile-friendly WebSocket URL
      const baseWsUrl = capacitorManager.isNative 
        ? capacitorManager.getWebSocketUrl(BACKEND_URL)
        : wsUrl.replace(`/${currentUser.id}/${currentUser.active_session_id}`, '');
          
      const finalWsUrl = `${baseWsUrl}/${currentUser.id}/${currentUser.active_session_id}`;
      console.log('🔌 Connecting to WebSocket:', finalWsUrl);
      
      const ws = new WebSocket(finalWsUrl);
      
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
            
          } else if (data.type === 'notification') {
            // New notification received
            console.log('🔔 Notification received:', data);
            
            // Add to notifications list
            setNotifications(prev => [data.notification, ...prev]);
            
            // Play notification sound for follow notifications
            if (data.notification.type === 'follow') {
              playNotificationSound();
            }
            
            // Visual notification in app title
            setTimeout(() => {
              if (document.hidden) {
                document.title = `🔔 ${data.notification.title} - CashoutAI`;
              }
            }, 100);
            
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
          } else if (data.type === 'message_deleted') {
            // Remove deleted message from state
            setMessages(prev => prev.filter(m => m.id !== data.data.id));
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
              const response = await axios.get(`${API}/messages?limit=50&user_id=${currentUser?.id}`);
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
      console.log('🔄 Starting message load...', new Date().toISOString());
      const startTime = performance.now();
      
      // PERFORMANCE OPTIMIZATION: Load more messages for 4+ weeks of history
      const url = currentUser ? `${API}/messages?user_id=${currentUser.id}&limit=50` : `${API}/messages?limit=50`;
      const response = await axios.get(url);
      
      const loadTime = performance.now() - startTime;
      console.log(`⚡ API Response received in ${loadTime.toFixed(2)}ms`);
      
      // Process messages immediately
      const processStart = performance.now();
      setMessages(response.data || []);
      const processTime = performance.now() - processStart;
      console.log(`📊 Messages processed in ${processTime.toFixed(2)}ms`);
      
      // CRITICAL UX FIX: Handle empty message state
      if (!response.data || response.data.length === 0) {
        console.log('📭 No messages in database - showing empty state');
        setMessages([]); // Ensure empty array to trigger empty state UI
      } else {
        console.log(`✅ FAST LOAD: ${response.data.length} messages loaded in ${loadTime.toFixed(2)}ms for ${currentUser?.username || 'user'}`);
      }
      
      console.log(`🏁 Total load time: ${(performance.now() - startTime).toFixed(2)}ms`);
      
    } catch (error) {
      console.error('❌ Error loading messages:', error);
      console.error('❌ Error details:', {
        message: error.message,
        status: error.response?.status,
        statusText: error.response?.statusText,
        url: error.config?.url,
        timeout: error.code === 'ECONNABORTED' ? 'Request timeout' : 'No timeout'
      });
      setMessages([]); // Set empty array on error to avoid infinite loading
      
      // If there's an access error, try the regular endpoint
      if (error.response?.status === 403) {
        try {
          console.log('🔄 Trying fallback endpoint...');
          const response = await axios.get(`${API}/messages?limit=50`);
          setMessages(response.data || []);
          console.log(`✅ Fallback loaded ${response.data?.length || 0} messages`);
        } catch (fallbackError) {
          console.error('❌ Fallback message loading failed:', fallbackError);
          setMessages([]); // Ensure empty state on complete failure
        }
      }
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

  const refreshUserProfile = async () => {
    if (!currentUser) return;
    try {
      const response = await axios.get(`${API}/users/${currentUser.id}/profile`);
      setCurrentUser(prev => ({
        ...prev,
        bio: response.data.bio,
        profile_banner: response.data.profile_banner,
        avatar_url: response.data.avatar_url,
        location: response.data.location,
        show_location: response.data.show_location,
        trading_style_tags: response.data.trading_style_tags,
        achievements: response.data.achievements,
        experience_points: response.data.experience_points,
        level: response.data.level,
      }));
    } catch (error) {
      console.error('Error refreshing user profile:', error);
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
    setIsLoggingIn(true); // PERFORMANCE OPTIMIZATION: Show loading state
    
    try {
      if (isRegistering) {
        // Registration
        const isTrialUser = loginForm.membership_plan === "14-Day Trial";
        
        const response = await axios.post(`${API}/users/register`, {
          username: loginForm.username,
          email: loginForm.email,
          real_name: loginForm.real_name,
          membership_plan: loginForm.membership_plan,
          password: loginForm.password,
          is_trial: isTrialUser  // NEW: Trial system support
        });
        
        if (isTrialUser) {
          alert('🎉 Trial registration successful! You can login immediately and start your 14-day free trial. Welcome to ArgusAI CashOut!');
        } else {
          alert('Registration successful! Please wait for admin approval. You will be approved within 5 minutes.');
        }
        
        setIsRegistering(false);
        setLoginForm({ username: '', email: '', password: '', real_name: '', membership_plan: '' });
        setRememberMe(false);
      } else {
        // Login
        console.log('🔐 Attempting login with API:', API);
        const response = await axios.post(`${API}/users/login`, {
          username: loginForm.username,
          password: loginForm.password
        });
        
        console.log('✅ Login successful, user data:', response.data);
        
        // PERFORMANCE OPTIMIZATION: Show login success immediately
        setCurrentUser(response.data);
        setShowLogin(false);
        setLoginForm({ username: '', email: '', password: '', real_name: '', membership_plan: '' });
        setRememberMe(false);
        
        // Save user to localStorage for persistence with session info
        const sessionData = {
          ...response.data,
          rememberMe: rememberMe,
          sessionCreated: new Date().toISOString(),
          sessionDuration: 365 // Stay logged in for 1 year
        };
        localStorage.setItem('cashoutai_user', JSON.stringify(sessionData));
        
        console.log('💾 User data saved to localStorage');
        console.log('🎯 Login complete, should now show main app interface');
        
        // Set up automatic session refresh for remember me sessions
        if (rememberMe) {
          console.log('🔄 Setting up automatic session refresh for new remember me session');
          setupSessionRefresh(sessionData);
        }
        
        // PERFORMANCE OPTIMIZATION: Initialize Firebase push notifications asynchronously in background
        // Don't await this - let it run in background so login completes immediately
        setTimeout(() => {
          initializeFirebaseAsync(response.data.id);
        }, 100); // Small delay to ensure UI updates first
      }
    } catch (error) {
      console.error('Authentication error:', error);
      const errorMessage = error.response?.data?.detail || 'An error occurred during authentication';
      setError(errorMessage);
    } finally {
      setIsLoggingIn(false); // PERFORMANCE OPTIMIZATION: Clear loading state
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

  const deleteMessage = async (messageId) => {
    if (!currentUser?.is_admin) return;
    try {
      await axios.delete(`${API}/messages/${messageId}?user_id=${currentUser.id}`);
      setMessages(prev => prev.filter(m => m.id !== messageId));
    } catch (error) {
      console.error('Failed to delete message:', error);
    }
  };


  const sendMessage = async (e) => {
    e.preventDefault();
    
    // Check if we have an image to send
    if (imageFile && imagePreview) {
      const textContent = newMessage.trim() || null;
      
      // OPTIMISTIC UI: Show message immediately before API responds
      const optimisticMsg = {
        id: 'pending-' + Date.now(),
        user_id: currentUser.id,
        username: currentUser.username,
        screen_name: currentUser.screen_name,
        content: imagePreview,
        content_type: "image",
        text_content: textContent,
        is_admin: currentUser.is_admin,
        avatar_url: currentUser.avatar_url,
        timestamp: new Date().toISOString(),
        highlighted_tickers: [],
        reply_to_id: replyToMessage?.id || null,
        reply_to: replyToMessage ? { id: replyToMessage.id, username: replyToMessage.username, screen_name: replyToMessage.screen_name, content: replyToMessage.content_type === 'image' ? '[image]' : replyToMessage.content?.substring(0, 100), content_type: replyToMessage.content_type } : null
      };
      
      // Clear inputs immediately for snappy UX
      setImageFile(null);
      setImagePreview(null);
      setNewMessage('');
      setReplyToMessage(null);
      
      try {
        await axios.post(`${API}/messages`, {
          content: imagePreview,
          content_type: "image",
          user_id: currentUser.id,
          reply_to_id: replyToMessage?.id || null,
          text_content: textContent
        });
      } catch (error) {
        console.error('Error sending image:', error);
        // Remove optimistic message on failure
        setMessages(prev => prev.filter(m => m.id !== optimisticMsg.id));
        alert('Error sending image');
      }
      return;
    }
    
    // Send text message
    if (!newMessage.trim()) return;
    
    const messageText = newMessage;
    
    // Clear input immediately for snappy UX
    setNewMessage('');
    setReplyToMessage(null);

    try {
      await axios.post(`${API}/messages`, {
        content: messageText,
        content_type: "text",
        user_id: currentUser.id,
        reply_to_id: replyToMessage?.id || null
      });
    } catch (error) {
      console.error('Error sending message:', error);
      // Restore message on failure
      setNewMessage(messageText);
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
        const response = await axios.get(`${API}/users/${currentUser.id}/profile`);
        setUserXP({
          experience_points: response.data.experience_points || 0,
          level: response.data.level || 1
        });
      }
    } catch (error) {
      console.error('Error fetching user XP data:', error);
    }
  };

  const handleViewProfile = (userId) => {
    setViewingUserId(userId);
  };

  const closeProfileView = () => {
    setViewingUserId(null);
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
    
    if (resetPasswordForm.new_password !== resetPasswordForm.confirm_password) {
      alert('Passwords do not match');
      return;
    }
    
    if (resetPasswordForm.new_password.length < 6) {
      alert('Password must be at least 6 characters');
      return;
    }
    
    try {
      const response = await axios.post(`${API}/users/reset-password-direct`, {
        email: resetPasswordForm.email,
        new_password: resetPasswordForm.new_password
      });
      
      alert(response.data.message || 'Password reset successfully! You can now log in.');
      setShowForgotPassword(false);
      setResetPasswordForm({ email: '', new_password: '', confirm_password: '' });
    } catch (error) {
      console.error('Error resetting password:', error);
      alert(error.response?.data?.detail || 'Error resetting password. Please check your email address.');
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

  // PERFORMANCE OPTIMIZATION: Async Firebase initialization
  const initializeFirebaseAsync = async (userId) => {
    try {
      console.log('🔄 Initializing Firebase notifications in background for user:', userId);
      let notificationSuccess = false;
      if (!capacitorManager.isMobile()) {
        notificationSuccess = await notificationService.initializeForUser(userId);
      } else {
        console.log('📱 Skipping Firebase in mobile WebView');  
      }
      if (notificationSuccess) {
        console.log('✅ Firebase notifications initialized successfully (background)');
      } else {
        console.log('⚠️ Firebase notifications failed to initialize (may not be supported)');
      }
    } catch (error) {
      console.error('Error initializing Firebase notifications (background):', error);
      // Don't show error to user since this is background initialization
    }
  };

  // Session refresh functionality for remember me sessions
  const setupSessionRefresh = (user) => {
    // Refresh session every 23 hours to keep it alive
    const refreshInterval = setInterval(async () => {
      try {
        console.log('🔄 Refreshing session for remember me user');
        const response = await axios.get(`${API}/users/${user.id}/session-status?session_id=${user.active_session_id}`);
        
        if (response.data.valid) {
          // Update session timestamp in localStorage
          const savedUser = JSON.parse(localStorage.getItem('cashoutai_user'));
          if (savedUser) {
            savedUser.sessionCreated = new Date().toISOString();
            localStorage.setItem('cashoutai_user', JSON.stringify(savedUser));
            console.log('✅ Session refreshed successfully');
          }
        } else {
          console.log('❌ Session invalid, logging out');
          clearInterval(refreshInterval);
          logout();
        }
      } catch (error) {
        console.error('Error refreshing session:', error);
        clearInterval(refreshInterval);
        logout();
      }
    }, 23 * 60 * 60 * 1000); // 23 hours

    // Store interval ID to clear it later
    window.sessionRefreshInterval = refreshInterval;
  };

  const logout = async () => {
    try {
      await axios.post(`${API}/users/logout?user_id=${currentUser.id}`);
    } catch (error) {
      console.error('Error during logout:', error);
    }
    
    // Clear session refresh interval
    if (window.sessionRefreshInterval) {
      clearInterval(window.sessionRefreshInterval);
      window.sessionRefreshInterval = null;
    }
    
    // Clear persisted user data and reset remember me state
    localStorage.removeItem('cashoutai_user');
    setRememberMe(false);
    
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
  console.log('🎬 Render conditions:', {
    showLoadingScreen,
    showLogin, 
    currentUser: !!currentUser,
    isLoading
  });

  if (showLoadingScreen) {
    console.log('📺 Rendering loading screen');
    return (
      <LoadingScreen 
        onComplete={() => setShowLoadingScreen(false)}
        isDarkTheme={isDarkTheme}
      />
    );
  }

  if (showLogin) {
    console.log('🔐 Rendering login screen');
    
    return (
      <div className="min-h-screen bg-black relative overflow-hidden">
        {/* Matrix Code Rain Background - CSS-only for performance */}
        <div className="absolute inset-0 pointer-events-none matrix-login-bg" />
        
        {/* Matrix Rain CSS */}
        <style>{`
          .matrix-login-bg {
            background: linear-gradient(180deg, transparent 0%, rgba(0,0,0,0.3) 100%);
          }
          .matrix-login-bg::before,
          .matrix-login-bg::after {
            content: '';
            position: absolute;
            inset: 0;
            background-image: 
              linear-gradient(180deg, rgba(0,255,0,0.03) 0%, transparent 50%),
              linear-gradient(0deg, rgba(0,136,255,0.03) 0%, transparent 50%);
          }
          @keyframes matrixRainDown {
            0% { transform: translateY(-110%); opacity: 0; }
            5% { opacity: 1; }
            95% { opacity: 1; }
            100% { transform: translateY(110vh); opacity: 0; }
          }
          @keyframes matrixRainUp {
            0% { transform: translateY(110vh); opacity: 0; }
            5% { opacity: 1; }
            95% { opacity: 1; }
            100% { transform: translateY(-110%); opacity: 0; }
          }
          .matrix-col-down {
            animation: matrixRainDown var(--dur) linear var(--delay) infinite;
          }
          .matrix-col-up {
            animation: matrixRainUp var(--dur) linear var(--delay) infinite;
          }
        `}</style>
        
        {/* Matrix columns */}
        <div className="absolute inset-0 pointer-events-none overflow-hidden">
          {(() => {
            const matrixChars = '01アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン';
            const cols = [];
            for (let i = 0; i < 90; i++) {
              const left = (i / 90) * 100;
              const goUp = i % 5 === 0;
              const dur = 3 + (i % 7) * 1.2;
              const delay = (i * 0.05) % 2;
              const height = 15 + (i % 12) * 3;
              const chars = [];
              for (let j = 0; j < height; j++) {
                chars.push(matrixChars[(i * 7 + j * 13) % matrixChars.length]);
              }
              cols.push(
                <div
                  key={i}
                  className={`absolute font-mono text-sm leading-tight ${goUp ? 'matrix-col-up bottom-0' : 'matrix-col-down top-0'}`}
                  style={{ left: `${left}%`, '--dur': `${dur}s`, '--delay': `${delay}s`, opacity: 0 }}
                >
                  {chars.map((c, j) => (
                    <span key={j} className="block" style={{
                      color: j === 0 
                        ? (goUp ? '#0088ff' : '#00ff00') 
                        : (goUp ? `rgba(0,136,255,${0.1 + (j % 5) * 0.1})` : `rgba(0,255,0,${0.1 + (j % 5) * 0.1})`)
                    }}>{c}</span>
                  ))}
                </div>
              );
            }
            return cols;
          })()}
        </div>
        
        {/* Login Form */}
        <div className="relative z-10 flex items-center justify-center min-h-screen p-4">
          <div className={`w-full max-w-md backdrop-blur-xl rounded-2xl border p-8 ${
            isDarkTheme 
              ? 'bg-black/60 border-green-500/20 shadow-[0_0_40px_rgba(0,255,0,0.08)]' 
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
                          ? 'bg-white/10 border border-white/20 text-white [&>option]:bg-gray-800 [&>option]:text-white' 
                          : 'bg-white border border-gray-200 text-gray-900 [&>option]:bg-white [&>option]:text-gray-900'
                      }`}
                      value={loginForm.membership_plan}
                      onChange={(e) => setLoginForm({...loginForm, membership_plan: e.target.value})}
                      required
                    >
                      <option value="">Select Membership Plan</option>
                      <option value="14-Day Trial">14-Day FREE Trial</option>
                      <option value="Monthly">Monthly - $199/month</option>
                      <option value="Yearly">Yearly - $1,296/year</option>
                      <option value="Lifetime">Lifetime - $3,969</option>
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
              
              {!isRegistering && (
                <div className="mb-4">
                  <label className={`flex items-center cursor-pointer ${isDarkTheme ? 'text-gray-300' : 'text-gray-700'}`}>
                    <input
                      type="checkbox"
                      className={`mr-3 rounded focus:ring-2 focus:ring-blue-500 ${
                        isDarkTheme 
                          ? 'bg-white/10 border-white/20 text-blue-500' 
                          : 'bg-white border-gray-300 text-blue-600'
                      }`}
                      checked={rememberMe}
                      onChange={(e) => setRememberMe(e.target.checked)}
                    />
                    <span className="text-sm">
                      Remember me for 30 days
                      <span className={`block text-xs ${isDarkTheme ? 'text-gray-400' : 'text-gray-500'}`}>
                        Keep me logged in on this device
                      </span>
                    </span>
                  </label>
                </div>
              )}
              
              {isRegistering && (
                <div className={`p-3 rounded-lg border ${
                  loginForm.membership_plan === "14-Day Trial"
                    ? isDarkTheme 
                      ? 'bg-green-500/10 border-green-500/30 text-green-400' 
                      : 'bg-green-50 border-green-200 text-green-600'
                    : isDarkTheme 
                      ? 'bg-blue-500/10 border-blue-500/30 text-blue-400' 
                      : 'bg-blue-50 border-blue-200 text-blue-600'
                }`}>
                  <p className="text-sm">
                    {loginForm.membership_plan === "14-Day Trial" 
                      ? '📝 Your trial account will be reviewed and approved by an admin.' 
                      : '📝 Your account will be reviewed and approved by an admin.'
                    }
                  </p>
                </div>
              )}
              
              <button
                type="submit"
                disabled={isLoggingIn}
                className={`w-full py-3 rounded-lg font-semibold transition-all duration-200 ${
                  isLoggingIn 
                    ? 'bg-gray-400 cursor-not-allowed text-gray-200' 
                    : 'bg-gradient-to-r from-blue-600 to-purple-600 text-white hover:from-blue-700 hover:to-purple-700'
                }`}
              >
                {isLoggingIn ? (
                  <div className="flex items-center justify-center space-x-2">
                    <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                    <span>Signing In...</span>
                  </div>
                ) : (
                  isRegistering ? 'Register' : 'Login'
                )}
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
        
        {/* Forgot Password Modal - inside login view */}
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
                    placeholder="Enter new password (min 6 characters)"
                    value={resetPasswordForm.new_password}
                    onChange={(e) => setResetPasswordForm({...resetPasswordForm, new_password: e.target.value})}
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
                    placeholder="Confirm new password"
                    value={resetPasswordForm.confirm_password}
                    onChange={(e) => setResetPasswordForm({...resetPasswordForm, confirm_password: e.target.value})}
                    required
                    minLength="6"
                  />
                </div>
                
                <div className={`p-3 rounded-lg border ${
                  isDarkTheme 
                    ? 'bg-blue-500/10 border-blue-500/30 text-blue-400' 
                    : 'bg-blue-50 border-blue-200 text-blue-600'
                }`}>
                  <p className="text-sm">
                    Enter the email linked to your account to set a new password.
                  </p>
                </div>
                
                {resetPasswordForm.new_password && resetPasswordForm.confirm_password && 
                  resetPasswordForm.new_password !== resetPasswordForm.confirm_password && (
                  <div className="p-2 rounded-lg bg-red-500/10 border border-red-500/30">
                    <p className="text-sm text-red-400">Passwords do not match</p>
                  </div>
                )}
                
                <div className="flex space-x-4 pt-4">
                  <button
                    type="submit"
                    disabled={!resetPasswordForm.email || !resetPasswordForm.new_password || resetPasswordForm.new_password !== resetPasswordForm.confirm_password}
                    className="flex-1 bg-gradient-to-r from-blue-600 to-purple-600 text-white py-3 rounded-lg font-semibold hover:from-blue-700 hover:to-purple-700 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Reset Password
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setShowForgotPassword(false);
                      setResetPasswordForm({ email: '', new_password: '', confirm_password: '' });
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
      </div>
    );
  }

  console.log('🏠 Rendering main app interface');
  console.log('📱 Mobile Debug - User:', currentUser ? 'Authenticated' : 'Not authenticated');
  console.log('📱 Mobile Debug - Active Tab:', activeTab);
  console.log('📱 Mobile Debug - Is Mobile:', capacitorManager.isMobile());
  
  const isMobile = capacitorManager.isMobile();
  
  // Mobile-specific simplified rendering to fix WebView issues
  if (isMobile) {
    console.log('📱 Using mobile-optimized layout');
    return (
      <MobileErrorBoundary>
        <div className={`min-h-screen ${isDarkTheme ? 'bg-gray-900' : 'bg-white'}`} style={{ height: '100vh', overflow: 'hidden' }}>
          {/* Simplified Mobile Header */}
          <div className={`${isDarkTheme ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'} border-b`} style={{ height: '60px' }}>
            <div className="px-4 py-3 flex items-center justify-between">
              <div className="flex items-center space-x-3">
                <h1 className={`text-lg font-bold ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
                  CashOutAi
                </h1>
              </div>
              <div className="flex items-center space-x-2">
                <button
                  onClick={logout}
                  className={`px-3 py-1 rounded text-sm ${
                    isDarkTheme 
                      ? 'bg-red-600 hover:bg-red-700 text-white' 
                      : 'bg-red-500 hover:bg-red-600 text-white'
                  }`}
                >
                  Logout
                </button>
              </div>
            </div>
          </div>

          {/* Simplified Mobile Content */}
          <div className={`${isDarkTheme ? 'bg-gray-900' : 'bg-white'}`} style={{ height: 'calc(100vh - 60px)', overflow: 'auto' }}>
            <div className="p-4">
              {activeTab === 'chat' && (
                <div>
                  <h2 className={`text-xl font-bold mb-4 ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
                    Welcome {currentUser?.real_name || currentUser?.username}!
                  </h2>
                  <ChatTab
                    messages={messages || []}
                    currentUser={currentUser}
                    isDarkTheme={isDarkTheme}
                    onUserClick={() => {}}
                  />
                </div>
              )}
            </div>
          </div>
        </div>
      </MobileErrorBoundary>
    );
  }

  // Desktop/Web rendering with complex CSS
  try {
    return (
      <MobileErrorBoundary>
        <div className={`min-h-screen overflow-auto ${isDarkTheme ? 'bg-gradient-to-br from-gray-900 via-gray-800 to-black' : 'bg-gradient-to-br from-blue-50 via-white to-indigo-50'}`}>{/* Ensure body can scroll */}
      {/* Header - Fixed/Sticky */}
      <div className={`sticky top-0 z-50 border-b ${isDarkTheme ? 'border-white/10 bg-black/30' : 'border-gray-200 bg-white/80'} backdrop-blur-lg`}>
        <div className="max-w-6xl mx-auto px-4 py-3">
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
              {[
                { key: 'chat', emoji: '💬', label: 'Chat' },
                { key: 'notifications', emoji: '🔔', label: 'Notifications' },
                { key: 'achievements', emoji: '🏆', label: 'Achievements' },
                { key: 'portfolio', emoji: '📊', label: 'Portfolio' },
                { key: 'practice', emoji: '🎯', label: 'Practice' },
                { key: 'favorites', emoji: '⭐', label: 'Favorites' },
                { key: 'profile', emoji: '👤', label: 'Profile' }
              ].map((tab) => (
                <button
                  key={tab.key}
                  onClick={() => setActiveTab(tab.key)}
                  className={`px-2 py-1 rounded-lg font-medium transition-colors ${
                    activeTab === tab.key
                      ? isDarkTheme 
                        ? 'bg-blue-600 text-white' 
                        : 'bg-blue-600 text-white'
                      : isDarkTheme 
                        ? 'text-gray-300 hover:bg-white/10' 
                        : 'text-gray-700 hover:bg-gray-100 border border-gray-200'
                  }`}
                  title={tab.label}
                >
                  <span className="text-base">{tab.emoji}</span>
                </button>
              ))}
              {currentUser?.is_admin && (
                <button
                  onClick={() => setActiveTab('admin')}
                  className={`px-2 py-1 rounded-lg font-medium transition-colors ${
                    activeTab === 'admin'
                      ? isDarkTheme 
                        ? 'bg-yellow-600 text-white' 
                        : 'bg-yellow-600 text-white'
                      : isDarkTheme 
                        ? 'text-yellow-400 hover:bg-white/10' 
                        : 'text-yellow-600 hover:bg-yellow-50 border border-yellow-200'
                  }`}
                  title="Admin"
                >
                  <span className="text-base">👑</span>
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
              <div className="hidden lg:block w-40">
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
      <div className="max-w-6xl mx-auto flex flex-col min-h-0 pb-6">{/* Allow natural height with bottom padding */}
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
          <div className="flex flex-col h-full" style={{ maxHeight: 'calc(100vh - 120px)' }}>
            {/* Mobile Chat Header with User List Toggle */}
            <div className="md:hidden flex items-center justify-between p-3 border-b border-white/20 flex-shrink-0 bg-opacity-90 backdrop-blur-sm" style={{
              background: isDarkTheme ? 'rgba(31, 41, 55, 0.95)' : 'rgba(255, 255, 255, 0.95)'
            }}>
              <h2 className={`text-lg font-semibold ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
                Chat
              </h2>
              <button
                onClick={() => setMobileUserListOpen(!mobileUserListOpen)}
                className={`px-3 py-2 rounded-lg transition-all duration-200 font-medium border-2 ${
                  mobileUserListOpen 
                    ? 'bg-blue-500 text-white border-blue-500 shadow-lg' 
                    : isDarkTheme 
                      ? 'bg-white/20 text-white border-white/30 hover:bg-white/30' 
                      : 'bg-blue-50 text-blue-700 border-blue-200 hover:bg-blue-100'
                }`}
                title={mobileUserListOpen ? 'Hide user list' : 'Show user list'}
              >
                <span className="flex items-center space-x-2">
                  <span className="text-lg">👥</span>
                  <span className="text-sm font-semibold">({onlineUsers?.length || 0})</span>
                </span>
              </button>
            </div>
            
            {/* Chat Content Area - 2 columns with isolated scroll containers */}
            <div className="flex flex-1 overflow-hidden min-h-0">
              {/* Chat Messages Column - isolated scroll container */}
              <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
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
                  onlineUsers={onlineUsers}
                  allUsers={allUsers}
                  currentUser={currentUser}
                  onViewProfile={handleViewProfile}
                  hideMessageInput={true}
                  mobileUserListOpen={mobileUserListOpen}
                  setMobileUserListOpen={setMobileUserListOpen}
                  deleteMessage={deleteMessage}
                  showScrollButton={showScrollButton}
                  scrollToBottom={scrollToBottom}
                />
              </div>
              
              {/* Desktop UserList Column - isolated scroll container with fixed height */}
              <div className="hidden md:block flex-shrink-0 overflow-hidden">
                <UserList 
                  onlineUsers={onlineUsers}
                  allUsers={allUsers}
                  currentUser={currentUser}
                  isDarkTheme={isDarkTheme}
                  showUserList={showUserList}
                  setShowUserList={setShowUserList}
                  onViewProfile={handleViewProfile}
                />
              </div>
            </div>
            
            {/* Message Input Area - Always at bottom */}
            <div className={`flex-shrink-0 border-t ${
              isDarkTheme ? 'border-white/10 bg-gray-900/50' : 'border-gray-200 bg-white/50'
            } backdrop-blur-lg`}>
              <div className="p-2">
                <ChatInput 
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
              </div>
            </div>
            
            {/* Mobile User List Overlay - Fixed positioning */}
            {mobileUserListOpen && (
              <div 
                className={`md:hidden fixed z-[9999] transform transition-all duration-300 ease-in-out ${
                  isDarkTheme ? 'bg-gray-900/98' : 'bg-white/98'
                } backdrop-blur-xl shadow-2xl border border-white/10`} 
                style={{ 
                  top: '160px',  // Below the mobile header
                  left: '0',
                  right: '0', 
                  bottom: '0',
                  position: 'fixed',
                  overflow: 'hidden'
                }}
              >
                <div className="h-full flex flex-col">
                  {/* User List Header */}
                  <div className={`p-3 border-b border-t flex items-center justify-between ${
                    isDarkTheme ? 'border-white/10' : 'border-gray-200'
                  }`}>
                    <h3 className={`font-semibold ${
                      isDarkTheme ? 'text-white' : 'text-gray-900'
                    }`}>
                      Online Users ({onlineUsers?.length || 0})
                    </h3>
                    <button
                      onClick={() => setMobileUserListOpen(false)}
                      className={`p-1.5 rounded-lg ${
                        isDarkTheme ? 'hover:bg-white/10 text-gray-400' : 'hover:bg-gray-100 text-gray-600'
                      }`}
                    >
                      ✕
                    </button>
                  </div>

                  {/* Scrollable User List */}
                  <div className="flex-1 overflow-y-auto p-2">
                    {onlineUsers?.map((user) => {
                      const isCurrentUser = user.id === currentUser?.id;
                      
                      return (
                        <div
                          key={`mobile-${user.id}`}
                          onClick={() => {
                            if (!isCurrentUser && handleViewProfile) {
                              handleViewProfile(user.id);
                              setMobileUserListOpen(false);
                            }
                          }}
                          className={`flex items-center space-x-3 p-3 rounded-lg mb-2 ${
                            isCurrentUser 
                              ? isDarkTheme ? 'bg-blue-900/50' : 'bg-blue-100'
                              : isDarkTheme ? 'hover:bg-white/10 cursor-pointer' : 'hover:bg-gray-50 cursor-pointer'
                          } transition-colors`}
                        >
                          {/* Avatar */}
                          <div className="relative">
                            {user.avatar_url ? (
                              <img
                                src={user.avatar_url}
                                alt={`${user.username}'s avatar`}
                                className="w-10 h-10 rounded-full object-cover"
                              />
                            ) : (
                              <div className={`w-10 h-10 rounded-full flex items-center justify-center text-sm font-medium ${
                                user.is_admin 
                                  ? 'bg-yellow-500 text-white' 
                                  : isDarkTheme ? 'bg-gray-600 text-white' : 'bg-gray-300 text-gray-700'
                              }`}>
                                {user.is_admin ? '👑' : (user.screen_name || user.username).charAt(0).toUpperCase()}
                              </div>
                            )}
                            
                            {/* Online status indicator */}
                            <div className={`absolute -bottom-1 -right-1 w-4 h-4 rounded-full border-2 ${
                              isDarkTheme ? 'border-gray-900' : 'border-white'
                            } bg-green-400`}></div>
                          </div>

                          {/* User Info */}
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center space-x-1">
                              <p className={`text-sm font-medium truncate ${
                                isDarkTheme ? 'text-white' : 'text-gray-900'
                              }`}>
                                {user.screen_name || user.username}
                                {isCurrentUser && ' (You)'}
                                {!isCurrentUser && ' 👁️'}
                              </p>
                              {user.is_admin && (
                                <span className="text-xs">👑</span>
                              )}
                            </div>
                            
                            <p className={`text-xs truncate ${
                              isDarkTheme ? 'text-gray-400' : 'text-gray-500'
                            }`}>
                              {user.role || 'Member'} • Online
                            </p>
                          </div>
                        </div>
                      );
                    })}

                    {/* Offline Users Section */}
                    {allUsers && allUsers.filter(user => !onlineUsers?.some(onlineUser => onlineUser.id === user.id)).length > 0 && (
                      <>
                        <div className={`px-2 py-1 mt-4 mb-2 text-xs font-semibold uppercase tracking-wide ${
                          isDarkTheme ? 'text-gray-400' : 'text-gray-500'
                        }`}>
                          Offline ({allUsers.filter(user => !onlineUsers?.some(onlineUser => onlineUser.id === user.id)).length})
                        </div>
                        
                        {allUsers.filter(user => !onlineUsers?.some(onlineUser => onlineUser.id === user.id)).map((user) => (
                          <div
                            key={`offline-${user.id}`}
                            onClick={() => {
                              if (handleViewProfile) {
                                handleViewProfile(user.id);
                                setMobileUserListOpen(false);
                              }
                            }}
                            className={`flex items-center space-x-3 p-2 rounded-lg mb-1 opacity-60 cursor-pointer ${
                              isDarkTheme ? 'hover:bg-white/10' : 'hover:bg-gray-50'
                            } transition-colors`}
                          >
                            {user.avatar_url ? (
                              <img
                                src={user.avatar_url}
                                alt={`${user.username}'s avatar`}
                                className="w-8 h-8 rounded-full object-cover"
                              />
                            ) : (
                              <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
                                user.is_admin 
                                  ? 'bg-yellow-500 text-white' 
                                  : isDarkTheme ? 'bg-gray-600 text-white' : 'bg-gray-300 text-gray-700'
                              }`}>
                                {user.is_admin ? '👑' : (user.screen_name || user.username).charAt(0).toUpperCase()}
                              </div>
                            )}

                            <div className="flex-1 min-w-0">
                              <div className="flex items-center space-x-1">
                                <p className={`text-sm font-medium truncate ${
                                  isDarkTheme ? 'text-gray-300' : 'text-gray-600'
                                }`}>
                                  {user.screen_name || user.username} 👁️
                                </p>
                                {user.is_admin && (
                                  <span className="text-xs">👑</span>
                                )}
                              </div>
                              
                              <p className={`text-xs truncate ${
                                isDarkTheme ? 'text-gray-500' : 'text-gray-400'
                              }`}>
                                {user.role || 'Member'}
                              </p>
                            </div>
                          </div>
                        ))}
                      </>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Notifications Tab */}
        {activeTab === 'notifications' && (
          <div className="flex-1 overflow-y-auto max-h-screen">
            <NotificationsTab 
              notifications={notifications}
              isDarkTheme={isDarkTheme}
              currentUser={currentUser}
              onMarkAsRead={markNotificationAsRead}
              onDeleteNotification={deleteNotification}
            />
          </div>
        )}

        {/* Achievements Tab */}
        {activeTab === 'achievements' && (
          <div className="flex-1 overflow-y-auto max-h-screen">
            <AchievementsTab 
              currentUser={currentUser}
              isDarkTheme={isDarkTheme}
            />
          </div>
        )}

        {/* Portfolio Tab */}
        {activeTab === 'portfolio' && (
          <div className="flex-1 overflow-y-auto space-y-6 p-4 max-h-screen">
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
          <div className="flex-1 overflow-y-auto max-h-screen">
            <FavoritesTab 
              favorites={favorites}
              addToFavorites={addToFavorites}
              removeFromFavorites={removeFromFavorites}
              isDarkTheme={isDarkTheme}
            />
          </div>
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

        {/* Profile Tab - Twitter/X Style */}
        {activeTab === 'profile' && (
          <div className="flex-1 overflow-y-auto max-h-screen" data-testid="profile-tab">

            {showProfileCustomization ? (
              <div className="p-4">
                <button
                  onClick={() => setShowProfileCustomization(false)}
                  className={`mb-4 px-4 py-2 rounded-lg font-medium transition-colors ${
                    isDarkTheme ? 'bg-white/10 text-white hover:bg-white/20' : 'bg-gray-100 text-gray-900 hover:bg-gray-200'
                  }`}
                  data-testid="back-to-profile-btn"
                >
                  &larr; Back to Profile
                </button>
                <ProfileCustomization 
                  currentUser={currentUser}
                  isDarkTheme={isDarkTheme}
                  onUpdate={() => {
                    setShowProfileCustomization(false);
                    refreshUserProfile();
                    fetchUserXPData();
                  }}
                />
              </div>
            ) : (
              <div className={`max-w-2xl mx-auto ${isDarkTheme ? 'bg-gray-900' : 'bg-white'}`}>
                {/* Banner Image */}
                <div className="relative" data-testid="profile-banner">
                  {currentUser?.profile_banner ? (
                    <img
                      src={currentUser.profile_banner}
                      alt="Profile banner"
                      className="w-full h-48 sm:h-56 object-cover"
                    />
                  ) : (
                    <div className={`w-full h-48 sm:h-56 ${
                      isDarkTheme 
                        ? 'bg-gradient-to-r from-blue-900 via-indigo-900 to-purple-900' 
                        : 'bg-gradient-to-r from-blue-400 via-indigo-400 to-purple-400'
                    }`} />
                  )}
                </div>

                {/* Avatar + Edit Button Row */}
                <div className="relative px-4">
                  {/* Avatar - overlapping banner */}
                  <div className="relative -mt-16 sm:-mt-20 mb-1" data-testid="profile-avatar">
                    <div className="flex items-end justify-between">
                      <div className="relative">
                        {currentUser?.avatar_url ? (
                          <img
                            src={currentUser.avatar_url}
                            alt="Profile"
                            className={`w-28 h-28 sm:w-36 sm:h-36 rounded-full object-cover border-4 ${
                              isDarkTheme ? 'border-gray-900' : 'border-white'
                            } shadow-lg`}
                          />
                        ) : (
                          <div className={`w-28 h-28 sm:w-36 sm:h-36 rounded-full border-4 ${
                            isDarkTheme ? 'border-gray-900' : 'border-white'
                          } shadow-lg flex items-center justify-center text-5xl sm:text-6xl font-bold ${
                            currentUser?.is_admin 
                              ? 'bg-gradient-to-br from-yellow-400 to-orange-500 text-white' 
                              : 'bg-gradient-to-br from-blue-500 to-indigo-600 text-white'
                          }`}>
                            {currentUser?.username?.charAt(0).toUpperCase()}
                          </div>
                        )}
                        {/* Level Badge */}
                        <div className="absolute -bottom-1 -right-1 bg-blue-500 text-white rounded-full w-10 h-10 flex items-center justify-center font-bold text-sm shadow-md border-2 border-gray-900">
                          {userXP.level}
                        </div>
                      </div>

                      {/* Action Buttons */}
                      <div className="flex gap-2 pb-2">
                        <button
                          onClick={() => setShowProfileCustomization(true)}
                          className={`px-5 py-2 rounded-full font-semibold text-sm transition-colors border ${
                            isDarkTheme 
                              ? 'border-gray-600 text-white hover:bg-white/10' 
                              : 'border-gray-300 text-gray-900 hover:bg-gray-50'
                          }`}
                          data-testid="edit-profile-btn"
                        >
                          Edit profile
                        </button>
                      </div>
                    </div>
                  </div>

                  {/* Name & Handle */}
                  <div className="mt-2" data-testid="profile-info">
                    <h1 className={`text-xl sm:text-2xl font-extrabold leading-tight ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
                      {currentUser?.screen_name || currentUser?.real_name || currentUser?.username}
                      {currentUser?.is_admin && (
                        <span className="ml-2 inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-yellow-500/20 text-yellow-400 border border-yellow-500/30">
                          Admin
                        </span>
                      )}
                    </h1>
                    <p className={`text-sm sm:text-base ${isDarkTheme ? 'text-gray-500' : 'text-gray-500'}`}>
                      @{currentUser?.username}
                    </p>
                  </div>

                  {/* Bio */}
                  {currentUser?.bio && (
                    <p className={`mt-3 text-sm sm:text-base leading-relaxed ${isDarkTheme ? 'text-gray-200' : 'text-gray-800'}`} data-testid="profile-bio">
                      {currentUser.bio}
                    </p>
                  )}

                  {/* Meta Row: Location, Joined Date, Role */}
                  <div className={`flex flex-wrap gap-x-4 gap-y-1 mt-3 text-sm ${isDarkTheme ? 'text-gray-500' : 'text-gray-500'}`}>
                    {currentUser?.location && currentUser?.show_location && (
                      <span className="flex items-center gap-1">
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" /></svg>
                        {currentUser.location}
                      </span>
                    )}
                    <span className="flex items-center gap-1">
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>
                      Joined {currentUser?.created_at ? new Date(currentUser.created_at).toLocaleDateString('en-US', { month: 'long', year: 'numeric' }) : 'Unknown'}
                    </span>
                    <span className="flex items-center gap-1">
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
                      {currentUser?.role === 'admin' ? 'Admin' : currentUser?.membership_plan || currentUser?.role || 'Member'}
                    </span>
                  </div>

                  {/* Followers / Following Row */}
                  <div className={`flex gap-5 mt-3 text-sm ${isDarkTheme ? 'text-gray-400' : 'text-gray-600'}`} data-testid="profile-follow-stats">
                    <span>
                      <span className={`font-bold ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
                        {currentUser?.following_count || currentUser?.following?.length || 0}
                      </span> Following
                    </span>
                    <span>
                      <span className={`font-bold ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
                        {currentUser?.follower_count || currentUser?.followers?.length || 0}
                      </span> Followers
                    </span>
                  </div>

                  {/* Trading Style Tags */}
                  {currentUser?.trading_style_tags && currentUser.trading_style_tags.length > 0 && (
                    <div className="flex flex-wrap gap-2 mt-4" data-testid="profile-tags">
                      {currentUser.trading_style_tags.map(tag => {
                        const tagStyles = {
                          day_trader: { label: 'Day Trader', color: 'bg-red-500/20 text-red-400 border-red-500/30' },
                          diamond_hands: { label: 'Diamond Hands', color: 'bg-blue-500/20 text-blue-400 border-blue-500/30' },
                          swing_trader: { label: 'Swing Trader', color: 'bg-green-500/20 text-green-400 border-green-500/30' },
                          technical_analyst: { label: 'Technical Analyst', color: 'bg-purple-500/20 text-purple-400 border-purple-500/30' },
                          news_trader: { label: 'News Trader', color: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30' },
                          growth_investor: { label: 'Growth Investor', color: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30' },
                          value_investor: { label: 'Value Investor', color: 'bg-indigo-500/20 text-indigo-400 border-indigo-500/30' },
                          momentum_trader: { label: 'Momentum Trader', color: 'bg-pink-500/20 text-pink-400 border-pink-500/30' },
                          balanced_trader: { label: 'Balanced Trader', color: 'bg-gray-500/20 text-gray-400 border-gray-500/30' },
                          algo_trader: { label: 'Algo Trader', color: 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30' },
                          mobile_trader: { label: 'Mobile Trader', color: 'bg-orange-500/20 text-orange-400 border-orange-500/30' },
                          contrarian: { label: 'Contrarian', color: 'bg-violet-500/20 text-violet-400 border-violet-500/30' }
                        };
                        const style = tagStyles[tag] || { label: tag, color: 'bg-gray-500/20 text-gray-400 border-gray-500/30' };
                        return (
                          <span key={tag} className={`px-3 py-1 rounded-full text-xs font-medium border ${style.color}`}>
                            {style.label}
                          </span>
                        );
                      })}
                    </div>
                  )}
                </div>

                {/* Divider */}
                <div className={`mt-5 border-t ${isDarkTheme ? 'border-gray-800' : 'border-gray-100'}`} />

                {/* Stats Cards */}
                <div className="px-4 py-5">
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3" data-testid="profile-stats">
                    <div className={`p-4 rounded-xl text-center ${isDarkTheme ? 'bg-gray-800/80' : 'bg-gray-50'}`}>
                      <div className={`text-2xl font-bold ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
                        {userXP.level}
                      </div>
                      <div className={`text-xs mt-1 ${isDarkTheme ? 'text-gray-500' : 'text-gray-500'}`}>Level</div>
                    </div>
                    <div className={`p-4 rounded-xl text-center ${isDarkTheme ? 'bg-gray-800/80' : 'bg-gray-50'}`}>
                      <div className={`text-2xl font-bold ${
                        (currentUser?.total_profit || 0) >= 0 
                          ? 'text-green-400' 
                          : 'text-red-400'
                      }`}>
                        {formatCurrency(currentUser?.total_profit || 0)}
                      </div>
                      <div className={`text-xs mt-1 ${isDarkTheme ? 'text-gray-500' : 'text-gray-500'}`}>Total P&L</div>
                    </div>
                    <div className={`p-4 rounded-xl text-center ${isDarkTheme ? 'bg-gray-800/80' : 'bg-gray-50'}`}>
                      <div className={`text-2xl font-bold ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
                        {currentUser?.win_percentage?.toFixed(0) || 0}%
                      </div>
                      <div className={`text-xs mt-1 ${isDarkTheme ? 'text-gray-500' : 'text-gray-500'}`}>Win Rate</div>
                    </div>
                    <div className={`p-4 rounded-xl text-center ${isDarkTheme ? 'bg-gray-800/80' : 'bg-gray-50'}`}>
                      <div className={`text-2xl font-bold ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
                        {currentUser?.trades_count || 0}
                      </div>
                      <div className={`text-xs mt-1 ${isDarkTheme ? 'text-gray-500' : 'text-gray-500'}`}>Trades</div>
                    </div>
                  </div>

                  {/* XP Progress */}
                  <div className="mt-4">
                    <XPProgressBar 
                      currentXP={userXP.experience_points} 
                      level={userXP.level} 
                      isDarkTheme={isDarkTheme} 
                    />
                  </div>
                </div>

                {/* Divider */}
                <div className={`border-t ${isDarkTheme ? 'border-gray-800' : 'border-gray-100'}`} />

                {/* Achievements */}
                {currentUser?.achievements && currentUser.achievements.length > 0 && (
                  <div className="px-4 py-5" data-testid="profile-achievements">
                    <h3 className={`text-base font-bold mb-3 ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
                      Achievements
                    </h3>
                    <div className="flex flex-wrap gap-2">
                      {currentUser.achievements.map(achievement => {
                        const achievementMap = {
                          chatterbox: { icon: '💬', label: 'Chatterbox' },
                          first_blood: { icon: '🩸', label: 'First Blood' },
                          team_member_3m: { icon: '🤝', label: '3 Month Member' },
                          team_member_8m: { icon: '🏆', label: '8 Month Member' },
                          profitable_trader: { icon: '💰', label: 'Profitable Trader' },
                          heart_giver: { icon: '❤️', label: 'Heart Giver' },
                          streak_master: { icon: '🔥', label: 'Streak Master' },
                          social_butterfly: { icon: '🦋', label: 'Social Butterfly' }
                        };
                        const info = achievementMap[achievement] || { icon: '🏅', label: achievement.replace(/_/g, ' ') };
                        return (
                          <span key={achievement} className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium ${
                            isDarkTheme 
                              ? 'bg-yellow-500/10 text-yellow-400 border border-yellow-500/20' 
                              : 'bg-yellow-50 text-yellow-700 border border-yellow-200'
                          }`}>
                            <span>{info.icon}</span>
                            {info.label}
                          </span>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* Divider */}
                <div className={`border-t ${isDarkTheme ? 'border-gray-800' : 'border-gray-100'}`} />

                {/* Account Details */}
                <div className="px-4 py-5" data-testid="profile-details">
                  <h3 className={`text-base font-bold mb-3 ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
                    Account Details
                  </h3>
                  <div className="space-y-3">
                    {[
                      { label: 'Email', value: currentUser?.email },
                      { label: 'Real Name', value: currentUser?.real_name || 'Not set' },
                      { label: 'Screen Name', value: currentUser?.screen_name || 'Not set' },
                      { label: 'Login Streak', value: `${currentUser?.daily_login_streak || 0} days` },
                      { label: 'XP', value: `${userXP.experience_points.toLocaleString()} XP` },
                    ].map(item => (
                      <div key={item.label} className={`flex justify-between items-center py-2 border-b last:border-0 ${
                        isDarkTheme ? 'border-gray-800' : 'border-gray-100'
                      }`}>
                        <span className={`text-sm ${isDarkTheme ? 'text-gray-500' : 'text-gray-500'}`}>{item.label}</span>
                        <span className={`text-sm font-medium ${isDarkTheme ? 'text-gray-200' : 'text-gray-800'}`}>{item.value}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Action Buttons */}
                <div className="px-4 pb-6">
                  <div className="flex gap-3">
                    <button
                      onClick={() => setShowChangePassword(true)}
                      className={`flex-1 py-3 rounded-xl font-medium text-sm transition-colors ${
                        isDarkTheme 
                          ? 'bg-gray-800 text-white hover:bg-gray-700' 
                          : 'bg-gray-100 text-gray-900 hover:bg-gray-200'
                      }`}
                      data-testid="change-password-btn"
                    >
                      Change Password
                    </button>
                    <button
                      onClick={logout}
                      className="flex-1 py-3 rounded-xl font-medium text-sm bg-red-500/10 text-red-400 hover:bg-red-500/20 transition-colors"
                      data-testid="logout-btn"
                    >
                      Log Out
                    </button>
                  </div>
                </div>
              </div>
            )}
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
                    placeholder="Enter new password (min 6 characters)"
                    value={resetPasswordForm.new_password}
                    onChange={(e) => setResetPasswordForm({...resetPasswordForm, new_password: e.target.value})}
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
                    placeholder="Confirm new password"
                    value={resetPasswordForm.confirm_password}
                    onChange={(e) => setResetPasswordForm({...resetPasswordForm, confirm_password: e.target.value})}
                    required
                    minLength="6"
                  />
                </div>
                
                <div className={`p-3 rounded-lg border ${
                  isDarkTheme 
                    ? 'bg-blue-500/10 border-blue-500/30 text-blue-400' 
                    : 'bg-blue-50 border-blue-200 text-blue-600'
                }`}>
                  <p className="text-sm">
                    Enter the email linked to your account to set a new password.
                  </p>
                </div>
                
                {resetPasswordForm.new_password && resetPasswordForm.confirm_password && 
                  resetPasswordForm.new_password !== resetPasswordForm.confirm_password && (
                  <div className="p-2 rounded-lg bg-red-500/10 border border-red-500/30">
                    <p className="text-sm text-red-400">Passwords do not match</p>
                  </div>
                )}
                
                <div className="flex space-x-4 pt-4">
                  <button
                    type="submit"
                    disabled={!resetPasswordForm.email || !resetPasswordForm.new_password || resetPasswordForm.new_password !== resetPasswordForm.confirm_password}
                    className="flex-1 bg-gradient-to-r from-blue-600 to-purple-600 text-white py-3 rounded-lg font-semibold hover:from-blue-700 hover:to-purple-700 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Reset Password
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setShowForgotPassword(false);
                      setResetPasswordForm({ email: '', new_password: '', confirm_password: '' });
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

      {/* Public Profile Modal */}
      {viewingUserId && (
        <PublicProfile 
          userId={viewingUserId}
          onClose={closeProfileView}
          isDarkTheme={isDarkTheme}
          currentUser={currentUser}
        />
      )}
        </div>
      </MobileErrorBoundary>
    );
  } catch (error) {
    console.error('🚨 Critical Mobile Rendering Error:', error);
    return (
      <div className="min-h-screen bg-red-900 text-white p-8 flex items-center justify-center">
        <div className="text-center">
          <h1 className="text-2xl font-bold mb-4">Critical Mobile App Error</h1>
          <p className="mb-4">The mobile app encountered a critical error.</p>
          <button 
            onClick={() => window.location.reload()} 
            className="bg-white text-red-900 px-6 py-2 rounded-lg hover:bg-gray-100"
          >
            Reload App
          </button>
        </div>
      </div>
    );
  }
}

export default App;