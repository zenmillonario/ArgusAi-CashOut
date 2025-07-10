import React from 'react';

const UserList = ({ onlineUsers, allUsers, currentUser, isDarkTheme, showUserList, setShowUserList, onViewProfile }) => {
  // Combine online users with all users and show online status
  const getUserStatus = (user) => {
    const isOnline = onlineUsers.some(onlineUser => onlineUser.id === user.id);
    return isOnline;
  };

  const sortedUsers = allUsers.sort((a, b) => {
    // Sort by online status first, then by role (admin first), then by name
    const aOnline = getUserStatus(a);
    const bOnline = getUserStatus(b);
    
    if (aOnline !== bOnline) return bOnline ? 1 : -1;
    if (a.is_admin !== b.is_admin) return b.is_admin ? 1 : -1;
    return (a.screen_name || a.username).localeCompare(b.screen_name || b.username);
  });

  if (!showUserList) {
    return (
      <button
        onClick={() => setShowUserList(true)}
        className={`fixed right-4 top-1/2 transform -translate-y-1/2 z-10 p-2 rounded-l-lg ${
          isDarkTheme ? 'bg-gray-800 text-white' : 'bg-white text-gray-900'
        } shadow-lg border-l border-t border-b ${
          isDarkTheme ? 'border-gray-700' : 'border-gray-200'
        }`}
      >
        <span className="text-lg">👥</span>
      </button>
    );
  }

  return (
    <div className={`w-64 flex-shrink-0 ${
      isDarkTheme ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'
    } border-l overflow-y-auto`}>
      {/* Header */}
      <div className={`p-4 border-b ${
        isDarkTheme ? 'border-gray-700' : 'border-gray-200'
      }`}>
        <div className="flex items-center justify-between">
          <h3 className={`font-semibold ${
            isDarkTheme ? 'text-white' : 'text-gray-900'
          }`}>
            Online Users ({onlineUsers.length})
          </h3>
          <button
            onClick={() => setShowUserList(false)}
            className={`p-1 rounded ${
              isDarkTheme ? 'hover:bg-gray-700 text-gray-400' : 'hover:bg-gray-100 text-gray-600'
            }`}
          >
            ✕
          </button>
        </div>
      </div>

      {/* User List */}
      <div className="p-2">
        {sortedUsers.map((user) => {
          const isOnline = getUserStatus(user);
          const isCurrentUser = user.id === currentUser?.id;
          
          return (
            <div
              key={user.id}
              onClick={() => !isCurrentUser && onViewProfile && onViewProfile(user.id)}
              className={`flex items-center space-x-3 p-2 rounded-lg mb-1 ${
                isCurrentUser 
                  ? isDarkTheme ? 'bg-blue-900/50' : 'bg-blue-100'
                  : isDarkTheme ? 'hover:bg-gray-700 cursor-pointer' : 'hover:bg-gray-50 cursor-pointer'
              } transition-colors`}
            >
              {/* Avatar */}
              <div className="relative">
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
                
                {/* Online status indicator */}
                <div className={`absolute -bottom-1 -right-1 w-3 h-3 rounded-full border-2 ${
                  isDarkTheme ? 'border-gray-800' : 'border-white'
                } ${isOnline ? 'bg-green-400' : 'bg-gray-400'}`}></div>
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
                  {user.role || 'Member'}
                  {isOnline && (
                    <span className="ml-1 text-green-400">• Online</span>
                  )}
                </p>
              </div>
            </div>
          );
        })}

        {/* Offline Users Section */}
        {allUsers.filter(user => !getUserStatus(user)).length > 0 && (
          <>
            <div className={`px-2 py-1 mt-4 mb-2 text-xs font-semibold uppercase tracking-wide ${
              isDarkTheme ? 'text-gray-400' : 'text-gray-500'
            }`}>
              Offline ({allUsers.filter(user => !getUserStatus(user)).length})
            </div>
            
            {allUsers.filter(user => !getUserStatus(user)).map((user) => (
              <div
                key={user.id}
                onClick={() => onViewProfile && onViewProfile(user.id)}
                className={`flex items-center space-x-3 p-2 rounded-lg mb-1 opacity-60 cursor-pointer ${
                  isDarkTheme ? 'hover:bg-gray-700' : 'hover:bg-gray-50'
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
                  <p className={`text-sm font-medium truncate ${
                    isDarkTheme ? 'text-gray-300' : 'text-gray-600'
                  }`}>
                    {user.screen_name || user.username} 👁️
                  </p>
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
  );
};

export default UserList;