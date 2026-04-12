import React, { useEffect, useRef } from 'react';

const NotificationsTab = ({ notifications, isDarkTheme, currentUser, onMarkAsRead, onDeleteNotification }) => {
  const processedNotifications = useRef(new Set());
  // Auto-mark notifications as read when they're viewed
  useEffect(() => {
    if (!notifications || !onMarkAsRead) return;
    
    // Mark unread notifications as read when they're displayed
    notifications.forEach(notification => {
      if (!notification.read && !processedNotifications.current.has(notification.id)) {
        // Mark this notification as processed to prevent duplicate API calls
        processedNotifications.current.add(notification.id);
        // Auto-mark as read
        onMarkAsRead(notification.id);
      }
    });
  }, [notifications, onMarkAsRead]);

  const formatDate = (dateString) => {
    if (!dateString) return '';
    const date = new Date(dateString);
    const now = new Date();
    const diffInMinutes = Math.floor((now - date) / (1000 * 60));
    
    if (diffInMinutes < 1) return 'Just now';
    if (diffInMinutes < 60) return `${diffInMinutes}m ago`;
    if (diffInMinutes < 1440) return `${Math.floor(diffInMinutes / 60)}h ago`;
    return `${Math.floor(diffInMinutes / 1440)}d ago`;
  };
  if (!notifications || notifications.length === 0) {
    return (
      <div className={`flex-1 flex flex-col items-center justify-center p-8 ${
        isDarkTheme ? 'text-gray-400' : 'text-gray-600'
      }`}>
        <div className="text-6xl mb-4">🔔</div>
        <h2 className="text-2xl font-bold mb-2">No Notifications</h2>
        <p className="text-center">
          You'll receive notifications here when someone replies to your messages or reacts to them.
        </p>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto p-4">
      <div className="max-w-4xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <h2 className={`text-2xl font-bold ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
            🔔 Notifications
          </h2>
          <span className={`text-sm ${isDarkTheme ? 'text-gray-400' : 'text-gray-600'}`}>
            {notifications.length} notification{notifications.length !== 1 ? 's' : ''}
          </span>
        </div>

        <div className="space-y-4">
          {notifications.map((notification, index) => (
            <div
              key={index}
              className={`p-4 rounded-lg border transition-colors ${
                isDarkTheme
                  ? 'bg-gray-800 border-gray-700 hover:bg-gray-750'
                  : 'bg-white border-gray-200 hover:bg-gray-50'
              }`}
            >
              <div className="flex items-start space-x-3">
                {/* Notification Icon */}
                <div className="flex-shrink-0">
                  {notification.type === 'reply' && (
                    <div className="w-10 h-10 bg-blue-500 rounded-full flex items-center justify-center">
                      <span className="text-white text-lg">↩️</span>
                    </div>
                  )}
                  {notification.type === 'reaction' && (
                    <div className="w-10 h-10 bg-red-500 rounded-full flex items-center justify-center">
                      <span className="text-white text-lg">❤️</span>
                    </div>
                  )}
                  {notification.type === 'follow' && (
                    <div className="w-10 h-10 bg-green-500 rounded-full flex items-center justify-center">
                      <span className="text-white text-lg">👥</span>
                    </div>
                  )}
                  {notification.type === 'achievement' && (
                    <div className="w-10 h-10 bg-yellow-500 rounded-full flex items-center justify-center">
                      <span className="text-white text-lg">🏆</span>
                    </div>
                  )}
                </div>

                {/* Notification Content */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between mb-2">
                    <p className={`text-sm font-medium ${
                      isDarkTheme ? 'text-white' : 'text-gray-900'
                    }`}>
                      {notification.type === 'reply' && (
                        <>
                          <span className="font-bold">{notification.from}</span> replied to your message
                        </>
                      )}
                      {notification.type === 'reaction' && (
                        <>
                          <span className="font-bold">{notification.from}</span> reacted to your message
                        </>
                      )}
                      {notification.type === 'follow' && (
                        <>
                          <span className="font-bold">{notification.data?.follower_name || notification.from}</span> started following you
                        </>
                      )}
                      {notification.type === 'achievement' && (
                        <>
                          🏆 <span className="font-bold">{notification.title}</span>
                        </>
                      )}
                    </p>
                    <span className={`text-xs ${
                      isDarkTheme ? 'text-gray-400' : 'text-gray-500'
                    }`}>
                      {formatDate(notification.created_at)}
                    </span>
                  </div>

                  {/* Notification Message */}
                  <p className={`text-sm ${isDarkTheme ? 'text-gray-300' : 'text-gray-700'}`}>
                    {notification.message}
                  </p>

                  {/* Action Buttons */}
                  <div className="flex items-center space-x-2 mt-3">
                    {notification.read && (
                      <span className="text-xs bg-green-100 text-green-800 px-2 py-1 rounded">
                        ✓ Read
                      </span>
                    )}
                    <button
                      onClick={() => onDeleteNotification && onDeleteNotification(notification.id)}
                      className="text-xs bg-red-500 text-white px-2 py-1 rounded hover:bg-red-600 transition-colors"
                    >
                      Delete
                    </button>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default NotificationsTab;