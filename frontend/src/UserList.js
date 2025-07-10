import React from 'react';
import axios from 'axios';

const UserList = ({ onlineUsers, allUsers, currentUser, isDarkTheme, showUserList, setShowUserList, onViewProfile }) => {
  const [followingUsers, setFollowingUsers] = React.useState([]);
  const [followerCounts, setFollowerCounts] = React.useState({});

  const API = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';

  React.useEffect(() => {
    // Fetch current user's following list
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
    // Fetch follower counts for all users
    const fetchFollowerCounts = async () => {
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

    if (allUsers.length > 0) {
      fetchFollowerCounts();
    }
  }, [allUsers, API]);

  const getUserStatus = (user) => {
    return onlineUsers.some(onlineUser => onlineUser.id === user.id);
  };

  const sortedUsers = [...onlineUsers].sort((a, b) => {
    if (a.is_admin !== b.is_admin) return b.is_admin ? 1 : -1;
    return (a.screen_name || a.username).localeCompare(b.screen_name || b.username);
  });

  if (!showUserList) {
    return (
      <button
        onClick={() => setShowUserList(true)}
        className={`fixed right-4 top-1/2 transform -translate-y-1/2 z-10 p-2 rounded-l-lg md:hidden ${
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
    <>
      {/* Mobile Modal Overlay */}
      {showUserList && (
        <div className="fixed inset-0 bg-black/50 z-50 md:hidden">
          <div className={`fixed right-0 top-0 bottom-0 w-80 ${
            isDarkTheme ? 'bg-gray-800' : 'bg-white'
          } transform transition-transform duration-300`}>
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
                  className={`p-2 rounded ${
                    isDarkTheme ? 'hover:bg-gray-700 text-gray-400' : 'hover:bg-gray-100 text-gray-600'
                  }`}
                >
                  ✕
                </button>
              </div>
            </div>

            {/* User List */}
            <div className="flex-1 overflow-y-auto p-2 h-full">
              {sortedUsers.map((user) => {
                const isOnline = getUserStatus(user);
                const isCurrentUser = user.id === currentUser?.id;
                const isFollowing = followingUsers.includes(user.id);
                const followerCount = followerCounts[user.id] || 0;
                
                return (
                  <div
                    key={`mobile-${user.id}`}
                    onClick={() => {
                      if (!isCurrentUser && onViewProfile) {
                        onViewProfile(user.id);
                        setShowUserList(false);
                      }
                    }}
                    className={`flex items-center space-x-3 p-3 rounded-lg mb-2 ${
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
                        {!isCurrentUser && isFollowing && (
                          <span className="text-xs bg-blue-500 text-white px-1 rounded">Following</span>
                        )}
                      </div>
                      
                      <div className="flex items-center space-x-2">
                        <p className={`text-xs truncate ${
                          isDarkTheme ? 'text-gray-400' : 'text-gray-500'
                        }`}>
                          {user.role || 'Member'}
                          {isOnline && (
                            <span className="ml-1 text-green-400">• Online</span>
                          )}
                        </p>
                        {followerCount > 0 && (
                          <span className={`text-xs ${isDarkTheme ? 'text-gray-400' : 'text-gray-500'}`}>
                            👥 {followerCount}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* Desktop User List */}
      <div className={`w-64 flex-shrink-0 flex flex-col h-full ${
        isDarkTheme ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'
      } border-l hidden md:flex`}>
        {/* Header */}
        <div className={`p-4 border-b ${
          isDarkTheme ? 'border-gray-700' : 'border-gray-200'
        }`}>
          <h3 className={`font-semibold ${
            isDarkTheme ? 'text-white' : 'text-gray-900'
          }`}>
            Online Users ({onlineUsers.length})
          </h3>
        </div>

        {/* Desktop User List - Scrollable */}
        <div className="flex-1 overflow-y-auto p-2">
          {sortedUsers.map((user) => {
            const isOnline = getUserStatus(user);
            const isCurrentUser = user.id === currentUser?.id;
            const isFollowing = followingUsers.includes(user.id);
            const followerCount = followerCounts[user.id] || 0;
            
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
                    {!isCurrentUser && isFollowing && (
                      <span className="text-xs bg-blue-500 text-white px-1 rounded">Following</span>
                    )}
                  </div>
                  
                  <div className="flex items-center space-x-2">
                    <p className={`text-xs truncate ${
                      isDarkTheme ? 'text-gray-400' : 'text-gray-500'
                    }`}>
                      {user.role || 'Member'}
                      {isOnline && (
                        <span className="ml-1 text-green-400">• Online</span>
                      )}
                    </p>
                    {followerCount > 0 && (
                      <span className={`text-xs ${isDarkTheme ? 'text-gray-400' : 'text-gray-500'}`}>
                        👥 {followerCount}
                      </span>
                    )}
                  </div>
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
              
              {allUsers.filter(user => !getUserStatus(user)).map((user) => {
                const isFollowing = followingUsers.includes(user.id);
                const followerCount = followerCounts[user.id] || 0;
                
                return (
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
                      <div className="flex items-center space-x-1">
                        <p className={`text-sm font-medium truncate ${
                          isDarkTheme ? 'text-gray-300' : 'text-gray-600'
                        }`}>
                          {user.screen_name || user.username} 👁️
                        </p>
                        {user.is_admin && (
                          <span className="text-xs">👑</span>
                        )}
                        {isFollowing && (
                          <span className="text-xs bg-blue-500 text-white px-1 rounded">Following</span>
                        )}
                      </div>
                      
                      <div className="flex items-center space-x-2">
                        <p className={`text-xs truncate ${
                          isDarkTheme ? 'text-gray-500' : 'text-gray-400'
                        }`}>
                          {user.role || 'Member'}
                        </p>
                        {followerCount > 0 && (
                          <span className={`text-xs ${isDarkTheme ? 'text-gray-500' : 'text-gray-400'}`}>
                            👥 {followerCount}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </>
          )}
        </div>
      </div>
    </>
  );
};

export default UserList;