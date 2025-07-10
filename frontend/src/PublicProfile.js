import React, { useState, useEffect } from 'react';
import axios from 'axios';

const PublicProfile = ({ userId, onClose, isDarkTheme, currentUser }) => {
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [isFollowing, setIsFollowing] = useState(false);
  const [followLoading, setFollowLoading] = useState(false);
  const [followerCount, setFollowerCount] = useState(0);
  const [followingCount, setFollowingCount] = useState(0);

  const API = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';

  useEffect(() => {
    fetchPublicProfile();
  }, [userId]);

  const fetchPublicProfile = async () => {
    try {
      const response = await axios.get(`${API}/users/${userId}/profile`);
      setProfile(response.data);
      setFollowerCount(response.data.follower_count || 0);
      setFollowingCount(response.data.following_count || 0);
      
      // Check if current user is following this user
      if (currentUser && response.data.followers) {
        setIsFollowing(response.data.followers.includes(currentUser.id));
      }
    } catch (error) {
      console.error('Error fetching public profile:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleFollow = async () => {
    if (!currentUser || followLoading) return;
    
    setFollowLoading(true);
    try {
      if (isFollowing) {
        await axios.post(`${API}/api/users/${currentUser.id}/unfollow`, {
          target_user_id: userId
        });
        setIsFollowing(false);
        setFollowerCount(prev => prev - 1);
      } else {
        await axios.post(`${API}/api/users/${currentUser.id}/follow`, {
          target_user_id: userId
        });
        setIsFollowing(true);
        setFollowerCount(prev => prev + 1);
      }
    } catch (error) {
      console.error('Error following/unfollowing user:', error);
      const errorMessage = error.response?.data?.detail || error.message || 'Error updating follow status';
      alert(`Follow Error: ${errorMessage}`);
    } finally {
      setFollowLoading(false);
    }
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'Unknown';
    return new Date(dateString).toLocaleDateString();
  };

  const formatLastSeen = (lastSeen) => {
    if (!lastSeen) return 'Never';
    const date = new Date(lastSeen);
    const now = new Date();
    const diffInMinutes = Math.floor((now - date) / (1000 * 60));
    
    if (diffInMinutes < 1) return 'Just now';
    if (diffInMinutes < 60) return `${diffInMinutes} minutes ago`;
    if (diffInMinutes < 1440) return `${Math.floor(diffInMinutes / 60)} hours ago`;
    return `${Math.floor(diffInMinutes / 1440)} days ago`;
  };

  if (loading) {
    return (
      <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
        <div className={`max-w-2xl w-full mx-4 p-6 rounded-xl ${
          isDarkTheme ? 'bg-gray-800' : 'bg-white'
        }`}>
          <div className="flex items-center justify-center">
            <div className={`animate-spin rounded-full h-16 w-16 border-4 ${
              isDarkTheme ? 'border-white/20 border-t-white' : 'border-gray-200 border-t-gray-900'
            }`}></div>
          </div>
        </div>
      </div>
    );
  }

  if (!profile) {
    return (
      <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
        <div className={`max-w-2xl w-full mx-4 p-6 rounded-xl ${
          isDarkTheme ? 'bg-gray-800' : 'bg-white'
        }`}>
          <div className="text-center">
            <div className="text-4xl mb-4">❌</div>
            <h3 className={`text-xl font-bold mb-2 ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
              Profile Not Found
            </h3>
            <p className={`mb-4 ${isDarkTheme ? 'text-gray-400' : 'text-gray-600'}`}>
              This user's profile could not be loaded.
            </p>
            <button
              onClick={onClose}
              className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    );
  }

  const tradingStyleOptions = {
    'day_trader': { label: '📈 Day Trader', color: 'bg-red-500' },
    'diamond_hands': { label: '💎 Diamond Hands', color: 'bg-blue-500' },
    'swing_trader': { label: '🎯 Swing Trader', color: 'bg-green-500' },
    'technical_analyst': { label: '📊 Technical Analyst', color: 'bg-purple-500' },
    'news_trader': { label: '📰 News Trader', color: 'bg-yellow-500' },
    'growth_investor': { label: '🌱 Growth Investor', color: 'bg-emerald-500' },
    'value_investor': { label: '💰 Value Investor', color: 'bg-indigo-500' },
    'momentum_trader': { label: '🚀 Momentum Trader', color: 'bg-pink-500' },
    'balanced_trader': { label: '⚖️ Balanced Trader', color: 'bg-gray-500' },
    'algo_trader': { label: '🤖 Algo Trader', color: 'bg-cyan-500' },
    'mobile_trader': { label: '📱 Mobile Trader', color: 'bg-orange-500' },
    'contrarian': { label: '🧠 Contrarian', color: 'bg-violet-500' }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4 overflow-y-auto">
      <div className={`max-w-4xl w-full my-8 rounded-xl ${
        isDarkTheme ? 'bg-gray-800' : 'bg-white'
      } max-h-[90vh] overflow-y-auto`}>
        
        {/* Header with Banner */}
        <div className="relative">
          {profile.profile_banner ? (
            <img
              src={profile.profile_banner}
              alt="Profile banner"
              className="w-full h-48 object-cover rounded-t-xl"
            />
          ) : (
            <div className={`w-full h-48 rounded-t-xl ${
              isDarkTheme ? 'bg-gradient-to-r from-gray-700 to-gray-600' : 'bg-gradient-to-r from-blue-500 to-purple-500'
            }`}></div>
          )}
          
          {/* Close Button */}
          <button
            onClick={onClose}
            className="absolute top-4 right-4 bg-black/50 text-white rounded-full w-10 h-10 flex items-center justify-center hover:bg-black/70 transition-colors"
          >
            ✕
          </button>
          
          {/* Profile Picture - Big and Prominent */}
          <div className="absolute -bottom-16 left-8">
            {profile.avatar_url ? (
              <img
                src={profile.avatar_url}
                alt={`${profile.username}'s profile`}
                className="w-32 h-32 rounded-full border-4 border-white shadow-xl object-cover"
              />
            ) : (
              <div className={`w-32 h-32 rounded-full border-4 border-white shadow-xl flex items-center justify-center text-4xl font-bold ${
                profile.is_admin 
                  ? 'bg-gradient-to-br from-yellow-400 to-orange-500 text-white' 
                  : 'bg-gradient-to-br from-blue-500 to-purple-500 text-white'
              }`}>
                {profile.is_admin ? '👑' : profile.username.charAt(0).toUpperCase()}
              </div>
            )}
            
            {/* Online Status */}
            <div className={`absolute -bottom-2 -right-2 w-8 h-8 rounded-full border-4 border-white ${
              profile.is_online ? 'bg-green-400' : 'bg-gray-400'
            }`}></div>
          </div>
        </div>

        {/* Profile Content */}
        <div className="pt-20 p-8">
          {/* Basic Info */}
          <div className="mb-6">
            <div className="flex items-center space-x-3 mb-2">
              <h1 className={`text-3xl font-bold ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
                {profile.screen_name || profile.username}
              </h1>
              {profile.is_admin && (
                <span className="bg-yellow-500 text-white px-3 py-1 rounded-full text-sm font-medium">
                  👑 Admin
                </span>
              )}
              <span className={`px-3 py-1 rounded-full text-sm font-medium ${
                profile.is_online 
                  ? 'bg-green-100 text-green-800' 
                  : 'bg-gray-100 text-gray-600'
              }`}>
                {profile.is_online ? '🟢 Online' : `⚫ ${formatLastSeen(profile.last_seen)}`}
              </span>
            </div>
            
            <div className="flex items-center justify-between">
              <div>
                <p className={`text-lg ${isDarkTheme ? 'text-gray-300' : 'text-gray-600'}`}>
                  @{profile.username} • {profile.role || 'Member'}
                </p>
                
                {/* Location Display */}
                {profile.location && profile.show_location && (
                  <p className={`text-sm mt-1 ${isDarkTheme ? 'text-gray-400' : 'text-gray-500'}`}>
                    📍 {profile.location}
                  </p>
                )}
              </div>
              
              {/* Follow/Unfollow Button */}
              {currentUser && currentUser.id !== userId && (
                <button
                  onClick={handleFollow}
                  disabled={followLoading}
                  className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                    isFollowing
                      ? 'bg-gray-500 text-white hover:bg-gray-600'
                      : 'bg-blue-500 text-white hover:bg-blue-600'
                  } disabled:opacity-50 disabled:cursor-not-allowed`}
                >
                  {followLoading ? '...' : isFollowing ? 'Following' : 'Follow'}
                </button>
              )}
            </div>
            
            {profile.bio && (
              <p className={`mt-4 text-base leading-relaxed ${isDarkTheme ? 'text-gray-300' : 'text-gray-700'}`}>
                {profile.bio}
              </p>
            )}
          </div>

          {/* Stats Grid */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <div className={`p-4 rounded-lg text-center ${isDarkTheme ? 'bg-gray-700' : 'bg-gray-100'}`}>
              <div className="text-2xl mb-1">⭐</div>
              <div className={`text-xl font-bold ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
                Level {profile.level}
              </div>
              <div className={`text-sm ${isDarkTheme ? 'text-gray-400' : 'text-gray-600'}`}>
                {profile.experience_points.toLocaleString()} XP
              </div>
            </div>

            <div className={`p-4 rounded-lg text-center ${isDarkTheme ? 'bg-gray-700' : 'bg-gray-100'}`}>
              <div className="text-2xl mb-1">👥</div>
              <div className={`text-xl font-bold ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
                {followerCount}
              </div>
              <div className={`text-sm ${isDarkTheme ? 'text-gray-400' : 'text-gray-600'}`}>
                Followers
              </div>
            </div>

            <div className={`p-4 rounded-lg text-center ${isDarkTheme ? 'bg-gray-700' : 'bg-gray-100'}`}>
              <div className="text-2xl mb-1">🔗</div>
              <div className={`text-xl font-bold ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
                {followingCount}
              </div>
              <div className={`text-sm ${isDarkTheme ? 'text-gray-400' : 'text-gray-600'}`}>
                Following
              </div>
            </div>

            <div className={`p-4 rounded-lg text-center ${isDarkTheme ? 'bg-gray-700' : 'bg-gray-100'}`}>
              <div className="text-2xl mb-1">🏆</div>
              <div className={`text-xl font-bold ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
                {profile.achievements.length}
              </div>
              <div className={`text-sm ${isDarkTheme ? 'text-gray-400' : 'text-gray-600'}`}>
                Achievements
              </div>
            </div>
          </div>

          {/* Additional Stats Grid */}
          <div className="grid grid-cols-2 md:grid-cols-2 gap-4 mb-6">
            <div className={`p-4 rounded-lg text-center ${isDarkTheme ? 'bg-gray-700' : 'bg-gray-100'}`}>
              <div className="text-2xl mb-1">📈</div>
              <div className={`text-xl font-bold ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
                {profile.win_percentage?.toFixed(1) || 0}%
              </div>
              <div className={`text-sm ${isDarkTheme ? 'text-gray-400' : 'text-gray-600'}`}>
                Win Rate
              </div>
            </div>

            <div className={`p-4 rounded-lg text-center ${isDarkTheme ? 'bg-gray-700' : 'bg-gray-100'}`}>
              <div className="text-2xl mb-1">🎯</div>
              <div className={`text-xl font-bold ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
                {profile.trades_count || 0}
              </div>
              <div className={`text-sm ${isDarkTheme ? 'text-gray-400' : 'text-gray-600'}`}>
                Total Trades
              </div>
            </div>
          </div>

          {/* Trading Style Tags */}
          {profile.trading_style_tags && profile.trading_style_tags.length > 0 && (
            <div className="mb-6">
              <h3 className={`text-lg font-bold mb-3 ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
                🏷️ Trading Style
              </h3>
              <div className="flex flex-wrap gap-2">
                {profile.trading_style_tags.map((tag) => {
                  const style = tradingStyleOptions[tag];
                  return style ? (
                    <span
                      key={tag}
                      className={`${style.color} text-white px-3 py-1 rounded-full text-sm font-medium`}
                    >
                      {style.label}
                    </span>
                  ) : null;
                })}
              </div>
            </div>
          )}

          {/* Member Info */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <h3 className={`text-lg font-bold mb-3 ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
                📅 Member Info
              </h3>
              <div className="space-y-2">
                <div className="flex justify-between">
                  <span className={`${isDarkTheme ? 'text-gray-400' : 'text-gray-600'}`}>
                    Member Since:
                  </span>
                  <span className={`font-medium ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
                    {formatDate(profile.created_at)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className={`${isDarkTheme ? 'text-gray-400' : 'text-gray-600'}`}>
                    Status:
                  </span>
                  <span className={`font-medium ${profile.is_online ? 'text-green-500' : 'text-gray-500'}`}>
                    {profile.is_online ? 'Online' : 'Offline'}
                  </span>
                </div>
              </div>
            </div>

            <div>
              <h3 className={`text-lg font-bold mb-3 ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
                💰 Trading Stats
              </h3>
              <div className="space-y-2">
                <div className="flex justify-between">
                  <span className={`${isDarkTheme ? 'text-gray-400' : 'text-gray-600'}`}>
                    Total Profit:
                  </span>
                  <span className={`font-medium ${
                    profile.total_profit >= 0 ? 'text-green-500' : 'text-red-500'
                  }`}>
                    ${profile.total_profit?.toLocaleString() || '0'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className={`${isDarkTheme ? 'text-gray-400' : 'text-gray-600'}`}>
                    Trades:
                  </span>
                  <span className={`font-medium ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
                    {profile.trades_count || 0}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PublicProfile;