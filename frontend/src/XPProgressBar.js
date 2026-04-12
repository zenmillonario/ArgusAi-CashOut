import React from 'react';

const XPProgressBar = ({ currentXP, level, isDarkTheme }) => {
  const getLevelThresholds = () => [0, 500, 1500, 5000, 15000, 50000];
  
  const thresholds = getLevelThresholds();
  const currentLevelStart = thresholds[level - 1] || 0;
  const nextLevelStart = thresholds[level] || thresholds[thresholds.length - 1];
  
  const progressInLevel = currentXP - currentLevelStart;
  const totalForLevel = nextLevelStart - currentLevelStart;
  const progressPercentage = totalForLevel > 0 ? (progressInLevel / totalForLevel) * 100 : 100;
  
  const isMaxLevel = level >= thresholds.length - 1;
  
  return (
    <div className={`p-2 rounded-lg ${
      isDarkTheme ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'
    } border`}>
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center space-x-2">
          <span className="text-lg">⭐</span>
          <div>
            <h3 className={`font-bold text-sm ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
              Level {level}
            </h3>
            <p className={`text-xs ${isDarkTheme ? 'text-gray-400' : 'text-gray-600'}`}>
              {currentXP.toLocaleString()} XP
            </p>
          </div>
        </div>
        
        {!isMaxLevel && (
          <div className={`text-xs ${isDarkTheme ? 'text-gray-400' : 'text-gray-600'}`}>
            <span className="font-medium">{(nextLevelStart - currentXP).toLocaleString()}</span> XP to next
          </div>
        )}
      </div>
      
      {!isMaxLevel && (
        <div className={`w-full h-2 rounded-full ${
          isDarkTheme ? 'bg-gray-700' : 'bg-gray-200'
        }`}>
          <div 
            className="h-2 bg-gradient-to-r from-blue-500 to-purple-500 rounded-full transition-all duration-300"
            style={{ width: `${Math.min(progressPercentage, 100)}%` }}
          ></div>
        </div>
      )}
      
      {isMaxLevel && (
        <div className={`text-center py-1 ${isDarkTheme ? 'text-yellow-400' : 'text-yellow-600'}`}>
          <span className="text-sm">👑 MAX LEVEL REACHED!</span>
        </div>
      )}
    </div>
  );
};

export default XPProgressBar;