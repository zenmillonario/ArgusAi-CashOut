import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';
const API = BACKEND_URL ? `${BACKEND_URL}/api` : '/api';

// Lazy-loading image component for chat images
const ChatImage = ({ messageId, content, alt }) => {
  const [src, setSrc] = useState(() => {
    // If content is already a full data URL (from WebSocket real-time), use it directly
    if (content && (content.startsWith('data:') || content.startsWith('http'))) {
      return content;
    }
    return null;
  });
  const [loading, setLoading] = useState(() => {
    return !(content && (content.startsWith('data:') || content.startsWith('http')));
  });
  const [error, setError] = useState(false);

  useEffect(() => {
    // Already have the image data
    if (content && (content.startsWith('data:') || content.startsWith('http'))) {
      setSrc(content);
      setLoading(false);
      return;
    }
    
    // Need to fetch from API (placeholder content like __IMAGE__id__)
    if (messageId) {
      setLoading(true);
      axios.get(`${API}/messages/${messageId}/image`)
        .then(res => {
          if (res.data && res.data.image_url) {
            setSrc(res.data.image_url);
          } else {
            setError(true);
          }
        })
        .catch(() => setError(true))
        .finally(() => setLoading(false));
    }
  }, [content, messageId]);

  if (loading) {
    return (
      <div className="w-48 h-24 rounded-lg bg-white/5 border border-white/10 flex items-center justify-center animate-pulse">
        <span className="text-gray-400 text-xs">Loading image...</span>
      </div>
    );
  }
  
  if (error || !src) {
    return (
      <div className="w-48 h-24 rounded-lg bg-white/5 border border-white/10 flex items-center justify-center">
        <span className="text-gray-400 text-xs">Image unavailable</span>
      </div>
    );
  }

  return (
    <img 
      src={src} 
      alt={alt || "Shared image"} 
      className="max-w-xs rounded-lg border border-white/20"
      style={{ maxHeight: '200px' }}
      loading="lazy"
      onError={() => setError(true)}
    />
  );
};

const ChatTab = ({ 
  messages, 
  filteredMessages, 
  showSearch, 
  searchQuery, 
  setSearchQuery, 
  formatMessageContent, 
  addReaction,
  messageReactions,
  addToFavorites,
  favorites,
  messagesEndRef,
  sendMessage,
  newMessage,
  setNewMessage,
  imageFile,
  setImageFile,
  imagePreview,
  setImagePreview,
  isDarkTheme,
  replyToMessage,
  setReplyToMessage,
  // User list props for mobile integration
  onlineUsers,
  allUsers,
  currentUser,
  onViewProfile,
  hideMessageInput = false,
  mobileUserListOpen,
  setMobileUserListOpen,
  showScrollButton,
  scrollToBottom,
  deleteMessage,
  messagesLoading = false
}) => {
  const displayMessages = showSearch ? (filteredMessages || []) : (messages || []);
  const [followingUsers, setFollowingUsers] = useState([]);
  const [followerCounts, setFollowerCounts] = useState({});
  const [hasScrolledOnLoad, setHasScrolledOnLoad] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(true);

  const loadOlderMessages = useCallback(async () => {
    if (loadingMore || !hasMore || !messages || messages.length === 0) return;
    setLoadingMore(true);
    try {
      const oldestTimestamp = messages[0]?.timestamp;
      const url = currentUser 
        ? `${API}/messages?user_id=${currentUser.id}&limit=50&before=${oldestTimestamp}`
        : `${API}/messages?limit=50&before=${oldestTimestamp}`;
      const response = await axios.get(url);
      if (response.data && response.data.length > 0) {
        // Prepend older messages (they come newest-first, so reverse)
        const chatContainer = document.querySelector('[data-chat-messages]');
        const prevHeight = chatContainer?.scrollHeight || 0;
        
        // Use the parent's setMessages if available, otherwise merge locally
        if (window.__setMessages) {
          window.__setMessages(prev => {
            const existingIds = new Set(prev.map(m => m.id));
            const newMsgs = response.data.filter(m => !existingIds.has(m.id));
            return [...newMsgs, ...prev];
          });
        }
        
        // Maintain scroll position after prepending
        requestAnimationFrame(() => {
          if (chatContainer) {
            chatContainer.scrollTop = chatContainer.scrollHeight - prevHeight;
          }
        });
        
        if (response.data.length < 50) setHasMore(false);
      } else {
        setHasMore(false);
      }
    } catch (e) {
      console.error('Error loading older messages:', e);
    }
    setLoadingMore(false);
  }, [loadingMore, hasMore, messages, currentUser]);

  // Auto-scroll to bottom when messages first load
  useEffect(() => {
    if (displayMessages.length > 0 && !hasScrolledOnLoad) {
      const scrollAttempt = () => {
        const chatContainer = document.querySelector('[data-chat-messages]');
        if (chatContainer) {
          chatContainer.scrollTop = chatContainer.scrollHeight;
          setHasScrolledOnLoad(true);
        }
      };
      const t1 = setTimeout(scrollAttempt, 200);
      const t2 = setTimeout(scrollAttempt, 1000);
      return () => { clearTimeout(t1); clearTimeout(t2); };
    }
  }, [displayMessages.length, hasScrolledOnLoad]);

  // Helper: parse timestamp as UTC (backend stores UTC without 'Z' suffix)
  const parseUTC = (ts) => {
    if (!ts) return new Date();
    const str = String(ts);
    return new Date(str.endsWith('Z') ? str : str + 'Z');
  };

  // Function to group messages by date and add daily separators
  const getMessagesWithDateSeparators = (msgs) => {
    if (!msgs || msgs.length === 0) return [];
    
    const result = [];
    let currentDateStr = null;
    
    // Messages come sorted oldest-first from backend
    msgs.forEach((message) => {
      const messageDate = parseUTC(message.timestamp);
      const dateKey = messageDate.toLocaleDateString('en-US', { timeZone: 'America/New_York' });
      
      if (currentDateStr !== dateKey) {
        currentDateStr = dateKey;
        
        const today = new Date().toLocaleDateString('en-US', { timeZone: 'America/New_York' });
        const yesterday = new Date(Date.now() - 86400000).toLocaleDateString('en-US', { timeZone: 'America/New_York' });
        
        let label;
        if (dateKey === today) {
          label = 'Today';
        } else if (dateKey === yesterday) {
          label = 'Yesterday';
        } else {
          label = messageDate.toLocaleDateString('en-US', {
            weekday: 'long',
            year: 'numeric', 
            month: 'long',
            day: 'numeric',
            timeZone: 'America/New_York'
          });
        }
        
        result.push({
          id: `date-sep-${dateKey}`,
          type: 'date-separator',
          date: label,
        });
      }
      
      result.push(message);
    });
    
    return result;
  };

  // API setup
  const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';
  const API = BACKEND_URL ? `${BACKEND_URL}/api` : '/api';

  // Fetch user data (similar to UserList component)
  React.useEffect(() => {
    const fetchFollowingList = async () => {
      if (!currentUser) return;
      
      try {
        const response = await axios.get(`${API}/users/${currentUser.id}/profile`);
        setFollowingUsers(response.data.following || []);
      } catch (error) {
        console.error('Error fetching following list:', error);
      }
    };

    fetchFollowingList();
  }, [currentUser, API]);

  React.useEffect(() => {
    const fetchFollowerCounts = async () => {
      if (!allUsers || allUsers.length === 0) return;
      
      const counts = {};
      
      for (const user of allUsers) {
        try {
          const response = await axios.get(`${API}/users/${user.id}/profile`);
          counts[user.id] = response.data.follower_count || 0;
        } catch (error) {
          console.error(`Error fetching follower count for user ${user.id}:`, error);
          counts[user.id] = 0;
        }
      }
      
      setFollowerCounts(counts);
    };

    fetchFollowerCounts();
  }, [allUsers, API]);

  const getUserStatus = (user) => {
    return onlineUsers?.some(onlineUser => onlineUser.id === user.id) || false;
  };

  const sortedUsers = onlineUsers ? [...onlineUsers].sort((a, b) => {
    if (a.is_admin !== b.is_admin) return b.is_admin ? 1 : -1;
    return (a.screen_name || a.username).localeCompare(b.screen_name || b.username);
  }) : [];

  const handleImageSelect = (e) => {
    const file = e.target.files[0];
    if (file) {
      setImageFile(file);
      
      // Create preview
      const reader = new FileReader();
      reader.onload = (e) => {
        setImagePreview(e.target.result);
      };
      reader.readAsDataURL(file);
    }
  };

  const removeImage = () => {
    setImageFile(null);
    setImagePreview(null);
  };

  // Handle paste events for images
  const handlePaste = (e) => {
    const items = e.clipboardData.items;
    
    for (let i = 0; i < items.length; i++) {
      const item = items[i];
      
      if (item.type.indexOf('image') !== -1) {
        e.preventDefault();
        const blob = item.getAsFile();
        
        if (blob) {
          setImageFile(blob);
          
          // Create preview
          const reader = new FileReader();
          reader.onload = (e) => {
            setImagePreview(e.target.result);
          };
          reader.readAsDataURL(blob);
        }
        break;
      }
    }
  };

  return (
    <div className="h-full flex flex-col">
      {/* Search Bar */}
      {showSearch && (
        <div className="mb-4">
          <input
            type="text"
            placeholder="Search messages, users, or stock tickers..."
            className={`w-full px-4 py-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${
              isDarkTheme 
                ? 'bg-white/10 border border-white/20 text-white placeholder-gray-400' 
                : 'bg-white border border-gray-200 text-gray-900 placeholder-gray-500'
            }`}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
          {searchQuery && (
            <div className="mt-2 text-sm text-gray-400">
              Found {filteredMessages.length} message(s)
            </div>
          )}
        </div>
      )}

      {/* Messages - STREAMLINED SAME LINE FORMAT - Isolated scroll container */}
      <div className={`backdrop-blur-lg rounded-2xl border p-4 flex-1 flex flex-col ${
        isDarkTheme 
          ? 'bg-white/5 border-white/10' 
          : 'bg-white/80 border-gray-200'
      } overflow-hidden min-h-0`}>
        {/* Timezone Indicator */}
        <div className={`text-xs text-center pb-2 mb-2 border-b ${
          isDarkTheme 
            ? 'text-gray-400 border-white/10' 
            : 'text-gray-500 border-gray-200'
        }`}>
          🕐 Times shown in Eastern Time Zone (ET)
        </div>
        
        {/* Messages container */}
        <div className="flex-1 overflow-y-auto min-h-0 flex flex-col" data-chat-messages="true">
          <div className="space-y-1 mt-auto">
          {/* Load More button at top of messages */}
          {hasMore && displayMessages.length > 0 && !showSearch && (
            <div className="text-center py-2">
              <button
                onClick={loadOlderMessages}
                disabled={loadingMore}
                className={`text-sm px-4 py-1.5 rounded-full ${
                  isDarkTheme ? 'bg-white/10 hover:bg-white/20 text-gray-300' : 'bg-gray-100 hover:bg-gray-200 text-gray-600'
                } transition-colors`}
                data-testid="load-more-messages"
              >
                {loadingMore ? 'Loading...' : 'Load older messages'}
              </button>
            </div>
          )}
          {/* CRITICAL UX FIX: Loading State */}
          {messagesLoading && displayMessages.length === 0 && (
            <div className="space-y-4 py-4 animate-pulse">
              {[1,2,3,4,5,6].map(i => (
                <div key={i} className="flex items-start space-x-2">
                  <div className={`w-6 h-6 rounded-full flex-shrink-0 ${isDarkTheme ? 'bg-white/10' : 'bg-gray-200'}`} />
                  <div className="flex-1 space-y-1">
                    <div className={`h-3 rounded w-24 ${isDarkTheme ? 'bg-white/10' : 'bg-gray-200'}`} />
                    <div className={`h-3 rounded w-3/4 ${isDarkTheme ? 'bg-white/5' : 'bg-gray-100'}`} />
                  </div>
                </div>
              ))}
              <div className={`text-center text-sm ${isDarkTheme ? 'text-gray-500' : 'text-gray-400'}`}>
                Loading messages...
              </div>
            </div>
          )}
          {/* Empty State - only show when NOT loading */}
          {!messagesLoading && displayMessages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full text-center py-8">
              <div className={`text-6xl mb-4 ${isDarkTheme ? 'text-gray-600' : 'text-gray-400'}`}>
                💬
              </div>
              <h3 className={`text-xl font-semibold mb-2 ${
                isDarkTheme ? 'text-gray-300' : 'text-gray-600'
              }`}>
                Welcome to ArgusAI CashOut!
              </h3>
              <p className={`text-sm ${isDarkTheme ? 'text-gray-400' : 'text-gray-500'}`}>
                Start the conversation! Share your trading insights and connect with the community.
              </p>
            </div>
          )}
          {/* PERFORMANCE OPTIMIZATION: Use React.memo and limit initial render */}
          {getMessagesWithDateSeparators(displayMessages).map((message, index) => (
            <div key={message.id} className="group">
              {/* Date Separator */}
              {message.type === 'date-separator' ? (
                <div className={`flex items-center my-3 ${isDarkTheme ? 'text-gray-500' : 'text-gray-400'}`}>
                  <div className={`flex-1 border-t ${isDarkTheme ? 'border-gray-700' : 'border-gray-300'}`} />
                  <span className={`px-3 text-xs font-medium ${isDarkTheme ? 'bg-gray-900/50' : 'bg-gray-100'} rounded-full py-1`}>
                    {message.date}
                  </span>
                  <div className={`flex-1 border-t ${isDarkTheme ? 'border-gray-700' : 'border-gray-300'}`} />
                </div>
              ) : (
              <>
              {/* STREAMLINED FORMAT: Username: Message on same line */}
              {message.content_type === 'image' ? (
                // Image messages get their own layout
                <div className="flex items-start space-x-2 py-1">
                  <div className="w-6 h-6 rounded-full overflow-hidden border border-white/20 flex-shrink-0">
                    {message.avatar_url ? (
                      <img 
                        src={message.avatar_url} 
                        alt={message.username} 
                        className="w-full h-full object-cover"
                        onError={(e) => {
                          e.target.style.display = 'none';
                          e.target.nextSibling.style.display = 'flex';
                        }}
                      />
                    ) : null}
                    <div className={`w-full h-full bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center text-white font-bold text-xs ${message.avatar_url ? 'hidden' : 'flex'}`}>
                      {(message.screen_name || message.username).charAt(0).toUpperCase()}
                    </div>
                  </div>
                  
                  <div className="flex-1">
                    <div className="flex items-center space-x-2 mb-1">
                      <span className={`font-medium text-sm ${
                        message.is_admin 
                          ? 'text-yellow-400' 
                          : isDarkTheme ? 'text-white' : 'text-gray-900'
                      }`}>
                        {message.screen_name || message.username}
                      </span>
                      {message.is_admin && (
                        <span className="px-1.5 py-0.5 bg-yellow-500/20 text-yellow-400 text-xs rounded">Admin</span>
                      )}
                      <span className="text-xs text-gray-400">
                        {parseUTC(message.timestamp).toLocaleTimeString([], {
                        hour: '2-digit', 
                        minute:'2-digit',
                        timeZone: 'America/New_York'
                      })}
                      </span>
                    </div>
                    <ChatImage 
                      messageId={message.id}
                      content={message.content}
                      alt="Shared image"
                    />
                    {/* Show text caption if present with image */}
                    {message.text_content && (
                      <div className={`mt-1 text-sm ${isDarkTheme ? 'text-gray-300' : 'text-gray-700'}`}>
                        {message.text_content}
                      </div>
                    )}
                  </div>
                </div>
              ) : (
                // Text messages - STREAMLINED SAME LINE FORMAT
                <div className="flex items-start space-x-1 py-0.5">
                  {/* Compact timestamp */}
                  <span className="text-xs text-gray-500 w-12 flex-shrink-0 text-right">
                    {parseUTC(message.timestamp).toLocaleTimeString([], {
                      hour: '2-digit', 
                      minute:'2-digit',
                      timeZone: 'America/New_York'
                    })}
                  </span>
                  
                  {/* Username: Message format with reply indicator */}
                  <div className="flex-1 min-w-0">
                    {/* Show if this is a reply */}
                    {message.reply_to && (
                      <div className={`text-xs mb-1 pl-3 border-l-2 ${
                        isDarkTheme ? 'border-blue-400 text-gray-400' : 'border-blue-500 text-gray-500'
                      }`}>
                        ↩️ Replying to {message.reply_to.username}: {message.reply_to.content.substring(0, 50)}...
                      </div>
                    )}
                    
                    <span className={`font-medium text-sm ${
                      message.is_admin 
                        ? 'text-yellow-400' 
                        : isDarkTheme ? 'text-blue-300' : 'text-blue-600'
                    }`}>
                      {message.screen_name || message.username}
                      {message.is_admin && <span className="text-yellow-400 text-xs ml-1">[Admin]</span>}:
                    </span>
                    <span 
                      className={`text-sm ml-2 ${
                        message.is_admin 
                          ? `font-medium ${isDarkTheme ? 'text-white' : 'text-gray-900'}` 
                          : isDarkTheme ? 'text-gray-300' : 'text-gray-700'
                      }`}
                      dangerouslySetInnerHTML={{
                        __html: formatMessageContent(message.content, message.highlighted_tickers)
                      }}
                    />
                    
                    {/* Stock tickers and reactions - inline */}
                    <span className="ml-2">
                      {message.highlighted_tickers.map(ticker => (
                        <button
                          key={ticker}
                          onClick={() => addToFavorites(ticker)}
                          className={`text-xs px-1 py-0.5 rounded ml-1 transition-colors ${
                            favorites.includes(ticker.toUpperCase())
                              ? 'bg-yellow-500/20 text-yellow-400'
                              : 'bg-blue-500/20 text-blue-400 hover:bg-blue-500/30'
                          }`}
                          title={`${favorites.includes(ticker.toUpperCase()) ? 'Remove from' : 'Add to'} favorites`}
                        >
                          {favorites.includes(ticker.toUpperCase()) ? '★' : '☆'}${ticker}
                        </button>
                      ))}
                      
                      {/* Quick reactions and reply button */}
                      <span className="opacity-0 group-hover:opacity-100 transition-opacity ml-1">
                        {/* Reply button */}
                        <button
                          onClick={() => setReplyToMessage(message)}
                          className="text-sm hover:scale-110 transition-transform px-1 text-blue-400"
                          title="Reply to this message"
                        >
                          ↩️
                        </button>
                        {['👍', '❤️', '💰', '🚀'].map(reaction => (
                          <button
                            key={reaction}
                            onClick={() => addReaction(message.id, reaction)}
                            className="text-sm hover:scale-110 transition-transform px-1"
                            title={`React with ${reaction}`}
                          >
                            {reaction}
                          </button>
                        ))}
                        {currentUser?.is_admin && deleteMessage && (
                          <button
                            onClick={() => { if (window.confirm('Delete this message?')) deleteMessage(message.id); }}
                            className="text-sm hover:scale-110 transition-transform px-1 text-red-400"
                            title="Delete message"
                            data-testid={`delete-msg-${message.id}`}
                          >
                            🗑️
                          </button>
                        )}
                      </span>
                      
                      {/* Show existing reactions */}
                      {messageReactions[message.id] && Object.entries(messageReactions[message.id]).map(([reaction, count]) => (
                        <button
                          key={reaction}
                          onClick={() => addReaction(message.id, reaction)}
                          className={`text-xs px-1 py-0.5 rounded ml-1 transition-colors ${
                            isDarkTheme ? 'bg-white/10 hover:bg-white/20' : 'bg-gray-100 hover:bg-gray-200'
                          }`}
                        >
                          {reaction}{count}
                        </button>
                      ))}
                    </span>
                  </div>
                </div>
              )}
              </>
              )}
            </div>
          ))}
          <div ref={messagesEndRef} />
          </div>
        </div>
        
        {/* Simple scroll to bottom button */}
        {showScrollButton && (
          <button
            onClick={scrollToBottom}
            className={`fixed right-4 bottom-24 z-50 p-3 rounded-full shadow-lg transition-all duration-300 hover:scale-110 ${
              isDarkTheme 
                ? 'bg-blue-600 hover:bg-blue-500 text-white' 
                : 'bg-blue-500 hover:bg-blue-600 text-white'
            }`}
            title="Scroll to bottom"
          >
            <svg 
              className="w-5 h-5" 
              fill="none" 
              stroke="currentColor" 
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 14l-7 7m0 0l-7-7m7 7V3" />
            </svg>
          </button>
        )}
      </div>

      {/* Reply To Message UI */}
      {replyToMessage && (
        <div className={`mb-4 p-3 rounded-lg border ${
          isDarkTheme 
            ? 'bg-blue-500/10 border-blue-500/30' 
            : 'bg-blue-50 border-blue-200'
        }`}>
          <div className="flex items-center justify-between mb-2">
            <span className={`text-sm font-medium ${isDarkTheme ? 'text-blue-400' : 'text-blue-600'}`}>
              ↩️ Replying to {replyToMessage.screen_name || replyToMessage.username}:
            </span>
            <button
              onClick={() => setReplyToMessage(null)}
              className="text-red-400 hover:text-red-300 text-sm"
            >
              ✕ Cancel
            </button>
          </div>
          <div className={`text-sm p-2 rounded border-l-2 ${
            isDarkTheme 
              ? 'bg-white/5 border-blue-400 text-gray-300' 
              : 'bg-white border-blue-500 text-gray-700'
          }`}>
            {/* Show image preview if replying to image */}
            {replyToMessage.content_type === 'image' && replyToMessage.content && (
              <div className="flex items-center space-x-2 mb-2">
                <img 
                  src={replyToMessage.content} 
                  alt="Replied message" 
                  className="w-12 h-12 object-cover rounded"
                />
                <span>📷 Image</span>
              </div>
            )}
            
            {/* Show text content */}
            {replyToMessage.content_type === 'text' && (
              <div>
                {replyToMessage.content.substring(0, 100)}
                {replyToMessage.content.length > 100 && '...'}
              </div>
            )}
            
            {/* Show both image and text if both exist */}
            {replyToMessage.content_type === 'image' && replyToMessage.text_content && (
              <div className="mt-2 text-xs opacity-75">
                "{replyToMessage.text_content.substring(0, 50)}"
                {replyToMessage.text_content.length > 50 && '...'}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Image Preview */}
      {imagePreview && (
        <div className={`mb-4 p-3 rounded-lg border ${
          isDarkTheme 
            ? 'bg-white/5 border-white/10' 
            : 'bg-white/80 border-gray-200'
        }`}>
          <div className="flex items-center justify-between mb-2">
            <span className={`text-sm font-medium ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
              Image to share:
            </span>
            <button
              onClick={removeImage}
              className="text-red-400 hover:text-red-300 text-sm"
            >
              ✕ Remove
            </button>
          </div>
          <img 
            src={imagePreview} 
            alt="Preview" 
            className="max-w-xs max-h-32 rounded border border-white/20"
          />
        </div>
      )}

      {/* Message Input - Fixed at bottom - Only show if not hidden */}
      {!hideMessageInput && currentUser.status === "trial_expired" ? (
        // TRIAL SYSTEM: Show upgrade message for expired trial users
        <div className={`flex-shrink-0 p-4 rounded-lg border ${
          isDarkTheme 
            ? 'bg-red-500/10 border-red-500/30' 
            : 'bg-red-50 border-red-200'
        }`}>
          <div className="text-center">
            <h3 className={`font-semibold text-lg mb-2 ${
              isDarkTheme ? 'text-red-400' : 'text-red-600'
            }`}>
              🚫 Chat Access Restricted
            </h3>
            <p className={`text-sm mb-3 ${
              isDarkTheme ? 'text-gray-300' : 'text-gray-700'
            }`}>
              Your 14-day trial has expired. Upgrade your account to continue chatting with other traders.
            </p>
            <div className={`inline-flex items-center px-4 py-2 rounded-lg ${
              isDarkTheme 
                ? 'bg-yellow-500/20 border border-yellow-500/30 text-yellow-400' 
                : 'bg-yellow-50 border border-yellow-200 text-yellow-600'
            }`}>
              <span className="font-bold mr-2">🎯 Special Offer:</span>
              <span>Use code <strong>ARGUS20</strong> for 20% OFF!</span>
            </div>
          </div>
        </div>
      ) : !hideMessageInput && (
        <div className={`flex-shrink-0 ${mobileUserListOpen ? 'relative z-60' : ''}`}>
          <form onSubmit={sendMessage}>
            <div className="flex space-x-2">
              <input
                type="text"
                value={newMessage}
                onChange={(e) => setNewMessage(e.target.value)}
                onPaste={handlePaste}
                placeholder={replyToMessage 
                  ? `Replying to ${replyToMessage.screen_name || replyToMessage.username}...`
                  : imageFile ? "Add a caption to your image..." : "Type a message..."
                }
                className={`flex-1 px-3 py-2 sm:py-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm sm:text-base ${
                  isDarkTheme 
                    ? 'bg-white/10 border border-white/20 text-white placeholder-gray-400' 
                    : 'bg-white border border-gray-200 text-gray-900 placeholder-gray-500'
                }`}
              />
              
              {/* Image Upload Button */}
              <label className={`px-3 py-2 sm:py-3 rounded-lg cursor-pointer transition-colors ${
                isDarkTheme 
                  ? 'bg-white/10 border border-white/20 text-gray-300 hover:bg-white/20' 
                  : 'bg-gray-100 border border-gray-200 text-gray-600 hover:bg-gray-200'
              }`}>
                📷
                <input
                  type="file"
                  accept="image/*,image/gif"
                  onChange={handleImageSelect}
                  className="hidden"
                />
              </label>
              
              <button
                type="submit"
                disabled={!newMessage.trim() && !imageFile}
                className="px-4 sm:px-6 py-2 sm:py-3 bg-gradient-to-r from-blue-600 to-purple-600 text-white rounded-lg font-semibold hover:from-blue-700 hover:to-purple-700 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed text-sm sm:text-base"
              >
                {imageFile ? (newMessage.trim() ? 'Send Both' : 'Send Image') : 'Send'}
              </button>
            </div>
            
            <div className={`hidden sm:block text-xs ${isDarkTheme ? 'text-gray-400' : 'text-gray-500'} text-center mt-2`}>
              Use $SYMBOL for stock tickers | Upload/paste images | Click reply arrow to reply
            </div>
          </form>
        </div>
      )}
    </div>
  );
};

export default ChatTab;