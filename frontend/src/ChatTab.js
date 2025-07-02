import React from 'react';

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
  setReplyToMessage
}) => {
  const displayMessages = showSearch ? filteredMessages : messages;

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
    <div className="h-full flex flex-col" style={{ maxHeight: 'calc(100vh - 160px)' }}>{/* Better height constraint */}
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

      {/* Messages - STREAMLINED SAME LINE FORMAT - Fixed scrolling */}
      <div className={`flex-1 backdrop-blur-lg rounded-2xl border p-4 mb-4 overflow-y-auto min-h-0 ${
        isDarkTheme 
          ? 'bg-white/5 border-white/10' 
          : 'bg-white/80 border-gray-200'
      }`} style={{ maxHeight: 'calc(100vh - 280px)', minHeight: '400px' }}>{/* Better height constraint */}
        {/* Timezone Indicator */}
        <div className={`text-xs text-center pb-2 mb-2 border-b ${
          isDarkTheme 
            ? 'text-gray-400 border-white/10' 
            : 'text-gray-500 border-gray-200'
        }`}>
          🕐 Times shown in Eastern Time Zone (ET)
        </div>
        
        <div className="space-y-1">
          {displayMessages.map((message) => (
            <div key={message.id} className="group">
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
                        {new Date(message.timestamp).toLocaleTimeString([], {
                        hour: '2-digit', 
                        minute:'2-digit',
                        timeZone: 'America/New_York'
                      })}
                      </span>
                    </div>
                    <img 
                      src={message.content} 
                      alt="Shared image" 
                      className="max-w-xs rounded-lg border border-white/20"
                      style={{ maxHeight: '200px' }}
                    />
                  </div>
                </div>
              ) : (
                // Text messages - STREAMLINED SAME LINE FORMAT
                <div className="flex items-start space-x-1 py-0.5">
                  {/* Compact timestamp */}
                  <span className="text-xs text-gray-500 w-12 flex-shrink-0 text-right">
                    {new Date(message.timestamp).toLocaleTimeString([], {
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
                        {['👍', '💰', '🚀'].map(reaction => (
                          <button
                            key={reaction}
                            onClick={() => addReaction(message.id, reaction)}
                            className="text-sm hover:scale-110 transition-transform px-1"
                            title={`React with ${reaction}`}
                          >
                            {reaction}
                          </button>
                        ))}
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
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>
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
            {replyToMessage.content_type === 'image' ? '📷 Image' : replyToMessage.content.substring(0, 100)}
            {replyToMessage.content.length > 100 && '...'}
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

      {/* Message Input */}
      <form onSubmit={sendMessage} className="space-y-3">
        <div className="flex space-x-2">
          <input
            type="text"
            value={newMessage}
            onChange={(e) => setNewMessage(e.target.value)}
            onPaste={handlePaste}
            placeholder={replyToMessage 
              ? `Replying to ${replyToMessage.screen_name || replyToMessage.username}...`
              : "Type a message... (Use $TSLA for stock tickers, or paste images)"
            }
            className={`flex-1 px-4 py-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${
              isDarkTheme 
                ? 'bg-white/10 border border-white/20 text-white placeholder-gray-400' 
                : 'bg-white border border-gray-200 text-gray-900 placeholder-gray-500'
            }`}
            disabled={!!imageFile}
          />
          
          {/* Image Upload Button */}
          <label className={`px-4 py-3 rounded-lg cursor-pointer transition-colors ${
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
            className="px-6 py-3 bg-gradient-to-r from-blue-600 to-purple-600 text-white rounded-lg font-semibold hover:from-blue-700 hover:to-purple-700 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {imageFile ? 'Send Image' : 'Send'}
          </button>
        </div>
        
        <div className={`text-xs ${isDarkTheme ? 'text-gray-400' : 'text-gray-500'} text-center`}>
          💡 Tip: Use $SYMBOL to highlight stock tickers • Upload/paste images/GIFs to share • Click ↩️ to reply
        </div>
      </form>
    </div>
  );
};

export default ChatTab;