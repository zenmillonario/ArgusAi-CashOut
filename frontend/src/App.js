import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import ChatTab from './ChatTab';
import ChatInput from './ChatInput';
import PortfolioTab from './PortfolioTab';
import UserList from './UserList';
import FavoritesTab from './FavoritesTab';
import AchievementsTab from './AchievementsTab';
import NotificationsTab from './NotificationsTab';
import QuoteObservation from './QuoteObservation';
import ProfileCustomization from './ProfileCustomization';
import PublicProfile from './PublicProfile';
import XPProgressBar from './XPProgressBar';
import AssetAllocationWheel from './AssetAllocationWheel';
import LoadingScreen from './LoadingScreen';
import { formatPrice, formatPnL, formatCurrency } from './utils';
import notificationService from './firebase-config';
import { sameSession, sessionHeaders, removeStoredSession, closeSessionTransport } from './sessionAuth.mjs';
import capacitorManager from './capacitor-utils';
import './App.css';
import BotTabs from './nautilus/BotTabs';
import BotTabContainer from './nautilus/BotTabContainer';
import BotRunBanner from './nautilus/BotRunBanner';
import useBotAnnouncements from './nautilus/useBotAnnouncements';
import { normalizeBotAnnouncement } from './nautilus/botAnnouncements.mjs';
import StocksWorkspace from './nautilus/StocksWorkspace';
import useStockAlerts from './useStockAlerts';
import { readStockAlertLink } from './stockNotifications.mjs';
import AppNavigation, { TradingTools, CommunityNavigation, MembersDirectory } from './social/AppNavigation';
import { appSection, unreadCount, reactionType, reactionSummary, persistReaction, winDraft } from './social/socialModel.mjs';
import BillingPanel, { AdminBillingPanel } from './billing/BillingPanel';
import AdminTrafficPanel from './admin/AdminTrafficPanel';
import { MEMBERSHIP_PLANS, membershipPlan, moneyFromCents, signupPlanIntent, billingReturnIntent, normalizeBillingProof,
  readBillingProof, saveBillingProof, clearBillingProof, memberBillingCredential, responseBelongsToSession } from './billing/billingModel.mjs';
import usePracticeEvent from './practiceEvent/usePracticeEvent';
import { PracticeEventInvitation, PracticeEventRequestDialog, PracticeEventVerification, PracticeEventMemberBanner } from './practiceEvent/PracticeEvent';
import { EVENT_REGISTRATION_PLAN, eventTokenFromLocation, withoutEventToken, eventDeadlineLabel, practiceEventError, requestPracticeEventLink, eventRegistrationPayload } from './practiceEvent/eventModel.mjs';

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
  const activeUserRef = useRef(null);
  activeUserRef.current = currentUser;
  const [billingPlanId, setBillingPlanId] = useState(() => signupPlanIntent(window.location.search));
  const [openBillingOnLogin] = useState(() => billingReturnIntent(window.location.search));
  const [billingProof, setBillingProof] = useState(() => readBillingProof(window.sessionStorage));
  const billingProofRef = useRef(billingProof);
  billingProofRef.current = billingProof;
  const authAttemptRef = useRef(0);
  const [membershipPaymentRequired, setMembershipPaymentRequired] = useState(false);
  const membershipRequiredRef = useRef(false);
  membershipRequiredRef.current = membershipPaymentRequired;
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  
  // PERFORMANCE OPTIMIZATION: Loading states for better UX
  const [isLoggingIn, setIsLoggingIn] = useState(false);
  const [messages, setMessages] = useState([]);
  const [messagesLoading, setMessagesLoading] = useState(true);
  // Expose setMessages for ChatTab's load-more feature
  window.__setMessages = setMessages;
  const [newMessage, setNewMessage] = useState('');
  const [isConnected, setIsConnected] = useState(false);
  const [connectionMode, setConnectionMode] = useState('disconnected'); // 'websocket', 'polling', 'disconnected'
  const [showLogin, setShowLogin] = useState(true);
  const [loginForm, setLoginForm] = useState(() => ({ username: '', email: '', password: '', real_name: '', membership_plan: membershipPlan(signupPlanIntent(window.location.search))?.registrationLabel || '' }));
  const [rememberMe, setRememberMe] = useState(false);
  const [isRegistering, setIsRegistering] = useState(() => Boolean(signupPlanIntent(window.location.search)));
  const [showScrollButton, setShowScrollButton] = useState(false);
  const [mobileUserListOpen, setMobileUserListOpen] = useState(false); // Track mobile user list state
  const [pendingUsers, setPendingUsers] = useState([]);
  const [allUsers, setAllUsers] = useState([]);
  const [billingReviewSelection, setBillingReviewSelection] = useState({ userId: '', version: 0 });
  const [communityMembers, setCommunityMembers] = useState([]);
  const [memberDirectoryError, setMemberDirectoryError] = useState('');
  const [showAdminPanel, setShowAdminPanel] = useState(false);
  const [activeTab, setActiveTab] = useState(() => readStockAlertLink(window.location.search) ? 'stocks' : signupPlanIntent(window.location.search) || billingReturnIntent(window.location.search) ? 'profile' : 'bot-BTC');
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
  const [resetTokenForm, setResetTokenForm] = useState(() => {
    const params = new URLSearchParams(window.location.search);
    return {
      token: params.get('reset_token') || (window.location.pathname === '/reset-password' ? params.get('token') : '') || '',
      new_password: '', confirm_password: ''
    };
  });
  const [passwordRecoveryBusy, setPasswordRecoveryBusy] = useState(false);
  const [eventToken, setEventToken] = useState(() => eventTokenFromLocation(window.location));
  const [eventRequest, setEventRequest] = useState({ open: false, email: '', message: '', error: '', version: 0 });
  const practiceEvent = usePracticeEvent(API, currentUser, requireMembershipForSession);
  const isEventRegistration = isRegistering && loginForm.membership_plan === EVENT_REGISTRATION_PLAN;

  useEffect(() => {
    if (eventTokenFromLocation(window.location)) window.history.replaceState({}, '', withoutEventToken(window.location.href));
  }, []);

  useEffect(() => {
    const url = new URL(window.location.href);
    if (url.searchParams.has('reset_token') || (url.pathname === '/reset-password' && url.searchParams.has('token'))) {
      url.searchParams.delete('reset_token');
      url.searchParams.delete('token');
      window.history.replaceState({}, '', `${url.pathname}${url.search}${url.hash}`);
    }
  }, []);

  useEffect(() => {
    // Credentials accompany only requests to this app's API, never other URLs.
    const interceptor = axios.interceptors.request.use(config => {
      const session = activeUserRef.current;
      const explicitBilling = config.headers?.get?.('X-Billing-Token') || config.headers?.['X-Billing-Token'] || config.headers?.['x-billing-token'];
      if (session?.id && session?.active_session_id && !explicitBilling) {
        const endpoint = new URL(config.url || '', window.location.origin);
        const expected = new URL(API, window.location.origin);
        if (endpoint.origin === expected.origin &&
            (endpoint.pathname === expected.pathname || endpoint.pathname.startsWith(`${expected.pathname}/`))) {
          config.headers = {
            ...sessionHeaders(session),
            ...config.headers
          };
        }
      }
      return config;
    });
    const responseInterceptor = axios.interceptors.response.use(response => response, error => {
      const detail = error.response?.data?.detail;
      const session = activeUserRef.current;
      if (error.response?.status === 403 && detail?.code === 'membership_required' &&
          responseBelongsToSession(error.config?.headers, session)) {
        requireMembershipForSession(session);
      }
      return Promise.reject(error);
    });
    return () => { axios.interceptors.request.eject(interceptor); axios.interceptors.response.eject(responseInterceptor); };
  }, []);
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
  const [audioContext, setAudioContext] = useState(null);
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
  const [currentStockQuote, setCurrentStockQuote] = useState(null);
  const [priceLoading, setPriceLoading] = useState(false);
  const [replyToMessage, setReplyToMessage] = useState(null);
  const [notifications, setNotifications] = useState([]);
  const [messageReactions, setMessageReactions] = useState({});
  const reactionCache = useRef({ loaded: new Set(), pending: new Set(), mine: {} });
  const [communityError, setCommunityError] = useState('');
  const [winComposerOpen, setWinComposerOpen] = useState(false);
  const [composerFocus, setComposerFocus] = useState(0);
  const lastTradingRoom = useRef('bot-BTC');
  if (activeTab.startsWith('bot-') || activeTab === 'stocks') lastTradingRoom.current = activeTab;
  const section = appSection(activeTab);
  const [onlineUsers, setOnlineUsers] = useState([]);
  const [showUserList, setShowUserList] = useState(true);
  const [userXP, setUserXP] = useState({ experience_points: 0, level: 1 });
  const [showProfileCustomization, setShowProfileCustomization] = useState(false);
  const [viewingUserId, setViewingUserId] = useState(null);
  const wsRef = useRef(null);
  const messagesEndRef = useRef(null);
  // Keep the member credential for billing, while alert callbacks see no
  // eligible member during a membership gate (including focus callbacks).
  const stockUserRef = useRef(null);
  stockUserRef.current = membershipPaymentRequired ? null : currentUser;
  const stocks = useStockAlerts({ currentUser: membershipPaymentRequired ? null : currentUser, activeUserRef: stockUserRef, activeTab, setActiveTab, apiBase: API });
  const botAnnouncements = useBotAnnouncements({ currentUser: membershipPaymentRequired ? null : currentUser,
    activeUserRef: stockUserRef, activeTab, apiBase: API });
  const openBotAnnouncement = raw => {
    const notice = normalizeBotAnnouncement(raw);
    if (notice) { setActiveTab(notice.tab); botAnnouncements.dismiss(); }
  };

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
            clearBillingProof(window.sessionStorage);
            billingProofRef.current = null;
            setBillingProof(null);
            setCurrentUser(user);
            setShowLogin(false);
            
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
      try {
        const savedFavorites = JSON.parse(localStorage.getItem(`cashoutai_favorites_${currentUser.id}`) || '[]');
        setFavorites(Array.isArray(savedFavorites) ? savedFavorites.filter(symbol => typeof symbol === 'string') : []);
      } catch (_) { setFavorites([]); }
      
      // Load notifications for the user
      loadNotifications();
    }
  }, [currentUser?.id, currentUser?.active_session_id]);

  const loadNotifications = async () => {
    const session = activeUserRef.current;
    if (!session) return;
    try {
      const response = await axios.get(`${API}/users/${session.id}/notifications`, { headers: sessionHeaders(session) });
      if (sameSession(activeUserRef.current, session)) setNotifications(response.data);
    } catch (error) {
      console.error('Error loading notifications:', error);
    }
  };

  const markNotificationAsRead = async (notificationId) => {
    const session = activeUserRef.current;
    if (!session) return;
    try {
      await axios.put(`${API}/users/${session.id}/notifications/${notificationId}/read`, null, { headers: sessionHeaders(session) });
      if (!sameSession(activeUserRef.current, session)) return false;
      setNotifications(prev => 
        prev.map(notification => 
          notification.id === notificationId 
            ? { ...notification, read: true }
            : notification
        )
      );
      return true;
    } catch (error) {
      console.error('Error marking notification as read:', error);
      return false;
    }
  };

  const deleteNotification = async (notificationId) => {
    const session = activeUserRef.current;
    if (!session) return;
    try {
      await axios.delete(`${API}/users/${session.id}/notifications/${notificationId}`, { headers: sessionHeaders(session) });
      if (!sameSession(activeUserRef.current, session)) return;
      setNotifications(prev => prev.filter(notification => notification.id !== notificationId));
      return true;
    } catch (error) {
      console.error('Error deleting notification:', error);
      return false;
    }
  };

  const markAllNotificationsAsRead = async () => {
    const session = activeUserRef.current;
    if (!session) return false;
    try {
      await axios.post(`${API}/users/${session.id}/notifications/read-all`, null, { headers: sessionHeaders(session) });
      if (!sameSession(activeUserRef.current, session)) return false;
      setNotifications(previous => previous.map(item => ({ ...item, read: true })));
      return true;
    } catch (_) { return false; }
  };

  const openNotification = notification => {
    if (!notification.read) markNotificationAsRead(notification.id);
    if (notification.type === 'follow' && notification.data?.follower_id) setViewingUserId(notification.data.follower_id);
    else if (notification.type === 'achievement') setActiveTab('achievements');
    else setActiveTab('chat');
  };

  function shareWin() {
    setActiveTab('chat');
    setNewMessage(previous => winDraft(previous));
    if (!newMessage.trim()) setReplyToMessage(null);
    setWinComposerOpen(true);
    setComposerFocus(previous => previous + 1);
  }

  useEffect(() => {
    if (activeTab !== 'chat' || !composerFocus) return undefined;
    const frame = window.requestAnimationFrame(() => {
      const input = document.querySelector('.cashout-chat-composer textarea');
      input?.focus();
      if (input) input.setSelectionRange(input.value.length, input.value.length);
    });
    return () => window.cancelAnimationFrame(frame);
  }, [activeTab, composerFocus]);

  useEffect(() => {
    if (activeTab === 'notifications' && currentUser && !membershipPaymentRequired) loadNotifications();
  }, [activeTab, currentUser?.id, currentUser?.active_session_id, membershipPaymentRequired]);

  useEffect(() => {
    const session = activeUserRef.current;
    if (section !== 'community' || !session || membershipPaymentRequired) return undefined;
    let cancelled = false;
    setMemberDirectoryError('');
    axios.get(`${API}/community/members`, { headers: sessionHeaders(session) }).then(response => {
      if (!cancelled && sameSession(activeUserRef.current, session)) setCommunityMembers(response.data.users || []);
    }).catch(() => {
      if (!cancelled && sameSession(activeUserRef.current, session)) setMemberDirectoryError('The member directory could not load. Open Community again to retry.');
    });
    return () => { cancelled = true; };
  }, [section, currentUser?.id, currentUser?.active_session_id, membershipPaymentRequired]);

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

  async function loadReactionState(session, messageId) {
    if (!messageId || !sameSession(activeUserRef.current, session)) return;
    const cache = reactionCache.current;
    try {
      const response = await axios.get(`${API}/messages/${encodeURIComponent(messageId)}/reactions`, { headers: sessionHeaders(session) });
      if (!sameSession(activeUserRef.current, session) || cache !== reactionCache.current) return;
      const summary = reactionSummary(response.data, session.id);
      cache.mine[messageId] = summary.mine;
      cache.loaded.add(messageId);
      setMessageReactions(previous => ({ ...previous, [messageId]: summary.counts }));
    } catch (_) { cache.loaded.delete(messageId); }
  }

  const addReaction = async (messageId, reaction) => {
    const session = activeUserRef.current;
    const type = reactionType(reaction);
    if (!session || !type || !messages.some(message => message.id === messageId)) return;
    const cache = reactionCache.current;
    if (cache.pending.has(messageId)) return;
    cache.pending.add(messageId); setCommunityError('');
    try {
      const summary = await persistReaction({ client: axios, api: API, session, currentSession: () => activeUserRef.current,
        messageId, reaction: type, remove: (cache.mine[messageId] || []).includes(type) });
      if (!summary || !sameSession(activeUserRef.current, session) || cache !== reactionCache.current) return;
      cache.mine[messageId] = summary.mine; cache.loaded.add(messageId);
      setMessageReactions(previous => ({ ...previous, [messageId]: summary.counts }));
    } catch (_) {
      if (sameSession(activeUserRef.current, session)) setCommunityError('Your reaction could not be saved. Please try again.');
    } finally { cache.pending.delete(messageId); }
  };

  useEffect(() => {
    reactionCache.current = { loaded: new Set(), pending: new Set(), mine: {} };
    setMessageReactions({}); setCommunityError('');
  }, [currentUser?.id, currentUser?.active_session_id]);

  useEffect(() => {
    if (activeTab !== 'chat' || !currentUser || membershipPaymentRequired) return undefined;
    const session = { id: currentUser.id, active_session_id: currentUser.active_session_id };
    const cache = reactionCache.current;
    const missing = messages.slice(-50).filter(message => message.id && !cache.loaded.has(message.id));
    // Bounded initial reads; live reaction_updated events refresh individual rows.
    let cancelled = false;
    (async () => {
      for (let start = 0; start < missing.length; start += 5) {
        if (cancelled || !sameSession(activeUserRef.current, session)) return;
        await Promise.allSettled(missing.slice(start, start + 5).map(message => loadReactionState(session, message.id)));
      }
    })();
    return () => { cancelled = true; };
  }, [activeTab, messages, currentUser?.id, currentUser?.active_session_id, membershipPaymentRequired]);

  // Fetch only the visible journal's selected symbol. A provider observation is
  // reference data, not a verified fill and never an automatic manual entry.
  useEffect(() => {
    let cancelled = false;
    const session = activeUserRef.current;
    setCurrentStockPrice(null);
    setCurrentStockQuote(null);
    setPriceLoading(false);
    if (activeTab !== 'practice' || !tradeForm.symbol || !session || membershipPaymentRequired) return undefined;
    const debounceTimer = setTimeout(() => {
      if (cancelled) return;
      setPriceLoading(true);
      axios.get(`${API}/stock/${encodeURIComponent(tradeForm.symbol)}`, { headers: sessionHeaders(session) }).then(response => {
        if (!cancelled && sameSession(activeUserRef.current, session)) {
          setCurrentStockPrice(response.data.price);
          setCurrentStockQuote(response.data);
        }
      }).catch(() => {
        if (!cancelled && sameSession(activeUserRef.current, session)) { setCurrentStockPrice(null); setCurrentStockQuote(null); }
      }).finally(() => {
        if (!cancelled && sameSession(activeUserRef.current, session)) setPriceLoading(false);
      });
    }, 500);
    return () => { cancelled = true; clearTimeout(debounceTimer); };
  }, [tradeForm.symbol, activeTab, currentUser?.id, currentUser?.active_session_id, membershipPaymentRequired]);

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





  // Each connection belongs to one captured login, including its fallback polls.
  useEffect(() => {
    if (!currentUser?.id || !currentUser?.active_session_id || membershipPaymentRequired) return;
    const session = { id: currentUser.id, active_session_id: currentUser.active_session_id };
    const headers = sessionHeaders(session);
    let disposed = false;
    let polling = null;
    let checkingSession = false;
    let checkingMessages = false;
    const isCurrent = () => !disposed && !membershipRequiredRef.current && sameSession(activeUserRef.current, session);
    const expireSession = () => {
      if (!isCurrent()) return;
      clearLocalSession(session);
      alert('Your session has ended. Sign in again to continue.');
    };
    const startPolling = () => {
      if (!isCurrent() || polling) return;
      const checkSession = async () => {
        if (!isCurrent() || checkingSession) return;
        checkingSession = true;
        try {
          const response = await axios.get(`${API}/users/${session.id}/session-status`, { headers });
          if (!isCurrent()) return;
          if (!response.data.valid) { expireSession(); return; }
          setIsConnected(true);
          setConnectionMode('polling');
        } catch (error) {
          if (!isCurrent()) return;
          if (error.response?.status === 401) { expireSession(); return; }
          setIsConnected(false);
          setConnectionMode('disconnected');
        } finally { checkingSession = false; }
      };
      const checkMessages = async () => {
        if (!isCurrent() || checkingMessages) return;
        checkingMessages = true;
        try {
          const response = await axios.get(`${API}/messages?limit=50&user_id=${session.id}`, { headers });
          if (!isCurrent()) return;
          setMessages(previous => {
            if (!isCurrent()) return previous;
            const ids = new Set(previous.map(message => message.id));
            const incoming = response.data.filter(message => !ids.has(message.id));
            if (incoming.some(message => message.is_admin && message.user_id !== session.id)) playSimpleAdminSound();
            return [...previous, ...incoming];
          });
        } catch (error) {
          if (isCurrent() && error.response?.status === 401) expireSession();
        } finally { checkingMessages = false; }
      };
      polling = { type: 'polling', sessionInterval: setInterval(checkSession, 10000), messageInterval: setInterval(checkMessages, 8000) };
      wsRef.current = polling;
      checkSession();
    };
    const protocol = BACKEND_URL.startsWith('https://') || (!BACKEND_URL && window.location.protocol === 'https:') ? 'wss://' : 'ws://';
    const host = BACKEND_URL ? BACKEND_URL.replace(/^https?:\/\//, '').replace(/\/$/, '') : window.location.host;
    const baseUrl = capacitorManager.isNative ? capacitorManager.getWebSocketUrl(BACKEND_URL) : `${protocol}${host}/api/ws`;
    const ws = new WebSocket(`${baseUrl}/${session.id}/${session.active_session_id}`);
    wsRef.current = ws;
    ws.onopen = () => {
      if (!isCurrent()) return;
      closeSessionTransport(polling);
      polling = null;
      wsRef.current = ws;
      setIsConnected(true);
      setConnectionMode('websocket');
      ws.send(JSON.stringify({ type: 'heartbeat' }));
    };
    ws.onmessage = async event => {
      if (!isCurrent()) return;
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'session_invalidated') {
          expireSession();
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
        } else if (data.type === 'reaction_updated' && data.message_id) {
            await loadReactionState(session, data.message_id);
        } else if (data.type === 'admin_notification') {
            // New admin notification handling
            console.log('🔔 Admin notification received:', data);
            
            playSimpleAdminSound();
            
        } else if (data.type === 'bot_session_started') {
            botAnnouncements.receive(data.notice);
        } else if (data.type === 'notification') {
            // New notification received
            console.log('🔔 Notification received:', data);
            
            // Add to notifications list
            setNotifications(prev => [data.notification, ...prev.filter(item => item.id !== data.notification.id)]);
            
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
      } catch (error) { console.error('Could not read chat event'); }
    };
    ws.onclose = event => {
      if (!isCurrent()) return;
      setIsConnected(false);
      setConnectionMode('disconnected');
      if (event.code === 4403 && event.reason === 'membership_required') { requireMembershipForSession(session); return; }
      if ([1008, 4001, 4002, 4003].includes(event.code)) { expireSession(); return; }
      startPolling();
    };
    ws.onerror = () => { if (isCurrent()) startPolling(); };
    return () => {
      disposed = true;
      closeSessionTransport(polling);
      closeSessionTransport(ws);
      if (wsRef.current === polling || wsRef.current === ws) wsRef.current = null;
    };
  }, [currentUser?.id, currentUser?.active_session_id, membershipPaymentRequired]);

  const loadMessages = async () => {
    const session = activeUserRef.current;
    if (!session || membershipRequiredRef.current) return;
    setMessagesLoading(true);
    try {
      const response = await axios.get(`${API}/messages?user_id=${session.id}&limit=50`, { headers: sessionHeaders(session) });
      if (sameSession(activeUserRef.current, session)) setMessages(response.data || []);
    } catch (error) {
      if (sameSession(activeUserRef.current, session)) setMessages([]);
    } finally {
      if (sameSession(activeUserRef.current, session)) setMessagesLoading(false);
    }
  };

  const loadPendingUsers = async () => {
    const session = activeUserRef.current;
    if (!session?.is_admin) return;
    try {
      const response = await axios.get(`${API}/users/pending`, { headers: sessionHeaders(session) });
      if (sameSession(activeUserRef.current, session)) setPendingUsers(response.data);
    } catch (_) { console.error('Could not load pending users'); }
  };

  const loadAllUsers = async () => {
    const session = activeUserRef.current;
    if (!session?.is_admin) return;
    try {
      const response = await axios.get(`${API}/users`, { headers: sessionHeaders(session) });
      if (sameSession(activeUserRef.current, session)) setAllUsers(response.data);
    } catch (_) { console.error('Could not load users'); }
  };

  const loadUserData = async () => {
    const session = activeUserRef.current;
    if (!session || membershipRequiredRef.current) return;
    const options = { headers: sessionHeaders(session) };
    try {
      const tradesResponse = await axios.get(`${API}/trades/${session.id}`, options);
      if (!sameSession(activeUserRef.current, session)) return;
      setUserTrades(tradesResponse.data);
      const performanceResponse = await axios.get(`${API}/users/${session.id}/performance`, options);
      if (!sameSession(activeUserRef.current, session)) return;
      setUserPerformance(performanceResponse.data);
      const positionsResponse = await axios.get(`${API}/positions/${session.id}`, options);
      if (sameSession(activeUserRef.current, session)) setOpenPositions(positionsResponse.data);
    } catch (_) { console.error('Could not load account data'); }
  };

  const refreshUserProfile = async () => {
    const session = activeUserRef.current;
    if (!session) return;
    try {
      const response = await axios.get(`${API}/users/${session.id}/profile`, { headers: sessionHeaders(session) });
      if (!sameSession(activeUserRef.current, session)) return;
      setCurrentUser(prev => sameSession(prev, session) ? ({
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
      }) : prev);
    } catch (error) {
      console.error('Error refreshing user profile:', error);
    }
  };

  useEffect(() => {
    if (currentUser && !membershipPaymentRequired) {
      loadMessages();
      loadUserData();
      loadPendingUsers();
      loadAllUsers();
      fetchUserXPData(); // Fetch XP data when user loads
    }
  }, [currentUser, membershipPaymentRequired]);

  function forgetBillingAccess() {
    clearBillingProof(window.sessionStorage);
    billingProofRef.current = null;
    setBillingProof(null);
  }

  async function openBillingForCredentials(credentials, attempt) {
    const response = await axios.post(`${API}/billing/auth`, credentials);
    if (authAttemptRef.current !== attempt || activeUserRef.current) return false;
    const proof = normalizeBillingProof(response.data, credentials.username);
    if (!proof) throw new Error('The account payment session could not be verified.');
    saveBillingProof(window.sessionStorage, proof);
    billingProofRef.current = proof;
    setBillingProof(proof);
    setLoginForm(previous => ({ ...previous, username: credentials.username, password: '' }));
    setIsRegistering(false);
    setRememberMe(false);
    return true;
  }

  const handleSubmit = async e => {
    e.preventDefault();
    const attempt = ++authAttemptRef.current;
    const credentials = { username: loginForm.username.trim(), password: loginForm.password };
    const registering = isRegistering;
    const selectedPlan = membershipPlan(loginForm.membership_plan);
    const joiningEvent = registering && loginForm.membership_plan === EVENT_REGISTRATION_PLAN;
    let accountCreated = false;
    setError(null);
    setIsLoggingIn(true);
    try {
      if (registering) {
        if (joiningEvent && practiceEvent.phase !== 'open') { setError('The practice event is not accepting new access. Choose a membership or sign in to your existing account.'); return; }
        if (!joiningEvent && !selectedPlan) { setError('Choose the practice event or a membership option.'); return; }
        await axios.post(`${API}/users/register`, joiningEvent
          ? eventRegistrationPayload(credentials, loginForm.email, practiceEvent.config)
          : { ...credentials, email: loginForm.email, real_name: loginForm.real_name, membership_plan: selectedPlan.registrationLabel });
        if (authAttemptRef.current !== attempt || activeUserRef.current) return;
        accountCreated = true;
        if (joiningEvent) {
          setIsRegistering(false);
          setLoginForm(previous => ({ ...previous, username: credentials.username, email: loginForm.email, password: '' }));
          try {
            const requested = await requestPracticeEventLink(axios, API, loginForm.email, practiceEvent.config);
            if (authAttemptRef.current === attempt && !activeUserRef.current) openEventRequest(loginForm.email, requested.message || 'If this account is eligible, a verification link has been sent to its registered email.');
          } catch (verificationError) {
            if (authAttemptRef.current === attempt && !activeUserRef.current) openEventRequest(loginForm.email, '', `Your account is saved. ${practiceEventError(verificationError)}`);
          }
          return;
        }
        setBillingPlanId(selectedPlan.id);
        setIsRegistering(false);
        await openBillingForCredentials(credentials, attempt);
      } else {
        let response;
        try { response = await axios.post(`${API}/users/login`, credentials); }
        catch (loginError) {
          // A pending or expired account can prove its identity for billing only.
          // That proof never becomes a member session or opens paid rooms.
          if (loginError.response?.status !== 403) throw loginError;
          await openBillingForCredentials(credentials, attempt);
          return;
        }
        if (authAttemptRef.current !== attempt || activeUserRef.current) return;
        if (!response.data?.id || !response.data?.active_session_id) throw new Error('Sign-in could not be verified.');
        forgetBillingAccess();
        membershipRequiredRef.current = false;
        setMembershipPaymentRequired(false);
        activeUserRef.current = response.data;
        setCurrentUser(response.data);
        setShowLogin(false);
        setLoginForm({ username: '', email: '', password: '', real_name: '', membership_plan: selectedPlan?.registrationLabel || '' });
        if (billingPlanId || openBillingOnLogin) setActiveTab('profile');
        const sessionData = {
          ...response.data, rememberMe, sessionCreated: new Date().toISOString(),
          sessionDuration: 365
        };
        localStorage.setItem('cashoutai_user', JSON.stringify(sessionData));
        if (rememberMe) setupSessionRefresh(sessionData);
        setRememberMe(false);
      }
    } catch (authError) {
      if (authAttemptRef.current !== attempt || activeUserRef.current) return;
      const detail = authError.response?.data?.detail;
      const message = typeof detail === 'string' ? detail : detail?.message;
      setError(accountCreated
        ? 'Your account was created, but payment options could not be opened. Sign in with the same username and password to continue; do not create another account.'
        : message || 'Sign-in could not be completed. Please try again.');
      setLoginForm(previous => ({ ...previous, password: '' }));
    } finally {
      if (authAttemptRef.current === attempt) setIsLoggingIn(false);
    }
  };

  const handleApproval = async (userId, approved) => {
    const session = activeUserRef.current;
    if (!session?.is_admin) return;
    if (approved && !window.confirm('Grant complimentary access to this member? This does not record a paid purchase or apply a purchased access term. Use “Review paid purchase” for a Square payment.')) return;
    try {
      await axios.post(`${API}/users/approve`, {
        user_id: userId,
        approved: approved,
        admin_id: session.id,
        role: "member"
      }, { headers: sessionHeaders(session) });
      if (!sameSession(activeUserRef.current, session)) return;
      
      // Reload pending users
      loadPendingUsers();
      loadAllUsers();
      
      alert(approved ? 'Complimentary access granted. No paid purchase was recorded.' : 'User rejected successfully');
    } catch (error) {
      if (sameSession(activeUserRef.current, session)) alert(typeof error.response?.data?.detail === 'string' ? error.response.data.detail : 'Error processing approval');
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
    const session = activeUserRef.current;
    if (!session) return;
    
    try {
      await axios.post(`${API}/trades?user_id=${session.id}`, {
        symbol: tradeForm.symbol,
        action: tradeForm.action,
        quantity: parseInt(tradeForm.quantity),
        price: parseFloat(tradeForm.price),
        notes: tradeForm.notes,
        stop_loss: tradeForm.stop_loss ? parseFloat(tradeForm.stop_loss) : null,
        take_profit: tradeForm.take_profit ? parseFloat(tradeForm.take_profit) : null
      }, { headers: sessionHeaders(session) });
      if (!sameSession(activeUserRef.current, session)) return;
      
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
      if (sameSession(activeUserRef.current, session)) alert('Error submitting trade');
    }
  };

  const closePosition = async (positionId, symbol) => {
    const session = activeUserRef.current;
    if (!session) return;
    if (!window.confirm(`Close position for ${symbol}?`)) return;
    
    try {
      const response = await axios.post(`${API}/positions/${positionId}/close?user_id=${session.id}`, null, { headers: sessionHeaders(session) });
      if (!sameSession(activeUserRef.current, session)) return;
      alert(`Position closed. P&L: $${response.data.realized_pnl}`);
      loadUserData();
    } catch (error) {
      if (!sameSession(activeUserRef.current, session)) return;
      console.error('Error closing position:', error);
      const detail = error.response?.data?.detail;
      alert(typeof detail === 'string' ? detail : detail?.message || 'Error closing position');
    }
  };

  const handlePositionAction = async (positionId, action, quantity = null, price = null) => {
    const session = activeUserRef.current;
    if (!session) return false;
    try {
      const response = await axios.post(`${API}/positions/${positionId}/action?user_id=${session.id}`, {
        action: action,
        quantity: quantity,
        price: price
      }, { headers: sessionHeaders(session) });
      if (!sameSession(activeUserRef.current, session)) return false;
      
      alert(response.data.message);
      loadUserData();
      return true;
    } catch (error) {
      if (!sameSession(activeUserRef.current, session)) return false;
      console.error('Error with position action:', error);
      const detail = error.response?.data?.detail;
      alert(typeof detail === 'string' ? detail : detail?.message || 'Error processing action');
      return false;
    }
  };

  const fetchUserXPData = async () => {
    const session = activeUserRef.current;
    try {
      if (session?.id) {
        const response = await axios.get(`${API}/users/${session.id}/profile`, { headers: sessionHeaders(session) });
        if (!sameSession(activeUserRef.current, session)) return;
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
    const session = activeUserRef.current;
    if (!session) return;
    try {
      const formData = new FormData();
      formData.append('file', file);
      
      const response = await axios.post(`${API}/users/${session.id}/avatar-upload`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data', ...sessionHeaders(session)
        }
      });
      
      if (!sameSession(activeUserRef.current, session)) return;
      setCurrentUser(prev => sameSession(prev, session) ? ({ ...prev, avatar_url: response.data.avatar_url }) : prev);
      
      setAvatarFile(null);
      setAvatarPreview(null);
      
      alert('Profile picture updated successfully!');
    } catch (error) {
      if (sameSession(activeUserRef.current, session)) alert('Error uploading profile picture');
    }
  };

  const updateProfile = async (e) => {
    e.preventDefault();
    const session = activeUserRef.current;
    if (!session) return;
    try {
      const response = await axios.put(`${API}/users/${session.id}/profile`, editProfileForm, { headers: sessionHeaders(session) });
      if (!sameSession(activeUserRef.current, session)) return;
      setCurrentUser(previous => sameSession(previous, session) ? ({ ...previous, ...response.data, active_session_id: previous.active_session_id }) : previous);
      setShowEditProfile(false);
      
      alert('Profile updated successfully!');
    } catch (error) {
      if (sameSession(activeUserRef.current, session)) alert(error.response?.data?.detail || 'Error updating profile');
    }
  };

  const changePassword = async (e) => {
    e.preventDefault();
    const session = activeUserRef.current;
    if (!session) return;
    
    if (passwordForm.new_password !== passwordForm.confirm_password) {
      alert('New passwords do not match');
      return;
    }
    
    try {
      await axios.post(`${API}/users/change-password?user_id=${session.id}`, {
        current_password: passwordForm.current_password,
        new_password: passwordForm.new_password
      }, { headers: sessionHeaders(session) });
      if (!sameSession(activeUserRef.current, session)) return;
      setShowChangePassword(false);
      setPasswordForm({
        current_password: '',
        new_password: '',
        confirm_password: ''
      });
      
      clearLocalSession(session);
      alert('Password changed successfully. Please sign in again.');
    } catch (error) {
      if (sameSession(activeUserRef.current, session)) alert(error.response?.data?.detail || 'Error changing password');
    }
  };

  const requestPasswordReset = async (e) => {
    e.preventDefault();
    if (passwordRecoveryBusy) return;
    setPasswordRecoveryBusy(true);
    try {
      const response = await axios.post(`${API}/users/reset-password-request`, {
        email: resetPasswordForm.email.trim()
      });
      alert(response.data.message || 'If an account with that email exists, you will receive a password recovery link.');
      setShowForgotPassword(false);
      setResetPasswordForm({ email: '' });
    } catch (error) {
      alert(error.response?.data?.detail || 'Unable to request a recovery email. Please try again.');
    } finally {
      setPasswordRecoveryBusy(false);
    }
  };

  const confirmPasswordReset = async (e) => {
    e.preventDefault();
    const sessionAtStart = activeUserRef.current;
    if (passwordRecoveryBusy) return;
    if (resetTokenForm.new_password !== resetTokenForm.confirm_password) {
      alert('New passwords do not match');
      return;
    }
    if (!resetTokenForm.token || resetTokenForm.new_password.length < 8) {
      alert('Use the recovery link from your email and a password of at least 8 characters.');
      return;
    }
    setPasswordRecoveryBusy(true);
    try {
      await axios.post(`${API}/users/reset-password-confirm`, {
        token: resetTokenForm.token,
        new_password: resetTokenForm.new_password
      });
      
      alert('Your existing account is ready. Sign in with your username and new password. Your profile and history remain on the same account.');
      setResetTokenForm({ token: '', new_password: '', confirm_password: '' });
      if (sessionAtStart) clearLocalSession(sessionAtStart);
      if (!activeUserRef.current) setShowLogin(true);
      setIsRegistering(false);
      setShowForgotPassword(false);
    } catch (error) {
      alert(error.response?.data?.detail || 'Error resetting password');
    } finally {
      setPasswordRecoveryBusy(false);
    }
  };

  const renderPasswordRecoveryModal = () => {
    const hasToken = Boolean(resetTokenForm.token);
    if (!showForgotPassword && !hasToken) return null;
    const fieldClass = `w-full px-4 py-3 rounded-lg border focus:outline-none focus:ring-2 focus:ring-blue-500 ${
      isDarkTheme ? 'bg-white/10 border-white/20 text-white' : 'bg-white border-gray-200 text-gray-900'
    }`;
    return (
      <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4 z-50">
        <div role="dialog" aria-modal="true" aria-labelledby="password-recovery-title"
          className={`rounded-2xl p-6 w-full max-w-md border ${isDarkTheme ? 'bg-gray-900 border-white/20 text-white' : 'bg-white border-gray-200 text-gray-900'}`}>
          <h2 id="password-recovery-title" className="text-2xl font-bold mb-3">{hasToken ? 'Set a new password' : 'Recover your existing account'}</h2>
          <p className="text-sm opacity-80 mb-6">{hasToken
            ? 'Use at least 8 characters. This one-use link expires after one hour. Your existing account, profile, and history are preserved.'
            : 'Enter the email you registered with. If it matches an account, we will send a verification link to set a password for that same account. You do not need to register again.'}</p>
          <form onSubmit={hasToken ? confirmPasswordReset : requestPasswordReset} className="space-y-4">
            {hasToken ? (
              <>
                <div>
                  <label htmlFor="recovery-password" className="block mb-2">New password</label>
                  <input id="recovery-password" type="password" autoComplete="new-password" className={fieldClass}
                    value={resetTokenForm.new_password} minLength={8} maxLength={72} required
                    onChange={e => setResetTokenForm({ ...resetTokenForm, new_password: e.target.value })} />
                </div>
                <div>
                  <label htmlFor="recovery-confirm" className="block mb-2">Confirm new password</label>
                  <input id="recovery-confirm" type="password" autoComplete="new-password" className={fieldClass}
                    value={resetTokenForm.confirm_password} minLength={8} maxLength={72} required
                    onChange={e => setResetTokenForm({ ...resetTokenForm, confirm_password: e.target.value })} />
                </div>
              </>
            ) : (
              <div>
                <label htmlFor="recovery-email" className="block mb-2">Email address</label>
                <input id="recovery-email" type="email" autoComplete="email" className={fieldClass}
                  value={resetPasswordForm.email} maxLength={254} required
                  onChange={e => setResetPasswordForm({ email: e.target.value })} />
              </div>
            )}
            <div className="flex gap-3 pt-3">
              <button type="submit" disabled={passwordRecoveryBusy || (hasToken && resetTokenForm.new_password !== resetTokenForm.confirm_password)}
                className="flex-1 bg-blue-600 text-white py-3 rounded-lg font-semibold hover:bg-blue-700 disabled:opacity-50">
                {passwordRecoveryBusy ? 'Please wait…' : hasToken ? 'Save new password' : 'Email recovery link'}
              </button>
              <button type="button" disabled={passwordRecoveryBusy} className="px-4 py-3 rounded-lg border border-gray-500"
                onClick={() => {
                  setShowForgotPassword(false);
                  setResetPasswordForm({ email: '' });
                  setResetTokenForm({ token: '', new_password: '', confirm_password: '' });
                }}>Cancel</button>
            </div>
          </form>
        </div>
      </div>
    );
  };

  // Keep a remembered login only while its original server session is current.
  const setupSessionRefresh = user => {
    if (window.sessionRefreshInterval) clearInterval(window.sessionRefreshInterval);
    const refreshInterval = setInterval(async () => {
      if (!sameSession(activeUserRef.current, user)) { clearInterval(refreshInterval); return; }
      try {
        const response = await axios.get(`${API}/users/${user.id}/session-status`, { headers: sessionHeaders(user) });
        if (!sameSession(activeUserRef.current, user)) return;
        if (!response.data.valid) { clearLocalSession(user); return; }
        const saved = JSON.parse(localStorage.getItem('cashoutai_user'));
        if (sameSession(saved, user)) {
          saved.sessionCreated = new Date().toISOString();
          localStorage.setItem('cashoutai_user', JSON.stringify(saved));
        }
      } catch (error) {
        if (sameSession(activeUserRef.current, user) && error.response?.status === 401) clearLocalSession(user);
      }
    }, 23 * 60 * 60 * 1000);
    window.sessionRefreshInterval = refreshInterval;
  };

  function requireMembershipForSession(session) {
    if (!sameSession(activeUserRef.current, session)) return;
    membershipRequiredRef.current = true;
    stockUserRef.current = null;
    setMembershipPaymentRequired(true);
    const transport = wsRef.current;
    wsRef.current = null;
    closeSessionTransport(transport);
    notificationService.clearSession?.(session);
    setIsConnected(false);
    setConnectionMode('disconnected');
  }

  function clearLocalSession(session) {
    if (!sameSession(activeUserRef.current, session)) return;
    authAttemptRef.current += 1;
    forgetBillingAccess();
    membershipRequiredRef.current = false;
    setMembershipPaymentRequired(false);
    activeUserRef.current = null;
    stockUserRef.current = null;
    if (window.sessionRefreshInterval) {
      clearInterval(window.sessionRefreshInterval);
      window.sessionRefreshInterval = null;
    }
    removeStoredSession(localStorage, session);
    const transport = wsRef.current;
    wsRef.current = null;
    closeSessionTransport(transport);
    notificationService.clearSession?.(session);
    setRememberMe(false);
    setCurrentUser(null);
    setShowLogin(true);
    setMessages([]);
    setNotifications([]);
    setMessageReactions({});
    reactionCache.current = { loaded: new Set(), pending: new Set(), mine: {} };
    setCommunityError(''); setWinComposerOpen(false);
    setNewMessage(''); setImageFile(null); setImagePreview(null); setReplyToMessage(null);
    setUserTrades([]);
    setUserPerformance(null);
    setUserXP({ experience_points: 0, level: 1 });
    setViewingUserId(null);
    setOpenPositions([]);
    setFavorites([]);
    setPendingUsers([]);
    setAllUsers([]);
    setBillingReviewSelection({ userId: '', version: 0 });
    setCommunityMembers([]);
    setMemberDirectoryError('');
    setOnlineUsers([]);
    setShowEditProfile(false);
    setShowProfileCustomization(false);
    setShowChangePassword(false);
    setEventRequest(previous => ({ ...previous, open: false, email: '', message: '', error: '' }));
    setPasswordForm({ current_password: '', new_password: '', confirm_password: '' });
    setIsConnected(false);
    setConnectionMode('disconnected');
  }

  function returnToMemberSignIn() {
    if (activeUserRef.current) { logout(); return; }
    const username = billingProofRef.current?.username || loginForm.username;
    authAttemptRef.current += 1;
    forgetBillingAccess();
    setIsLoggingIn(false);
    setIsRegistering(false);
    setShowLogin(true);
    setError(null);
    setLoginForm(previous => ({ ...previous, username, password: '' }));
  }

  const logout = async () => {
    const session = activeUserRef.current;
    if (!session?.id || !session?.active_session_id) return;
    // Clear locally before the request. A later login must not be affected by
    // this request's completion, or by the old connection's close callbacks.
    clearLocalSession(session);
    try {
      await axios.post(`${API}/users/logout?user_id=${encodeURIComponent(session.id)}`, null, { headers: sessionHeaders(session) });
    } catch (error) {
      console.error('Could not notify the server of logout');
    }
  };

  function openEventRequest(email = '', message = '', requestError = '') {
    setEventRequest(previous => ({ open: true, email, message, error: requestError, version: previous.version + 1 }));
  }
  function renderPracticeEventDialog() {
    return eventRequest.open ? <PracticeEventRequestDialog key={eventRequest.version} apiBase={API} event={practiceEvent}
      email={eventRequest.email} message={eventRequest.message} error={eventRequest.error}
      onClose={() => setEventRequest(previous => ({ ...previous, open: false }))}
      onRecover={() => { setEventRequest(previous => ({ ...previous, open: false })); setShowForgotPassword(true); }} /> : null;
  }
  function finishEventVerification(username) {
    setEventToken('');
    setShowLoadingScreen(false);
    // logout clears the local session synchronously; its delayed server response
    // must not be followed by a form write that could replace a newer attempt.
    if (activeUserRef.current) logout();
    else returnToMemberSignIn();
    if (username) setLoginForm(previous => ({ ...previous, username, password: '' }));
  }

  if (eventToken) return <><PracticeEventVerification apiBase={API} token={eventToken} onSignIn={finishEventVerification}
    onRequest={() => openEventRequest()} />{renderPracticeEventDialog()}{renderPasswordRecoveryModal()}</>;

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

  if ((currentUser && membershipPaymentRequired) || (!currentUser && billingProof)) {
    const credential = currentUser ? memberBillingCredential(currentUser) : billingProof;
    return <div className="billing-portal"><div className="billing-portal-shell">
      <header className="billing-portal-top"><span className="billing-brand">CashOutAI</span><button type="button" className="billing-exit" onClick={returnToMemberSignIn}>{currentUser ? 'Sign out' : 'Back to sign in'}</button></header>
      <div className="billing-portal-intro"><span>ACCOUNT: {currentUser?.username || billingProof?.username || 'YOUR ACCOUNT'}</span><h1>{currentUser ? 'Review your membership access.' : 'Your account is saved. Choose how to continue.'}</h1><p>Choose a one-time purchase, pay on Square, and wait for the CashOutAI team to approve access. You will use this same account for the trading rooms and community. If you have already paid, check your status here.{practiceEvent.phase === 'open' ? ' Eligible accounts can also verify their email for the current free practice event below.' : ''}</p></div>
      <BillingPanel apiBase={API} credential={credential} initialPlanId={billingPlanId}
        practiceEvent={practiceEvent} onRequestEvent={email => openEventRequest(email)}
        onAuthExpired={returnToMemberSignIn}
        onAccessReady={status => {
          if (!status?.entitlement?.active) return;
          if (credential?.kind === 'member' && sameSession(activeUserRef.current, credential.session) && status.user_id === credential.session.id) {
            membershipRequiredRef.current = false;
            setMembershipPaymentRequired(false);
            setActiveTab('profile');
          } else if (credential?.kind === 'billing' && billingProofRef.current?.billing_token === credential.billing_token) {
            returnToMemberSignIn();
          }
        }} />
      {renderPracticeEventDialog()}{renderPasswordRecoveryModal()}
    </div></div>;
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

            {billingPlanId && <div className="billing-plan-intent"><p>Selected: {membershipPlan(billingPlanId)?.label} · {moneyFromCents(membershipPlan(billingPlanId)?.amount_cents)}</p><small>Already a member? Sign in with your existing account to review this option. If your old password does not work, recover that account below.</small></div>}
            {openBillingOnLogin && !billingPlanId && <div className="billing-plan-intent"><p>Sign in to review your membership and payment status.</p><small>Returning from checkout does not confirm payment or activate access. Your account shows the server-verified status.</small></div>}
            <PracticeEventInvitation event={practiceEvent} registering={isRegistering}
              onJoin={() => { setError(null); setIsRegistering(true); setBillingPlanId(''); setLoginForm(previous => ({ ...previous, membership_plan: EVENT_REGISTRATION_PLAN, real_name: '', password: '' })); }}
              onExisting={() => openEventRequest(loginForm.email)} />
            
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
                  {!isEventRegistration && (
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
                  )}
                  
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
                  {isEventRegistration ? (
                    <div className="practice-event-choice-note">
                      <p>{practiceEvent.phase === 'open' ? `Free Event Access through ${eventDeadlineLabel(practiceEvent.config.ends_at)}. No card or automatic charge.` : 'The event is not accepting new access.'}</p>
                      <button type="button" className="practice-event-text" disabled={isLoggingIn} onClick={() => { setError(null); setBillingPlanId(''); setLoginForm(previous => ({ ...previous, membership_plan: '' })); }}>Choose a paid membership instead</button>
                    </div>
                  ) : (
                  <div>
                    <label className={`block mb-2 ${isDarkTheme ? 'text-gray-300' : 'text-gray-700'}`}>
                      Access option *
                    </label>
                    <select
                      className={`w-full px-4 py-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                        isDarkTheme 
                          ? 'bg-white/10 border border-white/20 text-white [&>option]:bg-gray-800 [&>option]:text-white' 
                          : 'bg-white border border-gray-200 text-gray-900 [&>option]:bg-white [&>option]:text-gray-900'
                      }`}
                      value={loginForm.membership_plan}
                      onChange={e => { setLoginForm({ ...loginForm, membership_plan: e.target.value }); setBillingPlanId(membershipPlan(e.target.value)?.id || ''); }}
                      required
                    >
                      <option value="">Select an access option</option>
                      {practiceEvent.phase === 'open' && <option value={EVENT_REGISTRATION_PLAN}>Free Event Access — verify your email</option>}
                      {MEMBERSHIP_PLANS.map(plan => <option value={plan.registrationLabel} key={plan.id}>{plan.label} — {moneyFromCents(plan.amount_cents)} one time</option>)}
                    </select>
                    <p className={`text-xs mt-2 ${isDarkTheme ? 'text-gray-400' : 'text-gray-500'}`}>Pay once on Square after creating your account. Paid access begins after the team approves your purchase. No automatic renewal or rolling trial.</p>
                  </div>
                  )}
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
                  minLength={isRegistering ? 8 : undefined}
                  maxLength={isRegistering ? 72 : undefined}
                  autoComplete={isRegistering ? 'new-password' : 'current-password'}
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
                      Keep me signed in on this device
                      <span className={`block text-xs ${isDarkTheme ? 'text-gray-400' : 'text-gray-500'}`}>
                        Keep me logged in on this device
                      </span>
                    </span>
                  </label>
                </div>
              )}
              
              {isRegistering && (
                <div className={`p-3 rounded-lg border ${
                  isDarkTheme
                    ? 'bg-blue-500/10 border-blue-500/30 text-blue-400'
                    : 'bg-blue-50 border-blue-200 text-blue-600'
                }`}>
                  <p className="text-sm">
                    {isEventRegistration ? 'Create your account, then open the verification link in your email. Your virtual practice starts after email verification. Your profile and progress stay saved when the event ends.' : 'Create your account first, then review your payment options. The team checks your purchase and approves access. This purchase has no automatic renewal.'}
                  </p>
                </div>
              )}
              
              <button
                type="submit"
                disabled={isLoggingIn || (isEventRegistration && practiceEvent.phase !== 'open')}
                className={`w-full py-3 rounded-lg font-semibold transition-all duration-200 ${
                  isLoggingIn || (isEventRegistration && practiceEvent.phase !== 'open') 
                    ? 'bg-gray-400 cursor-not-allowed text-gray-200' 
                    : 'bg-gradient-to-r from-blue-600 to-purple-600 text-white hover:from-blue-700 hover:to-purple-700'
                }`}
              >
                {isLoggingIn ? (
                  <div className="flex items-center justify-center space-x-2">
                    <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                    <span>{isRegistering ? 'Creating account…' : 'Signing in…'}</span>
                  </div>
                ) : (
                  isRegistering ? isEventRegistration ? 'Create account & verify email' : 'Create account & review payment' : 'Sign in'
                )}
              </button>

                <div className="text-center">
                  <p className={`text-sm mb-2 ${isDarkTheme ? 'text-gray-400' : 'text-gray-600'}`}>Used CashOutAI before? Keep your existing account. If your old password no longer works, recover access with your registered email.</p>
                  <button
                    type="button"
                    onClick={() => setShowForgotPassword(true)}
                    className={`text-sm ${isDarkTheme ? 'text-blue-400 hover:text-blue-300' : 'text-blue-600 hover:text-blue-700'} transition-colors`}
                  >
                    Recover existing account
                  </button>
                </div>
              
              <div className="text-center">
                <button
                  type="button"
                  disabled={isLoggingIn}
                  onClick={() => { setError(null); if (!isRegistering) setLoginForm(previous => ({ ...previous, membership_plan: membershipPlan(previous.membership_plan)?.registrationLabel || '', password: '' })); setIsRegistering(!isRegistering); }}
                  className={`${isDarkTheme ? 'text-blue-400 hover:text-blue-300' : 'text-blue-600 hover:text-blue-700'} transition-colors`}
                >
                  {isRegistering ? 'Already have an account? Sign in' : "Don't have an account? Create one"}
                </button>
              </div>
            </form>
          </div>
        </div>
        
        {renderPasswordRecoveryModal()}
        {renderPracticeEventDialog()}

      </div>
    );
  }

  console.log('🏠 Rendering main app interface');
  console.log('📱 Mobile Debug - User:', currentUser ? 'Authenticated' : 'Not authenticated');
  console.log('📱 Mobile Debug - Active Tab:', activeTab);
  console.log('📱 Mobile Debug - Is Mobile:', capacitorManager.isMobile());
  
  const isMobile = capacitorManager.isMobile();
  
  // Use the responsive web navigation on native devices as well, including all five bot rooms.
  // Desktop/Web rendering with complex CSS
  try {
    return (
      <MobileErrorBoundary>
        <div className={`cashout-app-shell ${isDarkTheme ? '' : 'cashout-light'} min-h-screen overflow-auto ${isDarkTheme ? 'bg-gradient-to-br from-gray-900 via-gray-800 to-black' : 'bg-gradient-to-br from-blue-50 via-white to-indigo-50'}`}>{/* Ensure body can scroll */}
      <AppNavigation activeTab={activeTab} onSelect={setActiveTab} lastRoom={lastTradingRoom.current}
        unread={unreadCount(notifications)} currentUser={currentUser} level={userXP.level} isDarkTheme={isDarkTheme}
        onToggleTheme={toggleTheme} onLogout={logout}
        connectionLabel={isConnected ? (connectionMode === 'websocket' ? 'Connected' : 'Polling') : 'Disconnected'} />
      <PracticeEventMemberBanner status={practiceEvent.status} onMembership={() => setActiveTab('profile')} />
      <BotRunBanner notices={botAnnouncements.banners} onOpen={openBotAnnouncement} onDismiss={botAnnouncements.dismiss} />

      {/* Main Content - Fixed height with proper scrolling accounting for header */}
      <div className="cashout-content-width mx-auto flex flex-col min-h-0 pb-6">{/* Allow natural height with bottom padding */}
        {/* Content area that takes remaining height */}
        <div className={`flex-1 ${activeTab.startsWith('bot-') || activeTab === 'stocks' ? 'cashout-bot-content' : 'p-4 pb-20 overflow-hidden'}`}>{/* This constrains the content */}

        {section === 'trading' && <><BotTabs activeTab={activeTab} onSelect={setActiveTab} /><TradingTools activeTab={activeTab} onSelect={setActiveTab} /></>}
        {section === 'community' && <CommunityNavigation activeTab={activeTab} onSelect={setActiveTab} onShareWin={shareWin} />}
        {section === 'community' && memberDirectoryError && <p className="cashout-community-error" role="alert">{memberDirectoryError}</p>}
        {activeTab === 'members' && <MembersDirectory key={`${currentUser.id}:${currentUser.active_session_id}`} members={communityMembers} onlineUsers={onlineUsers} currentUser={currentUser} onViewProfile={id => id === currentUser.id ? setActiveTab('profile') : handleViewProfile(id)} />}

        {activeTab.startsWith('bot-') && <BotTabContainer key={`${currentUser.id}:${currentUser.active_session_id}`} asset={activeTab.slice(4)} currentUser={currentUser} apiBase={API} />}
        {activeTab === 'stocks' && <StocksWorkspace key={`${currentUser.id}:${currentUser.active_session_id}`} currentUser={currentUser} onOpenCommunity={() => setActiveTab('chat')} {...stocks} />}

        {/* Chat Tab */}
        {activeTab === 'chat' && (
          <div className="cashout-community-screen flex flex-col">
            {winComposerOpen && <div className="cashout-community-status" role="status">Share a win or a lesson with a screenshot and your own explanation. Review the draft, then press Send when you're ready.</div>}
            {communityError && <div className="cashout-community-error" role="alert">{communityError}</div>}
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
                  allUsers={communityMembers}
                  currentUser={currentUser}
                  onViewProfile={handleViewProfile}
                  hideMessageInput={true}
                  mobileUserListOpen={mobileUserListOpen}
                  setMobileUserListOpen={setMobileUserListOpen}
                  deleteMessage={deleteMessage}
                  showScrollButton={showScrollButton}
                  scrollToBottom={scrollToBottom}
                  messagesLoading={messagesLoading}
                />
              </div>
              
              {/* Desktop UserList Column - isolated scroll container with fixed height */}
              <div className="hidden md:block flex-shrink-0 overflow-hidden">
                <UserList 
                  onlineUsers={onlineUsers}
                  allUsers={communityMembers}
                  currentUser={currentUser}
                  isDarkTheme={isDarkTheme}
                  showUserList={showUserList}
                  setShowUserList={setShowUserList}
                  onViewProfile={handleViewProfile}
                />
              </div>
            </div>
            
            {/* Message Input Area - Always at bottom */}
            <div className={`cashout-chat-composer flex-shrink-0 border-t ${
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
                    {communityMembers.filter(user => !onlineUsers?.some(onlineUser => onlineUser.id === user.id)).length > 0 && (
                      <>
                        <div className={`px-2 py-1 mt-4 mb-2 text-xs font-semibold uppercase tracking-wide ${
                          isDarkTheme ? 'text-gray-400' : 'text-gray-500'
                        }`}>
                          Offline ({communityMembers.filter(user => !onlineUsers?.some(onlineUser => onlineUser.id === user.id)).length})
                        </div>
                        
                        {communityMembers.filter(user => !onlineUsers?.some(onlineUser => onlineUser.id === user.id)).map((user) => (
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
              key={`${currentUser.id}:${currentUser.active_session_id}`}
              notifications={notifications}
              botNotices={botAnnouncements.notices}
              botNoticesError={botAnnouncements.error}
              onRefreshBotNotices={botAnnouncements.refresh}
              onOpenBotNotice={openBotAnnouncement}
              isDarkTheme={isDarkTheme}
              currentUser={currentUser}
              onMarkAsRead={markNotificationAsRead}
              onDeleteNotification={deleteNotification}
              onMarkAllAsRead={markAllNotificationsAsRead}
              onOpenNotification={openNotification}
              onOpenStocks={() => setActiveTab('stocks')}
            />
          </div>
        )}

        {/* Achievements Tab */}
        {activeTab === 'achievements' && (
          <div className="flex-1 overflow-y-auto max-h-screen">
            <AchievementsTab key={`${currentUser.id}:${currentUser.active_session_id}`}
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
              key={`${currentUser.id}:${currentUser.active_session_id}`}
              currentUser={currentUser}
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
                <p className="text-xs mb-3 opacity-75">Stock practice journal · Enter your own practice fill price. Stop and target levels are saved for your plan; automatic closes are paused until a current execution quote is verified.</p>
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
                        onChange={(e) => setTradeForm({...tradeForm, symbol: e.target.value.toUpperCase(), price: ''})}
                        required
                      />
                      {/* Current Price Display */}
                      {tradeForm.symbol && (
                        <div className={`mt-1 text-sm ${isDarkTheme ? 'text-gray-400' : 'text-gray-600'}`}>
                          {priceLoading ? (
                            '🔄 Loading price...'
                          ) : currentStockPrice ? (
                            <><span className="font-medium">Last observed: ${formatPrice(currentStockPrice)}</span><QuoteObservation quote={currentStockQuote} /></>
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
                        Manual journal price
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
                        placeholder="Planned stop level"
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
                        placeholder="Planned target level"
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
                  key={`${currentUser.id}:${currentUser.active_session_id}`}
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
                      <div className="flex flex-col sm:flex-row gap-2 pb-2">
                        <button type="button" onClick={shareWin} className="px-4 py-2 rounded-full font-semibold text-sm bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">Share a win</button>
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

                <div className="billing-profile-wrap">
                  <BillingPanel key={`${currentUser.id}:${currentUser.active_session_id}`} apiBase={API}
                    credential={memberBillingCredential(currentUser)} initialPlanId={billingPlanId}
                    practiceEvent={practiceEvent} onRequestEvent={email => openEventRequest(email)}
                    compact onAuthExpired={logout} />
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
            <AdminTrafficPanel key={`${currentUser.id}:${currentUser.active_session_id}`} apiBase={API} currentUser={currentUser} isDarkTheme={isDarkTheme} />
            <AdminBillingPanel key={`${currentUser.id}:${currentUser.active_session_id}`} apiBase={API}
              credential={memberBillingCredential(currentUser)} members={[...allUsers, ...pendingUsers]}
              selectedMemberId={billingReviewSelection.userId} selectionVersion={billingReviewSelection.version}
              onApproved={() => { loadPendingUsers(); loadAllUsers(); }} />
            <div className={`backdrop-blur-lg rounded-xl border p-6 ${
              isDarkTheme 
                ? 'bg-white/5 border-white/10' 
                : 'bg-white/80 border-gray-200'
            }`}>
              <h2 className={`text-2xl font-bold mb-6 ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
                ⚙️ Admin Panel
              </h2>
              
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Accounts awaiting review or using temporary access */}
                <div>
                  <h3 className={`text-xl font-semibold mb-4 ${isDarkTheme ? 'text-yellow-400' : 'text-yellow-600'}`}>
                    Member access &amp; reviews ({pendingUsers.length})
                  </h3>
                  <p className={`text-sm leading-relaxed mb-4 ${isDarkTheme ? 'text-gray-300' : 'text-gray-600'}`}>
                    Practice event access starts automatically after email verification. You do not need to approve each free participant. For paid access, check the Square receipt and choose Review paid purchase.
                  </p>
                  <div className="space-y-3 max-h-96 overflow-y-auto">
                    {pendingUsers.map((user) => {
                      const accessLabel = ({ pending: 'Pending account', trial: 'Temporary access', trial_expired: 'Temporary access ended', approved: 'Approved account', rejected: 'Rejected account' })[user.status] || 'Account review';
                      const accessEnd = ['trial', 'trial_expired'].includes(user.status) && user.trial_end_date ? new Date(user.trial_end_date) : null;
                      const accessEndLabel = accessEnd && Number.isFinite(accessEnd.valueOf())
                        ? accessEnd.toLocaleString('en-US', { timeZone: 'America/New_York', month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit' }) + ' Eastern'
                        : '';
                      return (
                      <div key={user.id} className={`p-4 rounded-lg border ${
                        isDarkTheme 
                          ? 'bg-white/5 border-white/10' 
                          : 'bg-white/70 border-gray-200'
                      }`}>
                        <div className="flex flex-wrap justify-between items-start gap-4">
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
                            <p className={`text-xs mt-2 ${isDarkTheme ? 'text-gray-200' : 'text-gray-700'}`}>
                              <span className={`inline-block rounded border px-2 py-1 ${isDarkTheme ? 'border-white/20 bg-white/5' : 'border-gray-300 bg-gray-100'}`}>{accessLabel}</span>
                            </p>
                            {accessEndLabel && <p className={`text-xs mt-2 ${isDarkTheme ? 'text-gray-400' : 'text-gray-500'}`}>
                              Temporary access end: {accessEndLabel}
                            </p>}
                          </div>
                          <div className="flex flex-wrap gap-2">
                            <button
                              onClick={() => {
                                setBillingReviewSelection(previous => ({ userId: user.id, version: previous.version + 1 }));
                                document.getElementById('admin-paid-approval')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
                              }}
                              className="px-3 py-1 bg-green-600 text-white rounded text-sm hover:bg-green-700"
                            >
                              Review paid purchase
                            </button>
                            <button
                              onClick={() => handleApproval(user.id, false)}
                              className="px-3 py-1 bg-red-600 text-white rounded text-sm hover:bg-red-700"
                            >
                              Reject
                            </button>
                            <button type="button" onClick={() => handleApproval(user.id, true)}
                              className={`basis-full text-left text-xs underline underline-offset-4 ${isDarkTheme ? 'text-gray-400 hover:text-white' : 'text-gray-500 hover:text-gray-800'}`}>
                              Grant complimentary access
                            </button>
                          </div>
                        </div>
                      </div>
                    ); })}
                    {pendingUsers.length === 0 && (
                      <p className={`text-center ${isDarkTheme ? 'text-gray-400' : 'text-gray-500'}`}>
                        No pending or temporary-access accounts to review
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
                    minLength="8"
                    maxLength="72"
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
                    minLength="8"
                    maxLength="72"
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

        {renderPasswordRecoveryModal()}

        {renderPracticeEventDialog()}
        </div> {/* End of content area */}
      </div> {/* End of main container */}

      {/* Public Profile Modal */}
      {viewingUserId && (
        <PublicProfile 
          key={`${currentUser.id}:${currentUser.active_session_id}:${viewingUserId}`}
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
