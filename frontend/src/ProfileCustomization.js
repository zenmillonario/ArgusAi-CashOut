import React, { useState, useEffect } from 'react';
import axios from 'axios';

const ProfileCustomization = ({ currentUser, isDarkTheme, onUpdate }) => {
  const [profile, setProfile] = useState({
    bio: '',
    trading_style_tags: [],
    profile_banner: ''
  });
  const [bannerFile, setBannerFile] = useState(null);
  const [bannerPreview, setBannerPreview] = useState(null);
  const [loading, setLoading] = useState(false);

  const API = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';

  const tradingStyleOptions = [
    { id: 'day_trader', label: '📈 Day Trader', color: 'bg-red-500' },
    { id: 'diamond_hands', label: '💎 Diamond Hands', color: 'bg-blue-500' },
    { id: 'swing_trader', label: '🎯 Swing Trader', color: 'bg-green-500' },
    { id: 'technical_analyst', label: '📊 Technical Analyst', color: 'bg-purple-500' },
    { id: 'news_trader', label: '📰 News Trader', color: 'bg-yellow-500' },
    { id: 'growth_investor', label: '🌱 Growth Investor', color: 'bg-emerald-500' },
    { id: 'value_investor', label: '💰 Value Investor', color: 'bg-indigo-500' },
    { id: 'momentum_trader', label: '🚀 Momentum Trader', color: 'bg-pink-500' },
    { id: 'balanced_trader', label: '⚖️ Balanced Trader', color: 'bg-gray-500' },
    { id: 'algo_trader', label: '🤖 Algo Trader', color: 'bg-cyan-500' },
    { id: 'mobile_trader', label: '📱 Mobile Trader', color: 'bg-orange-500' },
    { id: 'contrarian', label: '🧠 Contrarian', color: 'bg-violet-500' }
  ];

  useEffect(() => {
    fetchProfile();
  }, [currentUser]);

  const fetchProfile = async () => {
    try {
      const response = await axios.get(`${API}/api/users/${currentUser.id}/profile`);
      setProfile({
        bio: response.data.bio || '',
        trading_style_tags: response.data.trading_style_tags || [],
        profile_banner: response.data.profile_banner || ''
      });
      setBannerPreview(response.data.profile_banner);
    } catch (error) {
      console.error('Error fetching profile:', error);
    }
  };

  const handleBannerSelect = (e) => {
    const file = e.target.files[0];
    if (file) {
      setBannerFile(file);
      
      // Create preview
      const reader = new FileReader();
      reader.onload = (e) => {
        setBannerPreview(e.target.result);
      };
      reader.readAsDataURL(file);
    }
  };

  const removeBanner = () => {
    setBannerFile(null);
    setBannerPreview(null);
    setProfile(prev => ({ ...prev, profile_banner: '' }));
  };

  const toggleTradingStyle = (styleId) => {
    setProfile(prev => ({
      ...prev,
      trading_style_tags: prev.trading_style_tags.includes(styleId)
        ? prev.trading_style_tags.filter(id => id !== styleId)
        : [...prev.trading_style_tags, styleId]
    }));
  };

  const handleSave = async () => {
    setLoading(true);
    try {
      const updateData = {
        bio: profile.bio,
        trading_style_tags: profile.trading_style_tags,
        profile_banner: bannerPreview || profile.profile_banner
      };

      await axios.post(`${API}/api/users/${currentUser.id}/profile`, updateData);
      
      if (onUpdate) {
        onUpdate();
      }
      
      alert('Profile updated successfully!');
    } catch (error) {
      console.error('Error updating profile:', error);
      alert('Error updating profile');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Profile Banner */}
      <div className={`p-6 rounded-lg border ${
        isDarkTheme ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'
      }`}>
        <h3 className={`text-lg font-bold mb-4 ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
          🖼️ Profile Banner
        </h3>
        
        {bannerPreview ? (
          <div className="relative">
            <img
              src={bannerPreview}
              alt="Profile banner"
              className="w-full h-32 object-cover rounded-lg"
            />
            <button
              onClick={removeBanner}
              className="absolute top-2 right-2 bg-red-500 text-white rounded-full w-8 h-8 flex items-center justify-center hover:bg-red-600 transition-colors"
            >
              ✕
            </button>
          </div>
        ) : (
          <div className={`border-2 border-dashed rounded-lg p-6 text-center ${
            isDarkTheme ? 'border-gray-600 text-gray-400' : 'border-gray-300 text-gray-600'
          }`}>
            <div className="text-4xl mb-2">🖼️</div>
            <p className="mb-2">Add a profile banner</p>
            <input
              type="file"
              accept="image/*"
              onChange={handleBannerSelect}
              className="hidden"
              id="banner-upload"
            />
            <label
              htmlFor="banner-upload"
              className="inline-flex items-center px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 cursor-pointer transition-colors"
            >
              Choose Image
            </label>
          </div>
        )}
      </div>

      {/* Bio Section */}
      <div className={`p-6 rounded-lg border ${
        isDarkTheme ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'
      }`}>
        <h3 className={`text-lg font-bold mb-4 ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
          📝 Bio
        </h3>
        <textarea
          value={profile.bio}
          onChange={(e) => setProfile(prev => ({ ...prev, bio: e.target.value }))}
          placeholder="Tell other traders about your trading philosophy, experience, and goals..."
          className={`w-full h-24 p-3 rounded-lg border resize-none ${
            isDarkTheme 
              ? 'bg-gray-700 border-gray-600 text-white placeholder-gray-400' 
              : 'bg-white border-gray-300 text-gray-900 placeholder-gray-500'
          }`}
          maxLength={500}
        />
        <div className={`text-sm mt-2 text-right ${
          isDarkTheme ? 'text-gray-400' : 'text-gray-600'
        }`}>
          {profile.bio.length}/500
        </div>
      </div>

      {/* Trading Style Tags */}
      <div className={`p-6 rounded-lg border ${
        isDarkTheme ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'
      }`}>
        <h3 className={`text-lg font-bold mb-4 ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
          🏷️ Trading Style Tags
        </h3>
        <p className={`text-sm mb-4 ${isDarkTheme ? 'text-gray-400' : 'text-gray-600'}`}>
          Select tags that describe your trading style (max 3)
        </p>
        
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          {tradingStyleOptions.map((style) => {
            const isSelected = profile.trading_style_tags.includes(style.id);
            const canSelect = !isSelected && profile.trading_style_tags.length < 3;
            
            return (
              <button
                key={style.id}
                onClick={() => toggleTradingStyle(style.id)}
                disabled={!isSelected && !canSelect}
                className={`p-3 rounded-lg border-2 text-sm font-medium transition-all ${
                  isSelected
                    ? `${style.color} text-white border-transparent`
                    : canSelect
                    ? isDarkTheme
                      ? 'border-gray-600 text-gray-300 hover:border-gray-500'
                      : 'border-gray-300 text-gray-700 hover:border-gray-400'
                    : 'opacity-50 cursor-not-allowed border-gray-300 text-gray-500'
                }`}
              >
                {style.label}
              </button>
            );
          })}
        </div>
        
        <div className={`text-sm mt-3 ${isDarkTheme ? 'text-gray-400' : 'text-gray-600'}`}>
          {profile.trading_style_tags.length}/3 selected
        </div>
      </div>

      {/* Save Button */}
      <div className="flex justify-end">
        <button
          onClick={handleSave}
          disabled={loading}
          className="px-6 py-3 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-medium"
        >
          {loading ? 'Saving...' : 'Save Profile'}
        </button>
      </div>
    </div>
  );
};

export default ProfileCustomization;