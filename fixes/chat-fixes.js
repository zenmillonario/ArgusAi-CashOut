// Chat Fixes - Compact Messages, Image Upload, No Bot Messages
// Replace your ChatTab.js with these improvements

import React, { useState } from 'react';

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
  isDarkTheme,
  currentUser
}) => {
  const displayMessages = showSearch ? filteredMessages : messages;
  const [selectedImage, setSelectedImage] = useState(null);
  const [showImageModal, setShowImageModal] = useState(false);

  const handleImageUpload = async (file) => {
    if (!file) return;
    
    if (file.size > 5 * 1024 * 1024) {
      alert('Image too large. Please choose a file under 5MB.');
      return;
    }
    
    if (!file.type.startsWith('image/')) {
      alert('Please select an image file.');
      return;
    }
    
    try {
      const formData = new FormData();
      formData.append('file', file);
      
      const response = await axios.post(`${API}/users/upload-message-image?user_id=${currentUser.id}`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      });
      
      // Send image message
      sendMessage(null, response.data.image_url, 'image');
    } catch (error) {
      alert('Error uploading image: ' + (error.response?.data?.detail || error.message));
    }
  };

  const handlePaste = (e) => {
    const items = e.clipboardData.items;
    for (let item of items) {
      if (item.type.startsWith('image/')) {
        const file = item.getAsFile();
        handleImageUpload(file);
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
            <div className={`mt-2 text-sm ${isDarkTheme ? 'text-gray-400' : 'text-gray-600'}`}>
              Found {filteredMessages.length} message(s)
            </div>
          )}
        </div>
      )}

      {/* COMPACT Messages */}
      <div className={`flex-1 backdrop-blur-lg rounded-2xl border p-4 mb-4 overflow-y-auto ${
        isDarkTheme 
          ? 'bg-white/5 border-white/10' 
          : 'bg-white/80 border-gray-200'
      }`}>
        <div className="space-y-2"> {/* Reduced spacing from space-y-4 to space-y-2 */}
          {displayMessages
            .filter(message => !message.is_bot) // REMOVE BOT MESSAGES
            .map((message) => (
            <div key={message.id} className="message-compact flex space-x-3 group hover:bg-white/5 p-2 rounded">
              {/* SMALLER Avatar - 32px instead of 40px */}
              <div className="avatar-compact w-8 h-8 rounded-full overflow-hidden border border-white/20 flex-shrink-0">
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
                <div className={`w-full h-full bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center text-white font-bold text-sm ${message.avatar_url ? 'hidden' : 'flex'}`}>
                  {message.real_name?.charAt(0).toUpperCase() || message.username.charAt(0).toUpperCase()}
                </div>
              </div>
              
              <div className="flex-1 min-w-0">
                <div className="flex items-center space-x-2 mb-1">
                  {/* SMALLER Username and Timestamp */}
                  <span className={`message-username-small font-semibold text-sm ${
                    message.is_admin 
                      ? 'text-yellow-400' 
                      : isDarkTheme ? 'text-white' : 'text-gray-900'
                  }`}>
                    {message.username}
                  </span>
                  
                  {/* Admin Badge */}
                  {message.is_admin && (
                    <span className="px-2 py-0.5 bg-yellow-500/20 text-yellow-400 text-xs rounded-full font-semibold">
                      👑
                    </span>
                  )}
                  
                  {/* Moderator Badge */}
                  {message.is_moderator && (
                    <span className="px-2 py-0.5 bg-purple-500/20 text-purple-400 text-xs rounded-full font-semibold">
                      🛡️
                    </span>
                  )}
                  
                  {/* SMALLER Timestamp */}
                  <span className="message-timestamp-small text-xs opacity-60">
                    {new Date(message.timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}
                  </span>
                  
                  {/* Stock ticker favorites */}
                  {message.highlighted_tickers?.map(ticker => (
                    <button
                      key={ticker}
                      onClick={() => addToFavorites(ticker)}
                      className={`text-xs px-2 py-0.5 rounded transition-colors ${
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
                
                {/* Message Content */}
                {message.message_type === 'image' ? (
                  <div className="mt-2">
                    <img 
                      src={message.image_url} 
                      alt="Shared image" 
                      className="message-image max-w-xs max-h-48 rounded-lg border border-white/20 cursor-pointer"
                      onClick={() => {
                        setSelectedImage(message.image_url);
                        setShowImageModal(true);
                      }}
                    />
                    {message.image_url?.includes('.gif') && (
                      <span className="gif-indicator">GIF</span>
                    )}
                  </div>
                ) : (
                  <div 
                    className={`message-content-compact text-sm ${
                      message.is_admin 
                        ? `font-semibold ${isDarkTheme ? 'text-white' : 'text-gray-900'}` 
                        : isDarkTheme ? 'text-gray-300' : 'text-gray-700'
                    }`}
                    dangerouslySetInnerHTML={{
                      __html: formatMessageContent(message.content, message.highlighted_tickers)
                    }}
                  />
                )}
                
                {/* COMPACT Message Reactions */}
                <div className="flex items-center space-x-1 mt-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  {['👍', '💰', '🚀', '❤️'].map(reaction => (
                    <button
                      key={reaction}
                      onClick={() => addReaction(message.id, reaction)}
                      className="text-sm hover:scale-125 transition-transform p-1"
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

      {/* Enhanced Message Input with Image Upload */}
      <div className="space-y-3">
        {/* Image Upload Area */}
        <div className="flex items-center space-x-2">
          <label className="px-3 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors cursor-pointer text-sm font-semibold">
            📷 Image
            <input
              type="file"
              accept="image/*"
              onChange={(e) => e.target.files[0] && handleImageUpload(e.target.files[0])}
              className="hidden"
            />
          </label>
          <span className={`text-xs ${isDarkTheme ? 'text-gray-400' : 'text-gray-600'}`}>
            or paste image from clipboard
          </span>
        </div>
        
        {/* Message Input */}
        <form onSubmit={sendMessage} className="flex space-x-3">
          <input
            type="text"
            value={newMessage}
            onChange={(e) => setNewMessage(e.target.value)}
            onPaste={handlePaste}
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

      {/* Image Modal */}
      {showImageModal && (
        <div 
          className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4 z-50"
          onClick={() => setShowImageModal(false)}
        >
          <div className="max-w-4xl max-h-full">
            <img 
              src={selectedImage} 
              alt="Full size" 
              className="max-w-full max-h-full rounded-lg"
            />
          </div>
        </div>
      )}
    </div>
  );
};

export default ChatTab;