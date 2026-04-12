import React, { useState, useEffect, useRef } from 'react';
import ChatTab from './ChatTab';
import PortfolioTab from './PortfolioTab';
import FavoritesTab from './FavoritesTab';
import './App.css';

// Demo data for showcase
const DEMO_MESSAGES = [
  {
    id: '1',
    username: 'Admin_Mike',
    content: '🚨 Alert: $TSLA breaking resistance! Watch for breakout above $280',
    is_admin: true,
    timestamp: new Date(Date.now() - 300000),
    highlighted_tickers: ['TSLA'],
    avatar_url: null
  },
  {
    id: '2',
    username: 'TraderTom',
    content: 'Just entered $AAPL at $185. Stop loss at $180 🎯',
    is_admin: false,
    timestamp: new Date(Date.now() - 240000),
    highlighted_tickers: ['AAPL'],
    avatar_url: null
  },
  {
    id: '3',
    username: 'StockSarah',
    content: 'Love the $NVDA setup! Added to my portfolio 🚀',
    is_admin: false,
    timestamp: new Date(Date.now() - 180000),
    highlighted_tickers: ['NVDA'],
    avatar_url: null
  },
  {
    id: '4',
    username: 'Admin_Mike',
    content: '💰 $MSFT earnings beat! Great call team!',
    is_admin: true,
    timestamp: new Date(Date.now() - 120000),
    highlighted_tickers: ['MSFT'],
    avatar_url: null
  }
];

const DEMO_POSITIONS = [
  {
    id: '1',
    symbol: 'TSLA',
    quantity: 100,
    avg_price: 250.00,
    current_price: 275.50,
    unrealized_pnl: 2550.00,
    stop_loss: 240.00,
    take_profit: 300.00,
    opened_at: new Date(Date.now() - 86400000)
  },
  {
    id: '2',
    symbol: 'AAPL',
    quantity: 50,
    avg_price: 185.00,
    current_price: 188.20,
    unrealized_pnl: 160.00,
    stop_loss: 180.00,
    take_profit: 200.00,
    opened_at: new Date(Date.now() - 43200000)
  }
];

const DEMO_TRADES = [
  {
    id: '1',
    symbol: 'TSLA',
    action: 'BUY',
    quantity: 100,
    price: 250.00,
    timestamp: new Date(Date.now() - 86400000),
    notes: 'Breakout setup',
    is_closed: false
  },
  {
    id: '2',
    symbol: 'AAPL',
    action: 'BUY',
    quantity: 50,
    price: 185.00,
    timestamp: new Date(Date.now() - 43200000),
    notes: 'Support bounce',
    is_closed: false
  }
];

const DEMO_PERFORMANCE = {
  total_profit: 2450.75,
  win_percentage: 73.5,
  trades_count: 28,
  average_gain: 87.50
};

function App() {
  const [currentUser, setCurrentUser] = useState(null);
  const [messages, setMessages] = useState(DEMO_MESSAGES);
  const [newMessage, setNewMessage] = useState('');
  const [isConnected, setIsConnected] = useState(true); // Demo always connected
  const [showLogin, setShowLogin] = useState(true);
  const [loginForm, setLoginForm] = useState({ username: '', email: '', password: '' });
  const [isRegistering, setIsRegistering] = useState(false);
  const [pendingUsers, setPendingUsers] = useState([]);
  const [activeTab, setActiveTab] = useState('chat');
  const [userTrades, setUserTrades] = useState(DEMO_TRADES);
  const [userPerformance, setUserPerformance] = useState(DEMO_PERFORMANCE);
  const [openPositions, setOpenPositions] = useState(DEMO_POSITIONS);
  const [favorites, setFavorites] = useState(['TSLA', 'AAPL', 'NVDA', 'MSFT']);
  const [isDarkTheme, setIsDarkTheme] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [showSearch, setShowSearch] = useState(false);
  const [filteredMessages, setFilteredMessages] = useState(DEMO_MESSAGES);
  const [showEditProfile, setShowEditProfile] = useState(false);
  const [showChangePassword, setShowChangePassword] = useState(false);
  const [editProfileForm, setEditProfileForm] = useState({
    username: '',
    email: '',
    avatar_url: ''
  });
  const [passwordForm, setPasswordForm] = useState({
    current_password: '',
    new_password: '',
    confirm_password: ''
  });
  const [tradeForm, setTradeForm] = useState({
    symbol: '',
    action: 'BUY',
    quantity: '',
    price: '',
    notes: '',
    stop_loss: '',
    take_profit: ''
  });
  const messagesEndRef = useRef(null);

  // Filter messages based on search query
  useEffect(() => {
    if (searchQuery.trim() === '') {
      setFilteredMessages(messages);
    } else {
      const filtered = messages.filter(message =>
        message.content.toLowerCase().includes(searchQuery.toLowerCase()) ||
        message.username.toLowerCase().includes(searchQuery.toLowerCase()) ||
        message.highlighted_tickers.some(ticker => 
          ticker.toLowerCase().includes(searchQuery.toLowerCase())
        )
      );
      setFilteredMessages(filtered);
    }
  }, [messages, searchQuery]);

  // Load theme preference
  useEffect(() => {
    const savedTheme = localStorage.getItem('cashoutai_theme');
    if (savedTheme) {
      setIsDarkTheme(savedTheme === 'dark');
    }
  }, []);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [filteredMessages]);

  const toggleTheme = () => {
    const newTheme = !isDarkTheme;
    setIsDarkTheme(newTheme);
    localStorage.setItem('cashoutai_theme', newTheme ? 'dark' : 'light');
  };

  const addToFavorites = (symbol) => {
    if (!favorites.includes(symbol.toUpperCase())) {
      const newFavorites = [...favorites, symbol.toUpperCase()];
      setFavorites(newFavorites);
    }
  };

  const removeFromFavorites = (symbol) => {
    const newFavorites = favorites.filter(fav => fav !== symbol.toUpperCase());
    setFavorites(newFavorites);
  };

  const addReaction = (messageId, reaction) => {
    alert(`Added reaction ${reaction} to message! (Demo feature)`);
  };

  const handleLogin = async (e) => {
    e.preventDefault();
    
    if (isRegistering) {
      alert('Registration successful! This is a demo - you can now login with any credentials.');
      setIsRegistering(false);
      return;
    }

    // Demo login - accept any credentials
    const demoUser = {
      id: 'demo-user-1',
      username: loginForm.username || 'DemoTrader',
      email: loginForm.email || 'demo@cashoutai.com',
      is_admin: loginForm.username.toLowerCase().includes('admin'),
      avatar_url: null,
      created_at: new Date()
    };

    setCurrentUser(demoUser);
    setShowLogin(false);
  };

  const sendMessage = (e) => {
    e.preventDefault();
    if (!newMessage.trim()) return;

    // Extract stock tickers
    const tickers = extractStockTickers(newMessage);
    
    const newMsg = {
      id: Date.now().toString(),
      username: currentUser.username,
      content: newMessage,
      is_admin: currentUser.is_admin,
      timestamp: new Date(),
      highlighted_tickers: tickers,
      avatar_url: currentUser.avatar_url
    };

    setMessages(prev => [...prev, newMsg]);
    setNewMessage('');
  };

  const extractStockTickers = (content) => {
    const pattern = /\$([A-Z]{1,5})/g;
    const matches = [];
    let match;
    while ((match = pattern.exec(content.toUpperCase())) !== null) {
      matches.push(match[1]);
    }
    return matches;
  };

  const formatMessageContent = (content, tickers) => {
    if (!tickers || tickers.length === 0) return content;
    
    let formattedContent = content;
    tickers.forEach(ticker => {
      const regex = new RegExp(`\\$${ticker}`, 'gi');
      formattedContent = formattedContent.replace(regex, `<span class="stock-ticker">$${ticker}</span>`);
    });
    
    return formattedContent;
  };

  const submitTrade = (e) => {
    e.preventDefault();
    if (!tradeForm.symbol || !tradeForm.quantity || !tradeForm.price) return;

    const newTrade = {
      id: Date.now().toString(),
      symbol: tradeForm.symbol.toUpperCase(),
      action: tradeForm.action,
      quantity: parseInt(tradeForm.quantity),
      price: parseFloat(tradeForm.price),
      timestamp: new Date(),
      notes: tradeForm.notes,
      stop_loss: tradeForm.stop_loss ? parseFloat(tradeForm.stop_loss) : null,
      take_profit: tradeForm.take_profit ? parseFloat(tradeForm.take_profit) : null,
      is_closed: false
    };

    setUserTrades(prev => [newTrade, ...prev]);
    
    // Add to positions if BUY
    if (tradeForm.action === 'BUY') {
      const newPosition = {
        id: Date.now().toString(),
        symbol: tradeForm.symbol.toUpperCase(),
        quantity: parseInt(tradeForm.quantity),
        avg_price: parseFloat(tradeForm.price),
        current_price: parseFloat(tradeForm.price) * (1 + (Math.random() - 0.5) * 0.1), // Random price movement
        unrealized_pnl: 0,
        stop_loss: tradeForm.stop_loss ? parseFloat(tradeForm.stop_loss) : null,
        take_profit: tradeForm.take_profit ? parseFloat(tradeForm.take_profit) : null,
        opened_at: new Date()
      };
      
      setOpenPositions(prev => [newPosition, ...prev]);
    }

    setTradeForm({
      symbol: '',
      action: 'BUY',
      quantity: '',
      price: '',
      notes: '',
      stop_loss: '',
      take_profit: ''
    });

    const tradeValue = (parseInt(tradeForm.quantity) * parseFloat(tradeForm.price)).toFixed(2);
    alert(`✅ Trade recorded successfully!\n${tradeForm.action} ${tradeForm.quantity} ${tradeForm.symbol.toUpperCase()} at $${tradeForm.price}\nTotal value: $${tradeValue}`);
  };

  const closePosition = (positionId, symbol) => {
    if (!window.confirm(`Close ${symbol} position at current market price?`)) return;
    
    setOpenPositions(prev => prev.filter(pos => pos.id !== positionId));
    alert(`Position ${symbol} closed successfully! (Demo)`);
  };

  const updateProfile = (e) => {
    e.preventDefault();
    setCurrentUser({...currentUser, ...editProfileForm});
    setShowEditProfile(false);
    alert('Profile updated successfully!');
  };

  const changePassword = (e) => {
    e.preventDefault();
    if (passwordForm.new_password !== passwordForm.confirm_password) {
      alert('New passwords do not match');
      return;
    }
    setPasswordForm({ current_password: '', new_password: '', confirm_password: '' });
    setShowChangePassword(false);
    alert('Password changed successfully!');
  };

  const openEditProfile = () => {
    setEditProfileForm({
      username: currentUser.username,
      email: currentUser.email,
      avatar_url: currentUser.avatar_url || ''
    });
    setShowEditProfile(true);
  };

  const logout = () => {
    setCurrentUser(null);
    setShowLogin(true);
    setActiveTab('chat');
  };

  if (showLogin) {
    return (
      <div className={`min-h-screen ${isDarkTheme ? 'bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900' : 'bg-gradient-to-br from-blue-50 via-purple-50 to-blue-50'}`}>
        <div className="min-h-screen flex items-center justify-center p-4">
          <div className="bg-white/10 backdrop-blur-lg rounded-2xl p-8 w-full max-w-md border border-white/20">
            <div className="text-center mb-8">
              <div className="flex items-center justify-center mb-4">
                <img 
                  src="https://i.imgur.com/ZPYCiyg.png" 
                  alt="CashOutAi Peacock Logo" 
                  className="w-20 h-20 rounded-xl border-2 border-blue-400/50 mr-4 bg-white/10 p-1"
                  onError={(e) => {
                    e.target.style.display = 'none';
                    e.target.nextSibling.style.display = 'flex';
                  }}
                />
                <div className="w-20 h-20 rounded-xl bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center text-white font-bold text-3xl border-2 border-blue-400/50 mr-4 hidden">
                  🦚
                </div>
                <div>
                  <h1 className="text-4xl font-bold text-white mb-2">CashOutAi</h1>
                </div>
              </div>
              <p className="text-gray-300">Trade Together, Win Together</p>
              <p className="text-sm text-yellow-400 mt-2">Demo Trading Platform</p>
            </div>
            
            <form onSubmit={handleLogin} className="space-y-4">
              <div>
                <input
                  type="text"
                  placeholder="Username (try 'admin' for admin access)"
                  className="w-full px-4 py-3 bg-white/10 border border-white/20 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  value={loginForm.username}
                  onChange={(e) => setLoginForm({...loginForm, username: e.target.value})}
                />
              </div>
              
              {isRegistering && (
                <div>
                  <input
                    type="email"
                    placeholder="Email"
                    className="w-full px-4 py-3 bg-white/10 border border-white/20 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                    value={loginForm.email}
                    onChange={(e) => setLoginForm({...loginForm, email: e.target.value})}
                  />
                </div>
              )}
              
              <div>
                <input
                  type="password"
                  placeholder="Password (any password works in demo)"
                  className="w-full px-4 py-3 bg-white/10 border border-white/20 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  value={loginForm.password}
                  onChange={(e) => setLoginForm({...loginForm, password: e.target.value})}
                />
              </div>
              
              <button
                type="submit"
                className="w-full bg-gradient-to-r from-blue-600 to-purple-600 text-white py-3 rounded-lg font-semibold hover:from-blue-700 hover:to-purple-700 transition-all duration-200"
              >
                {isRegistering ? 'Register' : 'Login to Demo'}
              </button>
            </form>
            
            <div className="text-center mt-4">
              <button
                onClick={() => setIsRegistering(!isRegistering)}
                className="text-blue-400 hover:text-blue-300 transition-colors"
              >
                {isRegistering ? 'Already have an account? Login' : "Don't have an account? Register"}
              </button>
            </div>
            
            <div className="mt-4 p-3 bg-blue-500/20 border border-blue-500/30 rounded-lg">
              <p className="text-blue-300 text-sm text-center">
                🎯 This is a demo version showcasing CashOutAi features
              </p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={`min-h-screen ${isDarkTheme ? 'bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900' : 'bg-gradient-to-br from-blue-50 via-purple-50 to-blue-50'}`}>
      {/* Header */}
      <div className={`backdrop-blur-lg border-b p-4 ${isDarkTheme ? 'bg-black/20 border-white/10' : 'bg-white/20 border-gray-200'}`}>
        <div className="flex items-center justify-between max-w-6xl mx-auto">
          <div className="flex items-center space-x-4">
            <div className="flex items-center space-x-3">
              <img 
                src="https://i.imgur.com/ZPYCiyg.png" 
                alt="CashOutAi Peacock Logo" 
                className="w-10 h-10 rounded-lg border border-blue-400/50 bg-white/10 p-0.5"
                onError={(e) => {
                  e.target.style.display = 'none';
                  e.target.nextSibling.style.display = 'flex';
                }}
              />
              <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center text-white font-bold text-lg border border-blue-400/50 hidden">
                🦚
              </div>
              <h1 className={`text-2xl font-bold ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>CashOutAi</h1>
            </div>
            <div className="flex items-center space-x-2">
              <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`}></div>
              <span className={`text-sm ${isDarkTheme ? 'text-gray-300' : 'text-gray-600'}`}>
                {isConnected ? 'Connected' : 'Disconnected'}
              </span>
            </div>
          </div>
          
          <div className="flex items-center space-x-4">
            {/* Tab Navigation */}
            <div className="flex space-x-2">
              <button
                onClick={() => setActiveTab('chat')}
                className={`px-4 py-2 rounded-lg transition-colors ${
                  activeTab === 'chat' ? 'bg-blue-600 text-white' : `${isDarkTheme ? 'bg-white/10 text-gray-300 hover:bg-white/20' : 'bg-gray-200 text-gray-700 hover:bg-gray-300'}`
                }`}
              >
                Chat
              </button>
              <button
                onClick={() => setActiveTab('practice')}
                className={`px-4 py-2 rounded-lg transition-colors ${
                  activeTab === 'practice' ? 'bg-blue-600 text-white' : `${isDarkTheme ? 'bg-white/10 text-gray-300 hover:bg-white/20' : 'bg-gray-200 text-gray-700 hover:bg-gray-300'}`
                }`}
              >
                Practice
              </button>
              <button
                onClick={() => setActiveTab('portfolio')}
                className={`px-4 py-2 rounded-lg transition-colors ${
                  activeTab === 'portfolio' ? 'bg-blue-600 text-white' : `${isDarkTheme ? 'bg-white/10 text-gray-300 hover:bg-white/20' : 'bg-gray-200 text-gray-700 hover:bg-gray-300'}`
                }`}
              >
                Portfolio
              </button>
              <button
                onClick={() => setActiveTab('favorites')}
                className={`px-4 py-2 rounded-lg transition-colors ${
                  activeTab === 'favorites' ? 'bg-blue-600 text-white' : `${isDarkTheme ? 'bg-white/10 text-gray-300 hover:bg-white/20' : 'bg-gray-200 text-gray-700 hover:bg-gray-300'}`
                }`}
              >
                Favorites
              </button>
              <button
                onClick={() => setActiveTab('profile')}
                className={`px-4 py-2 rounded-lg transition-colors ${
                  activeTab === 'profile' ? 'bg-blue-600 text-white' : `${isDarkTheme ? 'bg-white/10 text-gray-300 hover:bg-white/20' : 'bg-gray-200 text-gray-700 hover:bg-gray-300'}`
                }`}
              >
                Profile
              </button>
            </div>
            
            {/* Action Buttons */}
            <div className="flex items-center space-x-2">
              {activeTab === 'chat' && (
                <button
                  onClick={() => setShowSearch(!showSearch)}
                  className={`p-2 rounded-lg transition-colors ${isDarkTheme ? 'bg-white/10 text-gray-300 hover:bg-white/20' : 'bg-gray-200 text-gray-600 hover:bg-gray-300'}`}
                  title="Search messages"
                >
                  🔍
                </button>
              )}
              
              <button
                onClick={toggleTheme}
                className={`p-2 rounded-lg transition-colors ${isDarkTheme ? 'bg-white/10 text-gray-300 hover:bg-white/20' : 'bg-gray-200 text-gray-600 hover:bg-gray-300'}`}
                title="Toggle theme"
              >
                {isDarkTheme ? '☀️' : '🌙'}
              </button>
            </div>
            
            <div className="text-right">
              <div className={`font-semibold ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>{currentUser?.username}</div>
              <div className={`text-xs ${isDarkTheme ? 'text-gray-400' : 'text-gray-600'}`}>
                {currentUser?.is_admin ? 'Admin' : 'Member'} (Demo)
              </div>
            </div>
            <button
              onClick={logout}
              className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
            >
              Logout
            </button>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-6xl mx-auto p-4 h-[calc(100vh-80px)]">
        
        {/* Chat Tab */}
        {activeTab === 'chat' && (
          <ChatTab 
            messages={messages}
            filteredMessages={filteredMessages}
            showSearch={showSearch}
            searchQuery={searchQuery}
            setSearchQuery={setSearchQuery}
            formatMessageContent={formatMessageContent}
            addReaction={addReaction}
            addToFavorites={addToFavorites}
            favorites={favorites}
            messagesEndRef={messagesEndRef}
            sendMessage={sendMessage}
            newMessage={newMessage}
            setNewMessage={setNewMessage}
            isDarkTheme={isDarkTheme}
          />
        )}

        {/* Portfolio Tab */}
        {activeTab === 'portfolio' && (
          <PortfolioTab 
            openPositions={openPositions}
            userPerformance={userPerformance}
            closePosition={closePosition}
            isDarkTheme={isDarkTheme}
          />
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

        {/* Practice Tab with Enhanced Trading */}
        {activeTab === 'practice' && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Enhanced Trade Form */}
              <div className={`backdrop-blur-lg rounded-2xl border p-6 ${
                isDarkTheme 
                  ? 'bg-white/5 border-white/10' 
                  : 'bg-white/80 border-gray-200'
              }`}>
                <h2 className={`text-2xl font-bold mb-6 ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
                  📈 Paper Trading Demo
                </h2>
                <form onSubmit={submitTrade} className="space-y-4">
                  <div>
                    <label className={`block mb-2 ${isDarkTheme ? 'text-gray-300' : 'text-gray-700'}`}>
                      Stock Symbol
                    </label>
                    <input
                      type="text"
                      placeholder="TSLA"
                      className={`w-full px-4 py-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                        isDarkTheme 
                          ? 'bg-white/10 border border-white/20 text-white placeholder-gray-400' 
                          : 'bg-white border border-gray-200 text-gray-900 placeholder-gray-500'
                      }`}
                      value={tradeForm.symbol}
                      onChange={(e) => setTradeForm({...tradeForm, symbol: e.target.value.toUpperCase()})}
                      required
                    />
                  </div>
                  
                  <div>
                    <label className={`block mb-2 ${isDarkTheme ? 'text-gray-300' : 'text-gray-700'}`}>
                      Action
                    </label>
                    <select
                      className={`w-full px-4 py-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${
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
                  
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className={`block mb-2 ${isDarkTheme ? 'text-gray-300' : 'text-gray-700'}`}>
                        Quantity
                      </label>
                      <input
                        type="number"
                        placeholder="100"
                        className={`w-full px-4 py-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${
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
                      <label className={`block mb-2 ${isDarkTheme ? 'text-gray-300' : 'text-gray-700'}`}>
                        Price
                      </label>
                      <input
                        type="number"
                        step="0.01"
                        placeholder="250.00"
                        className={`w-full px-4 py-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${
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
                  
                  {/* Stop Loss & Take Profit */}
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className={`block mb-2 ${isDarkTheme ? 'text-gray-300' : 'text-gray-700'}`}>
                        Stop Loss (Optional)
                      </label>
                      <input
                        type="number"
                        step="0.01"
                        placeholder="Auto-sell if price drops"
                        className={`w-full px-4 py-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-red-500 ${
                          isDarkTheme 
                            ? 'bg-white/10 border border-white/20 text-white placeholder-gray-400' 
                            : 'bg-white border border-gray-200 text-gray-900 placeholder-gray-500'
                        }`}
                        value={tradeForm.stop_loss}
                        onChange={(e) => setTradeForm({...tradeForm, stop_loss: e.target.value})}
                      />
                    </div>
                    
                    <div>
                      <label className={`block mb-2 ${isDarkTheme ? 'text-gray-300' : 'text-gray-700'}`}>
                        Take Profit (Optional)
                      </label>
                      <input
                        type="number"
                        step="0.01"
                        placeholder="Auto-sell when profit reached"
                        className={`w-full px-4 py-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500 ${
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
                    <label className={`block mb-2 ${isDarkTheme ? 'text-gray-300' : 'text-gray-700'}`}>
                      Notes (Optional)
                    </label>
                    <textarea
                      placeholder="Trade notes and strategy..."
                      className={`w-full px-4 py-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                        isDarkTheme 
                          ? 'bg-white/10 border border-white/20 text-white placeholder-gray-400' 
                          : 'bg-white border border-gray-200 text-gray-900 placeholder-gray-500'
                      }`}
                      value={tradeForm.notes}
                      onChange={(e) => setTradeForm({...tradeForm, notes: e.target.value})}
                      rows="3"
                    />
                  </div>
                  
                  <button
                    type="submit"
                    className="w-full bg-gradient-to-r from-green-600 to-blue-600 text-white py-3 rounded-lg font-semibold hover:from-green-700 hover:to-blue-700 transition-all duration-200"
                  >
                    🎯 Record Demo Trade
                  </button>
                </form>
              </div>

              {/* Recent Trades */}
              <div className={`backdrop-blur-lg rounded-2xl border p-6 ${
                isDarkTheme 
                  ? 'bg-white/5 border-white/10' 
                  : 'bg-white/80 border-gray-200'
              }`}>
                <h2 className={`text-2xl font-bold mb-6 ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
                  📋 Recent Trades
                </h2>
                <div className="space-y-3 max-h-96 overflow-y-auto">
                  {userTrades.map((trade) => (
                    <div key={trade.id} className={`p-4 rounded-lg ${
                      isDarkTheme ? 'bg-white/5' : 'bg-gray-50'
                    }`}>
                      <div className="flex justify-between items-center">
                        <div className="flex items-center space-x-3">
                          <span className={`px-2 py-1 rounded text-xs font-semibold ${
                            trade.action === 'BUY' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
                          }`}>
                            {trade.action}
                          </span>
                          <span className={`font-semibold ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
                            {trade.symbol}
                          </span>
                          <span className={isDarkTheme ? 'text-gray-300' : 'text-gray-600'}>
                            {trade.quantity} shares
                          </span>
                          {trade.is_closed && (
                            <span className="px-2 py-1 bg-blue-500/20 text-blue-400 text-xs rounded">
                              CLOSED
                            </span>
                          )}
                        </div>
                        <div className="text-right">
                          <div className={`font-semibold ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
                            ${trade.price}
                          </div>
                          <div className="text-xs text-gray-400">
                            {new Date(trade.timestamp).toLocaleDateString()}
                          </div>
                        </div>
                      </div>
                      {trade.notes && (
                        <div className={`mt-2 text-sm ${isDarkTheme ? 'text-gray-400' : 'text-gray-600'}`}>
                          {trade.notes}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Profile Tab */}
        {activeTab === 'profile' && (
          <div className="space-y-6">
            {/* Profile Header */}
            <div className={`backdrop-blur-lg rounded-2xl border p-6 ${
              isDarkTheme 
                ? 'bg-white/5 border-white/10' 
                : 'bg-white/80 border-gray-200'
            }`}>
              <div className="flex items-center space-x-6">
                {/* Profile Picture */}
                <div className="relative">
                  <div className="w-24 h-24 rounded-full overflow-hidden border-4 border-white/20">
                    {currentUser?.avatar_url ? (
                      <img 
                        src={currentUser.avatar_url} 
                        alt="Profile" 
                        className="w-full h-full object-cover"
                      />
                    ) : (
                      <div className="w-full h-full bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center text-white font-bold text-2xl">
                        {currentUser?.username?.charAt(0).toUpperCase()}
                      </div>
                    )}
                  </div>
                  <button
                    onClick={openEditProfile}
                    className="absolute -bottom-2 -right-2 w-8 h-8 bg-blue-600 rounded-full flex items-center justify-center text-white text-sm hover:bg-blue-700 transition-colors"
                  >
                    ✏️
                  </button>
                </div>
                
                {/* Profile Info */}
                <div className="flex-1">
                  <h2 className={`text-2xl font-bold ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
                    {currentUser?.username}
                  </h2>
                  <p className={isDarkTheme ? 'text-gray-300' : 'text-gray-600'}>
                    {currentUser?.email}
                  </p>
                  <div className="flex items-center space-x-2 mt-2">
                    {currentUser?.is_admin && (
                      <span className="px-2 py-1 bg-yellow-500/20 text-yellow-400 text-xs rounded-full">
                        Admin
                      </span>
                    )}
                    <span className="text-green-400 text-sm">
                      Demo User
                    </span>
                  </div>
                </div>
                
                <div className="flex space-x-3">
                  <button
                    onClick={openEditProfile}
                    className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                  >
                    Edit Profile
                  </button>
                  <button
                    onClick={() => setShowChangePassword(true)}
                    className="px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
                  >
                    Change Password
                  </button>
                </div>
              </div>
            </div>

            {/* Performance Stats */}
            {userPerformance && (
              <div className={`backdrop-blur-lg rounded-2xl border p-6 ${
                isDarkTheme 
                  ? 'bg-white/5 border-white/10' 
                  : 'bg-white/80 border-gray-200'
              }`}>
                <h3 className={`text-xl font-bold mb-6 ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
                  Trading Performance (Demo)
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                  <div className={`p-6 rounded-xl text-center ${
                    isDarkTheme ? 'bg-white/5' : 'bg-gray-50'
                  }`}>
                    <div className="text-3xl font-bold text-green-400">
                      ${userPerformance.total_profit.toFixed(2)}
                    </div>
                    <div className={`mt-2 ${isDarkTheme ? 'text-gray-300' : 'text-gray-600'}`}>
                      Total Profit
                    </div>
                  </div>
                  
                  <div className={`p-6 rounded-xl text-center ${
                    isDarkTheme ? 'bg-white/5' : 'bg-gray-50'
                  }`}>
                    <div className="text-3xl font-bold text-blue-400">
                      {userPerformance.win_percentage.toFixed(1)}%
                    </div>
                    <div className={`mt-2 ${isDarkTheme ? 'text-gray-300' : 'text-gray-600'}`}>
                      Win Rate
                    </div>
                  </div>
                  
                  <div className={`p-6 rounded-xl text-center ${
                    isDarkTheme ? 'bg-white/5' : 'bg-gray-50'
                  }`}>
                    <div className="text-3xl font-bold text-purple-400">
                      {userPerformance.trades_count}
                    </div>
                    <div className={`mt-2 ${isDarkTheme ? 'text-gray-300' : 'text-gray-600'}`}>
                      Total Trades
                    </div>
                  </div>
                  
                  <div className={`p-6 rounded-xl text-center ${
                    isDarkTheme ? 'bg-white/5' : 'bg-gray-50'
                  }`}>
                    <div className="text-3xl font-bold text-yellow-400">
                      ${userPerformance.average_gain.toFixed(2)}
                    </div>
                    <div className={`mt-2 ${isDarkTheme ? 'text-gray-300' : 'text-gray-600'}`}>
                      Avg Gain
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Edit Profile Modal */}
      {showEditProfile && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-white/10 backdrop-blur-lg rounded-2xl p-6 w-full max-w-md border border-white/20">
            <h2 className="text-2xl font-bold text-white mb-6">Edit Profile (Demo)</h2>
            
            <form onSubmit={updateProfile} className="space-y-4">
              <div>
                <label className="block text-gray-300 mb-2">Username</label>
                <input
                  type="text"
                  className="w-full px-4 py-3 bg-white/10 border border-white/20 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  value={editProfileForm.username}
                  onChange={(e) => setEditProfileForm({...editProfileForm, username: e.target.value})}
                  required
                />
              </div>
              
              <div>
                <label className="block text-gray-300 mb-2">Email</label>
                <input
                  type="email"
                  className="w-full px-4 py-3 bg-white/10 border border-white/20 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  value={editProfileForm.email}
                  onChange={(e) => setEditProfileForm({...editProfileForm, email: e.target.value})}
                  required
                />
              </div>
              
              <div>
                <label className="block text-gray-300 mb-2">Avatar URL</label>
                <input
                  type="url"
                  placeholder="https://example.com/your-avatar.jpg"
                  className="w-full px-4 py-3 bg-white/10 border border-white/20 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  value={editProfileForm.avatar_url}
                  onChange={(e) => setEditProfileForm({...editProfileForm, avatar_url: e.target.value})}
                />
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
                  onClick={() => setShowEditProfile(false)}
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
          <div className="bg-white/10 backdrop-blur-lg rounded-2xl p-6 w-full max-w-md border border-white/20">
            <h2 className="text-2xl font-bold text-white mb-6">Change Password (Demo)</h2>
            
            <form onSubmit={changePassword} className="space-y-4">
              <div>
                <label className="block text-gray-300 mb-2">Current Password</label>
                <input
                  type="password"
                  className="w-full px-4 py-3 bg-white/10 border border-white/20 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  value={passwordForm.current_password}
                  onChange={(e) => setPasswordForm({...passwordForm, current_password: e.target.value})}
                  required
                />
              </div>
              
              <div>
                <label className="block text-gray-300 mb-2">New Password</label>
                <input
                  type="password"
                  className="w-full px-4 py-3 bg-white/10 border border-white/20 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  value={passwordForm.new_password}
                  onChange={(e) => setPasswordForm({...passwordForm, new_password: e.target.value})}
                  required
                />
              </div>
              
              <div>
                <label className="block text-gray-300 mb-2">Confirm New Password</label>
                <input
                  type="password"
                  className="w-full px-4 py-3 bg-white/10 border border-white/20 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  value={passwordForm.confirm_password}
                  onChange={(e) => setPasswordForm({...passwordForm, confirm_password: e.target.value})}
                  required
                />
              </div>
              
              <div className="flex space-x-4 pt-4">
                <button
                  type="submit"
                  className="flex-1 bg-gradient-to-r from-green-600 to-blue-600 text-white py-3 rounded-lg font-semibold hover:from-green-700 hover:to-blue-700 transition-all duration-200"
                >
                  Change Password
                </button>
                <button
                  type="button"
                  onClick={() => setShowChangePassword(false)}
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

export default App;