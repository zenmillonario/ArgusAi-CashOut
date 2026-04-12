// Theme and Tab Visibility Fixes
// Update your main App.js header section with these fixed tab styles

const TabNavigation = ({ activeTab, setActiveTab, currentUser, pendingUsers, isDarkTheme }) => {
  const getTabClasses = (tabName) => {
    const isActive = activeTab === tabName;
    
    if (isDarkTheme) {
      return `px-4 py-2 rounded-lg transition-colors font-semibold ${
        isActive 
          ? 'bg-blue-600 text-white border border-blue-600' 
          : 'bg-white/10 text-gray-300 hover:bg-white/20 border border-white/20'
      }`;
    } else {
      return `px-4 py-2 rounded-lg transition-colors font-semibold ${
        isActive 
          ? 'bg-blue-600 text-white border border-blue-600' 
          : 'bg-blue-100 text-blue-800 hover:bg-blue-200 border border-blue-200'
      }`;
    }
  };

  return (
    <div className="flex space-x-2">
      <button
        onClick={() => setActiveTab('chat')}
        className={getTabClasses('chat')}
      >
        💬 Chat
      </button>
      <button
        onClick={() => setActiveTab('practice')}
        className={getTabClasses('practice')}
      >
        📈 Practice
      </button>
      <button
        onClick={() => setActiveTab('portfolio')}
        className={getTabClasses('portfolio')}
      >
        📊 Portfolio
      </button>
      <button
        onClick={() => setActiveTab('profile')}
        className={getTabClasses('profile')}
      >
        👤 Profile
      </button>
      {currentUser?.is_admin && (
        <button
          onClick={() => setActiveTab('admin')}
          className={`${getTabClasses('admin')} relative`}
        >
          👑 Admin
          {pendingUsers.length > 0 && (
            <span className="absolute -top-2 -right-2 bg-red-500 text-white rounded-full w-6 h-6 text-xs flex items-center justify-center font-bold">
              {pendingUsers.length}
            </span>
          )}
        </button>
      )}
    </div>
  );
};

// Enhanced Header Component with Fixed Theme Support
const AppHeader = ({ 
  currentUser, 
  isConnected, 
  activeTab, 
  setActiveTab, 
  pendingUsers, 
  showSearch, 
  setShowSearch, 
  isDarkTheme, 
  toggleTheme, 
  logout 
}) => {
  return (
    <div className={`backdrop-blur-lg border-b p-4 ${
      isDarkTheme 
        ? 'bg-black/20 border-white/10' 
        : 'bg-white/90 border-gray-200'
    }`}>
      <div className="flex items-center justify-between max-w-6xl mx-auto">
        {/* Logo and Connection Status */}
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
            <h1 className={`text-2xl font-bold ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
              CashOutAi
            </h1>
          </div>
          <div className="flex items-center space-x-2">
            <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`}></div>
            <span className={`text-sm ${isDarkTheme ? 'text-gray-300' : 'text-gray-600'}`}>
              {isConnected ? 'Connected' : 'Disconnected'}
            </span>
          </div>
        </div>
        
        <div className="flex items-center space-x-4">
          {/* Fixed Tab Navigation */}
          <TabNavigation 
            activeTab={activeTab}
            setActiveTab={setActiveTab}
            currentUser={currentUser}
            pendingUsers={pendingUsers}
            isDarkTheme={isDarkTheme}
          />
          
          {/* Action Buttons */}
          <div className="flex items-center space-x-2">
            {activeTab === 'chat' && (
              <button
                onClick={() => setShowSearch(!showSearch)}
                className={`p-2 rounded-lg transition-colors ${
                  isDarkTheme 
                    ? 'bg-white/10 text-gray-300 hover:bg-white/20' 
                    : 'bg-blue-100 text-blue-600 hover:bg-blue-200'
                }`}
                title="Search messages"
              >
                🔍
              </button>
            )}
            
            <button
              onClick={toggleTheme}
              className={`p-2 rounded-lg transition-colors ${
                isDarkTheme 
                  ? 'bg-white/10 text-gray-300 hover:bg-white/20' 
                  : 'bg-blue-100 text-blue-600 hover:bg-blue-200'
              }`}
              title="Toggle theme"
            >
              {isDarkTheme ? '☀️' : '🌙'}
            </button>
          </div>
          
          {/* User Info */}
          <div className="text-right">
            <div className={`font-semibold ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
              {currentUser?.real_name || currentUser?.username}
            </div>
            <div className={`text-xs ${isDarkTheme ? 'text-gray-400' : 'text-gray-600'}`}>
              {currentUser?.is_admin ? '👑 Admin' : currentUser?.is_moderator ? '🛡️ Moderator' : '👤 Member'}
            </div>
          </div>
          
          <button
            onClick={logout}
            className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors font-semibold"
          >
            Logout
          </button>
        </div>
      </div>
    </div>
  );
};

export { TabNavigation, AppHeader };