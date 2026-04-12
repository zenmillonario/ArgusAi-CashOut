// Enhanced Admin Panel with Member Management
// Replace your admin functionality with this comprehensive version

import React, { useState, useEffect } from 'react';

const AdminPanel = ({ 
  pendingUsers, 
  handleApproval, 
  currentUser, 
  isDarkTheme,
  API 
}) => {
  const [allUsers, setAllUsers] = useState([]);
  const [selectedUser, setSelectedUser] = useState(null);
  const [showUserModal, setShowUserModal] = useState(false);
  const [showRemoveConfirm, setShowRemoveConfirm] = useState(false);
  const [userToRemove, setUserToRemove] = useState(null);
  const [activeAdminTab, setActiveAdminTab] = useState('pending');

  // Load all users
  useEffect(() => {
    if (currentUser?.is_admin) {
      loadAllUsers();
      // Refresh every 30 seconds to update online status
      const interval = setInterval(loadAllUsers, 30000);
      return () => clearInterval(interval);
    }
  }, [currentUser]);

  const loadAllUsers = async () => {
    try {
      const response = await axios.get(`${API}/users/all?admin_id=${currentUser.id}`);
      setAllUsers(response.data);
    } catch (error) {
      console.error('Error loading users:', error);
    }
  };

  const setUserRole = async (userId, role) => {
    try {
      await axios.post(`${API}/users/${userId}/set-role?admin_id=${currentUser.id}`, {
        role: role
      });
      loadAllUsers();
      alert(`User role updated to ${role}`);
    } catch (error) {
      alert('Error updating user role: ' + (error.response?.data?.detail || error.message));
    }
  };

  const removeUser = async (userId) => {
    try {
      await axios.delete(`${API}/users/${userId}?admin_id=${currentUser.id}`);
      loadAllUsers();
      setShowRemoveConfirm(false);
      setUserToRemove(null);
      alert('User removed successfully');
    } catch (error) {
      alert('Error removing user: ' + (error.response?.data?.detail || error.message));
    }
  };

  const getUserStatusBadge = (user) => {
    if (user.is_admin) return { text: '👑 Admin', class: 'role-admin' };
    if (user.is_moderator) return { text: '🛡️ Moderator', class: 'role-moderator' };
    return { text: '👤 Member', class: 'role-member' };
  };

  const getOnlineStatus = (user) => {
    // Mock online status - in real implementation, this would be based on last_seen timestamp
    const isOnline = Math.random() > 0.6; // 40% chance of being online for demo
    return isOnline;
  };

  return (
    <div className="space-y-6">
      {/* Admin Panel Header */}
      <div className={`backdrop-blur-lg rounded-2xl border p-6 ${
        isDarkTheme 
          ? 'bg-white/5 border-white/10' 
          : 'bg-white/80 border-gray-200'
      }`}>
        <h2 className={`text-2xl font-bold mb-4 ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
          👑 Admin Panel
        </h2>
        
        {/* Admin Sub-Tabs */}
        <div className="flex space-x-2">
          <button
            onClick={() => setActiveAdminTab('pending')}
            className={`px-4 py-2 rounded-lg font-semibold transition-colors ${
              activeAdminTab === 'pending'
                ? 'bg-yellow-600 text-white'
                : isDarkTheme 
                  ? 'bg-white/10 text-gray-300 hover:bg-white/20' 
                  : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
            }`}
          >
            🔄 Pending Approvals ({pendingUsers.length})
          </button>
          <button
            onClick={() => setActiveAdminTab('members')}
            className={`px-4 py-2 rounded-lg font-semibold transition-colors ${
              activeAdminTab === 'members'
                ? 'bg-blue-600 text-white'
                : isDarkTheme 
                  ? 'bg-white/10 text-gray-300 hover:bg-white/20' 
                  : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
            }`}
          >
            👥 All Members ({allUsers.length})
          </button>
        </div>
      </div>

      {/* Pending Approvals Tab */}
      {activeAdminTab === 'pending' && (
        <div className={`backdrop-blur-lg rounded-2xl border p-6 ${
          isDarkTheme 
            ? 'bg-white/5 border-white/10' 
            : 'bg-white/80 border-gray-200'
        }`}>
          <h3 className={`text-xl font-bold mb-6 ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
            🔄 Pending Approvals
          </h3>
          
          {pendingUsers.length === 0 ? (
            <div className="text-center py-8">
              <div className="text-6xl mb-4">✅</div>
              <h4 className={`text-lg font-semibold mb-2 ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
                No Pending Approvals
              </h4>
              <p className={isDarkTheme ? 'text-gray-300' : 'text-gray-600'}>
                All users have been reviewed
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {pendingUsers.map((user) => (
                <div key={user.id} className="user-list-item">
                  <div className="flex items-center space-x-4">
                    {/* Avatar */}
                    <div className="w-12 h-12 rounded-full overflow-hidden border-2 border-white/20">
                      {user.avatar_url ? (
                        <img src={user.avatar_url} alt={user.username} className="w-full h-full object-cover" />
                      ) : (
                        <div className="w-full h-full bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center text-white font-bold">
                          {user.real_name?.charAt(0).toUpperCase() || user.username.charAt(0).toUpperCase()}
                        </div>
                      )}
                    </div>
                    
                    {/* User Info */}
                    <div className="flex-1">
                      <div className={`font-semibold ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
                        {user.real_name || user.username}
                      </div>
                      <div className={`text-sm ${isDarkTheme ? 'text-gray-300' : 'text-gray-600'}`}>
                        @{user.username} • {user.email}
                      </div>
                      <div className="text-xs text-gray-400">
                        Registered: {new Date(user.created_at).toLocaleString()}
                      </div>
                    </div>
                  </div>
                  
                  {/* Approval Actions */}
                  <div className="flex space-x-2">
                    <select
                      className="px-3 py-2 bg-white/10 border border-white/20 rounded text-white text-sm"
                      onChange={(e) => {
                        if (e.target.value === 'approve_member') {
                          handleApproval(user.id, true, 'member');
                        } else if (e.target.value === 'approve_moderator') {
                          handleApproval(user.id, true, 'moderator');
                        } else if (e.target.value === 'approve_admin') {
                          handleApproval(user.id, true, 'admin');
                        }
                      }}
                      defaultValue=""
                    >
                      <option value="">Approve as...</option>
                      <option value="approve_member">👤 Member</option>
                      <option value="approve_moderator">🛡️ Moderator</option>
                      <option value="approve_admin">👑 Admin</option>
                    </select>
                    <button
                      onClick={() => handleApproval(user.id, false)}
                      className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
                    >
                      ❌ Reject
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* All Members Tab */}
      {activeAdminTab === 'members' && (
        <div className={`backdrop-blur-lg rounded-2xl border p-6 ${
          isDarkTheme 
            ? 'bg-white/5 border-white/10' 
            : 'bg-white/80 border-gray-200'
        }`}>
          <h3 className={`text-xl font-bold mb-6 ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
            👥 All Members ({allUsers.length})
          </h3>
          
          {/* Member Stats */}
          <div className="grid grid-cols-4 gap-4 mb-6">
            <div className={`p-4 rounded-lg text-center ${isDarkTheme ? 'bg-white/5' : 'bg-gray-50'}`}>
              <div className="text-2xl font-bold text-yellow-400">
                {allUsers.filter(u => u.is_admin).length}
              </div>
              <div className={`text-sm ${isDarkTheme ? 'text-gray-300' : 'text-gray-600'}`}>
                Admins
              </div>
            </div>
            <div className={`p-4 rounded-lg text-center ${isDarkTheme ? 'bg-white/5' : 'bg-gray-50'}`}>
              <div className="text-2xl font-bold text-purple-400">
                {allUsers.filter(u => u.is_moderator && !u.is_admin).length}
              </div>
              <div className={`text-sm ${isDarkTheme ? 'text-gray-300' : 'text-gray-600'}`}>
                Moderators
              </div>
            </div>
            <div className={`p-4 rounded-lg text-center ${isDarkTheme ? 'bg-white/5' : 'bg-gray-50'}`}>
              <div className="text-2xl font-bold text-blue-400">
                {allUsers.filter(u => !u.is_admin && !u.is_moderator).length}
              </div>
              <div className={`text-sm ${isDarkTheme ? 'text-gray-300' : 'text-gray-600'}`}>
                Members
              </div>
            </div>
            <div className={`p-4 rounded-lg text-center ${isDarkTheme ? 'bg-white/5' : 'bg-gray-50'}`}>
              <div className="text-2xl font-bold text-green-400">
                {allUsers.filter(u => getOnlineStatus(u)).length}
              </div>
              <div className={`text-sm ${isDarkTheme ? 'text-gray-300' : 'text-gray-600'}`}>
                Online
              </div>
            </div>
          </div>
          
          {/* Members List */}
          <div className="space-y-3 max-h-96 overflow-y-auto">
            {allUsers.map((user) => {
              const isOnline = getOnlineStatus(user);
              const statusBadge = getUserStatusBadge(user);
              
              return (
                <div key={user.id} className="user-list-item">
                  <div className="flex items-center space-x-4">
                    {/* Avatar with Online Indicator */}
                    <div className="relative">
                      <div className="w-12 h-12 rounded-full overflow-hidden border-2 border-white/20">
                        {user.avatar_url ? (
                          <img src={user.avatar_url} alt={user.username} className="w-full h-full object-cover" />
                        ) : (
                          <div className="w-full h-full bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center text-white font-bold">
                            {user.real_name?.charAt(0).toUpperCase() || user.username.charAt(0).toUpperCase()}
                          </div>
                        )}
                      </div>
                      {/* Online Status Dot */}
                      <div className={`absolute -bottom-1 -right-1 w-4 h-4 rounded-full border-2 border-gray-800 ${
                        isOnline ? 'bg-green-500' : 'bg-gray-500'
                      }`}></div>
                    </div>
                    
                    {/* User Info */}
                    <div className="flex-1">
                      <div className="flex items-center space-x-2">
                        <span className={`font-semibold ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
                          {user.real_name || user.username}
                        </span>
                        <span className={`user-role-badge ${statusBadge.class}`}>
                          {statusBadge.text}
                        </span>
                      </div>
                      <div className={`text-sm ${isDarkTheme ? 'text-gray-300' : 'text-gray-600'}`}>
                        @{user.username} • {user.email}
                      </div>
                      <div className={`text-xs ${isOnline ? 'user-status-online' : 'user-status-offline'}`}>
                        {isOnline ? '🟢 Online' : '⚪ Last seen: ' + new Date(user.last_seen || user.created_at).toLocaleDateString()}
                      </div>
                    </div>
                  </div>
                  
                  {/* User Actions */}
                  {user.id !== currentUser.id && (
                    <div className="flex space-x-2">
                      <select
                        className="px-3 py-2 bg-white/10 border border-white/20 rounded text-white text-sm"
                        value={user.is_admin ? 'admin' : user.is_moderator ? 'moderator' : 'member'}
                        onChange={(e) => setUserRole(user.id, e.target.value)}
                      >
                        <option value="member">👤 Member</option>
                        <option value="moderator">🛡️ Moderator</option>
                        <option value="admin">👑 Admin</option>
                      </select>
                      
                      <button
                        onClick={() => {
                          setUserToRemove(user);
                          setShowRemoveConfirm(true);
                        }}
                        className="px-3 py-2 bg-red-600 text-white rounded hover:bg-red-700 transition-colors text-sm"
                      >
                        🗑️
                      </button>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Remove User Confirmation Modal */}
      {showRemoveConfirm && userToRemove && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-white/10 backdrop-blur-lg rounded-2xl p-6 w-full max-w-md border border-white/20">
            <h2 className="text-xl font-bold text-white mb-4">⚠️ Remove User</h2>
            <p className="text-gray-300 mb-6">
              Are you sure you want to remove <strong>{userToRemove.real_name || userToRemove.username}</strong> from the app? 
              This action cannot be undone.
            </p>
            
            <div className="flex space-x-4">
              <button
                onClick={() => removeUser(userToRemove.id)}
                className="flex-1 bg-red-600 text-white py-3 rounded-lg font-semibold hover:bg-red-700 transition-colors"
              >
                🗑️ Remove User
              </button>
              <button
                onClick={() => {
                  setShowRemoveConfirm(false);
                  setUserToRemove(null);
                }}
                className="flex-1 bg-gray-600 text-white py-3 rounded-lg font-semibold hover:bg-gray-700 transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AdminPanel;