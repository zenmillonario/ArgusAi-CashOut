import React from 'react';

const ChatInput = ({ 
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
    <div className="space-y-2">
      {/* Reply To Message UI */}
      {replyToMessage && (
        <div className={`p-3 rounded-lg border ${
          isDarkTheme 
            ? 'bg-blue-500/10 border-blue-500/30' 
            : 'bg-blue-50 border-blue-200'
        }`}>
          <div className="flex items-center justify-between mb-2">
            <div className={`text-sm font-medium ${
              isDarkTheme ? 'text-blue-300' : 'text-blue-700'
            }`}>
              Replying to {replyToMessage.username}
            </div>
            <button
              onClick={() => setReplyToMessage(null)}
              className={`text-sm px-2 py-1 rounded ${
                isDarkTheme ? 'hover:bg-blue-500/20' : 'hover:bg-blue-100'
              }`}
            >
              ✕
            </button>
          </div>
          <div className={`text-sm p-2 rounded border-l-2 ${
            isDarkTheme 
              ? 'bg-gray-700 border-blue-400 text-gray-300' 
              : 'bg-gray-50 border-blue-400 text-gray-700'
          }`}>
            {replyToMessage.content.substring(0, 100)}
            {replyToMessage.content.length > 100 && '...'}
          </div>
        </div>
      )}

      {/* Image Preview */}
      {imagePreview && (
        <div className={`p-3 rounded-lg border ${
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
      <form onSubmit={sendMessage} className="space-y-2">
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

export default ChatInput;