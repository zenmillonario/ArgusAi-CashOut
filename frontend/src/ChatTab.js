import React from 'react';

const ChatTab = ({ 
  messages, 
  filteredMessages, 
  showSearch, 
  searchQuery, 
  setSearchQuery, 
  formatMessageContent, 
  addReaction,
  addToFavorites,
  favorites,
  messagesEndRef,
  sendMessage,
  newMessage,
  setNewMessage,
  isDarkTheme 
}) => {
  const displayMessages = showSearch ? filteredMessages : messages;

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

      {/* Messages */}
      <div className={`flex-1 backdrop-blur-lg rounded-2xl border p-6 mb-4 overflow-y-auto ${
        isDarkTheme 
          ? 'bg-white/5 border-white/10' 
          : 'bg-white/80 border-gray-200'
      }`}>
        <div className="space-y-4">
          {displayMessages.map((message) => (
            <div key={message.id} className="flex space-x-3 group">
              <div className="w-10 h-10 rounded-full overflow-hidden border-2 border-white/20 flex-shrink-0">
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
                <div className={`w-full h-full bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center text-white font-bold ${message.avatar_url ? 'hidden' : 'flex'}`}>
                  {message.username.charAt(0).toUpperCase()}
                </div>
              </div>
              <div className="flex-1">
                <div className="flex items-center space-x-2 mb-1">
                  <span className={`font-semibold ${
                    message.is_admin 
                      ? 'text-yellow-400' 
                      : isDarkTheme ? 'text-white' : 'text-gray-900'
                  }`}>
                    {message.username}
                  </span>
                  {message.is_admin && (
                    <span className="px-2 py-1 bg-yellow-500/20 text-yellow-400 text-xs rounded-full">
                      Admin
                    </span>
                  )}
                  <span className="text-xs text-gray-400">
                    {new Date(message.timestamp).toLocaleTimeString()}
                  </span>
                  
                  {/* Stock ticker favorites */}
                  {message.highlighted_tickers.map(ticker => (
                    <button
                      key={ticker}
                      onClick={() => addToFavorites(ticker)}
                      className={`text-xs px-2 py-1 rounded transition-colors ${
                        favorites.includes(ticker.toUpperCase())
                          ? 'bg-yellow-500/20 text-yellow-400'
                          : 'bg-blue-500/20 text-blue-400 hover:bg-blue-500/30'
                      }`}
                      title={`${favorites.includes(ticker.toUpperCase()) ? 'Remove from' : 'Add to'} favorites`}
                    >
                      {favorites.includes(ticker.toUpperCase()) ? '★' : '☆'} ${ticker}
                    </button>
                  ))}
                </div>
                <div 
                  className={`${
                    message.is_admin 
                      ? `font-bold ${isDarkTheme ? 'text-white' : 'text-gray-900'}` 
                      : isDarkTheme ? 'text-gray-300' : 'text-gray-700'
                  }`}
                  dangerouslySetInnerHTML={{
                    __html: formatMessageContent(message.content, message.highlighted_tickers)
                  }}
                />
                
                {/* Message Reactions */}
                <div className="flex items-center space-x-2 mt-2 opacity-0 group-hover:opacity-100 transition-opacity">
                  {['👍', '💰', '🚀', '❤️'].map(reaction => (
                    <button
                      key={reaction}
                      onClick={() => addReaction(message.id, reaction)}
                      className="text-lg hover:scale-125 transition-transform"
                      title={`React with ${reaction}`}
                    >
                      {reaction}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Message Input */}
      <form onSubmit={sendMessage} className="flex space-x-4">
        <input
          type="text"
          value={newMessage}
          onChange={(e) => setNewMessage(e.target.value)}
          placeholder="Type a message... (Use $TSLA for stock tickers)"
          className={`flex-1 px-4 py-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${
            isDarkTheme 
              ? 'bg-white/10 border border-white/20 text-white placeholder-gray-400' 
              : 'bg-white border border-gray-200 text-gray-900 placeholder-gray-500'
          }`}
        />
        <button
          type="submit"
          disabled={!newMessage.trim()}
          className="px-6 py-3 bg-gradient-to-r from-blue-600 to-purple-600 text-white rounded-lg font-semibold hover:from-blue-700 hover:to-purple-700 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Send
        </button>
      </form>
    </div>
  );
};

export default ChatTab;
