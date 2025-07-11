import React, { useState, useEffect } from 'react';
import axios from 'axios';

const AchievementsTab = ({ currentUser, isDarkTheme }) => {
  const [achievements, setAchievements] = useState({ earned: [], available: [] });
  const [loading, setLoading] = useState(true);

  const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';
  const API = BACKEND_URL ? `${BACKEND_URL}/api` : '/api';

  useEffect(() => {
    fetchAchievements();
  }, [currentUser]);

  const fetchAchievements = async () => {
    try {
      const response = await axios.get(`${API}/users/${currentUser.id}/achievements`);
      setAchievements(response.data);
    } catch (error) {
      console.error('Error fetching achievements:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className={`animate-spin rounded-full h-16 w-16 border-4 ${
          isDarkTheme ? 'border-white/20 border-t-white' : 'border-gray-200 border-t-gray-900'
        }`}></div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto p-4 max-h-screen">{/* Add max-height and ensure scroll */}
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <h2 className={`text-3xl font-bold ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
            🏆 Achievements
          </h2>
          <div className={`text-sm ${isDarkTheme ? 'text-gray-400' : 'text-gray-600'}`}>
            {achievements.earned.length} of {achievements.total_available} earned
          </div>
        </div>

        {/* Progress Overview */}
        <div className={`p-4 rounded-lg mb-6 ${
          isDarkTheme ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'
        } border`}>
          <div className="flex items-center justify-between mb-2">
            <span className={`font-medium ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
              Achievement Progress
            </span>
            <span className={`text-sm ${isDarkTheme ? 'text-gray-400' : 'text-gray-600'}`}>
              {Math.round((achievements.earned.length / achievements.total_available) * 100)}% Complete
            </span>
          </div>
          <div className={`w-full h-3 rounded-full ${
            isDarkTheme ? 'bg-gray-700' : 'bg-gray-200'
          }`}>
            <div 
              className="h-3 bg-gradient-to-r from-yellow-500 to-orange-500 rounded-full transition-all duration-300"
              style={{ width: `${(achievements.earned.length / achievements.total_available) * 100}%` }}
            ></div>
          </div>
        </div>

        {/* Earned Achievements */}
        {achievements.earned.length > 0 && (
          <div className="mb-8">
            <h3 className={`text-xl font-bold mb-4 ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
              ✨ Earned Achievements
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {achievements.earned.map((achievement) => (
                <div
                  key={achievement.id}
                  className={`p-4 rounded-lg border-2 border-yellow-500 ${
                    isDarkTheme ? 'bg-yellow-900/20' : 'bg-yellow-50'
                  } relative overflow-hidden`}
                >
                  {/* Sparkle effect */}
                  <div className="absolute top-2 right-2 text-yellow-400 animate-pulse">
                    ✨
                  </div>
                  
                  <div className="flex items-start space-x-3">
                    <div className="text-3xl">{achievement.icon}</div>
                    <div className="flex-1">
                      <h4 className={`font-bold ${isDarkTheme ? 'text-yellow-300' : 'text-yellow-800'}`}>
                        {achievement.name}
                      </h4>
                      <p className={`text-sm ${isDarkTheme ? 'text-yellow-200' : 'text-yellow-700'}`}>
                        {achievement.description}
                      </p>
                      <div className="mt-2 flex items-center space-x-2">
                        <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${
                          isDarkTheme ? 'bg-yellow-800 text-yellow-200' : 'bg-yellow-200 text-yellow-800'
                        }`}>
                          +{achievement.points_reward} XP
                        </span>
                        <span className={`text-xs ${isDarkTheme ? 'text-yellow-400' : 'text-yellow-600'}`}>
                          {achievement.category}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Available Achievements */}
        <div>
          <h3 className={`text-xl font-bold mb-4 ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
            🎯 Available Achievements
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {achievements.available.map((achievement) => {
              const progressPercentage = Math.min(
                (achievement.current_progress / achievement.requirement_value) * 100,
                100
              );
              
              return (
                <div
                  key={achievement.id}
                  className={`p-4 rounded-lg border ${
                    isDarkTheme ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'
                  }`}
                >
                  <div className="flex items-start space-x-3">
                    <div className={`text-3xl ${progressPercentage > 50 ? '' : 'grayscale opacity-60'}`}>
                      {achievement.icon}
                    </div>
                    <div className="flex-1">
                      <h4 className={`font-bold ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
                        {achievement.name}
                      </h4>
                      <p className={`text-sm ${isDarkTheme ? 'text-gray-400' : 'text-gray-600'}`}>
                        {achievement.description}
                      </p>
                      
                      {/* Progress Bar */}
                      <div className="mt-3">
                        <div className="flex items-center justify-between mb-1">
                          <span className={`text-xs ${isDarkTheme ? 'text-gray-400' : 'text-gray-600'}`}>
                            Progress
                          </span>
                          <span className={`text-xs ${isDarkTheme ? 'text-gray-400' : 'text-gray-600'}`}>
                            {achievement.current_progress} / {achievement.requirement_value}
                          </span>
                        </div>
                        <div className={`w-full h-2 rounded-full ${
                          isDarkTheme ? 'bg-gray-700' : 'bg-gray-200'
                        }`}>
                          <div 
                            className="h-2 bg-gradient-to-r from-blue-500 to-purple-500 rounded-full transition-all duration-300"
                            style={{ width: `${progressPercentage}%` }}
                          ></div>
                        </div>
                      </div>
                      
                      <div className="mt-2 flex items-center space-x-2">
                        <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${
                          isDarkTheme ? 'bg-gray-700 text-gray-300' : 'bg-gray-100 text-gray-700'
                        }`}>
                          +{achievement.points_reward} XP
                        </span>
                        <span className={`text-xs ${isDarkTheme ? 'text-gray-500' : 'text-gray-500'}`}>
                          {achievement.category}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* No achievements yet */}
        {achievements.earned.length === 0 && achievements.available.length === 0 && (
          <div className={`text-center py-12 ${isDarkTheme ? 'text-gray-400' : 'text-gray-600'}`}>
            <div className="text-6xl mb-4">🏆</div>
            <h3 className="text-xl font-semibold mb-2">No Achievements Yet</h3>
            <p>Start trading, chatting, and exploring to earn your first achievements!</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default AchievementsTab;