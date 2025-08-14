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
            
            // Show success notification
            const notification = document.createElement('div');
            notification.innerHTML = '✅ Image pasted successfully! Click "Send Image" to share.';
            notification.style.cssText = `
              position: fixed;
              top: 20px;
              right: 20px;
              background: #10b981;
              color: white;
              padding: 12px 20px;
              border-radius: 8px;
              z-index: 1000;
              font-size: 14px;
              box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
              animation: slideIn 0.3s ease-out;
            `;
            
            // Add slide-in animation
            const style = document.createElement('style');
            style.textContent = `
              @keyframes slideIn {
                from { transform: translateX(100%); opacity: 0; }
                to { transform: translateX(0); opacity: 1; }
              }
            `;
            document.head.appendChild(style);
            
            document.body.appendChild(notification);
            
            // Remove notification after 3 seconds
            setTimeout(() => {
              notification.style.animation = 'slideIn 0.3s ease-out reverse';
              setTimeout(() => {
                document.body.removeChild(notification);
                document.head.removeChild(style);
              }, 300);
            }, 3000);
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
            ? 'bg-gray-700 border-gray-600' 
            : 'bg-gray-50 border-gray-200'
        }`}>
          <div className="flex items-center justify-between mb-2">
            <span className={`text-sm font-medium ${
              isDarkTheme ? 'text-gray-300' : 'text-gray-700'
            }`}>
              Image Preview
            </span>
            <button
              onClick={removeImage}
              className={`text-sm px-2 py-1 rounded ${
                isDarkTheme ? 'hover:bg-gray-600' : 'hover:bg-gray-200'
              }`}
            >
              ✕
            </button>
          </div>
          <div className="flex items-center space-x-2 mb-2">
            <img 
              src={imagePreview} 
              alt="Preview" 
              className="w-20 h-20 object-cover rounded" 
            />
            <div className={`text-sm ${
              isDarkTheme ? 'text-gray-400' : 'text-gray-600'
            }`}>
              {imageFile?.name}
            </div>
          </div>
          <div className="mt-2 text-xs opacity-75">
            Click send to share this image
          </div>
        </div>
      )}

      {/* Message Input */}
      <form onSubmit={sendMessage} className="space-y-2">
        <div className="flex space-x-2">
          <textarea
            value={newMessage}
            onChange={(e) => setNewMessage(e.target.value)}
            onPaste={handlePaste}
            placeholder="Type your message... (Use $TSLA for stock tickers, or paste images with Ctrl+V)"
            rows="3"
            className={`flex-1 px-4 py-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${
              isDarkTheme 
                ? 'bg-gray-700 border-gray-600 text-white placeholder-gray-400' 
                : 'bg-white border-gray-300 text-gray-900 placeholder-gray-500'
            } border resize-none transition-all duration-200 ${
              imageFile ? 'border-green-500 bg-green-50/10' : ''
            }`}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage(e);
              }
            }}
          />
          
          {/* Image Upload Button */}
          <label className={`px-4 py-3 rounded-lg cursor-pointer transition-colors ${
            isDarkTheme 
              ? 'bg-gray-700 border-gray-600 text-gray-300 hover:bg-gray-600' 
              : 'bg-gray-100 border-gray-300 text-gray-700 hover:bg-gray-200'
          } border`}>
            📎
            <input
              type="file"
              accept="image/*"
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
          Press Enter to send, Shift+Enter for new line
        </div>
      </form>
    </div>
  );
};

export default ChatInput;