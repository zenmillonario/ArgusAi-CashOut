import React from 'react';

const PortfolioTab = ({ 
  openPositions, 
  userPerformance, 
  closePosition, 
  isDarkTheme 
}) => {
  const totalUnrealizedPnL = openPositions.reduce((sum, pos) => sum + (pos.unrealized_pnl || 0), 0);

  return (
    <div className="space-y-6">
      {/* Portfolio Summary */}
      <div className={`backdrop-blur-lg rounded-2xl border p-6 ${
        isDarkTheme 
          ? 'bg-white/5 border-white/10' 
          : 'bg-white/80 border-gray-200'
      }`}>
        <h2 className={`text-2xl font-bold mb-6 ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
          📊 Portfolio Overview
        </h2>
        
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-6">
          <div className={`p-4 rounded-xl text-center ${
            isDarkTheme ? 'bg-white/5' : 'bg-gray-50'
          }`}>
            <div className={`text-2xl font-bold ${
              totalUnrealizedPnL >= 0 ? 'text-green-400' : 'text-red-400'
            }`}>
              {totalUnrealizedPnL >= 0 ? '+' : ''}${totalUnrealizedPnL.toFixed(2)}
            </div>
            <div className={`mt-2 ${isDarkTheme ? 'text-gray-300' : 'text-gray-600'}`}>
              Unrealized P&L
            </div>
          </div>
          
          <div className={`p-4 rounded-xl text-center ${
            isDarkTheme ? 'bg-white/5' : 'bg-gray-50'
          }`}>
            <div className="text-2xl font-bold text-blue-400">
              {openPositions.length}
            </div>
            <div className={`mt-2 ${isDarkTheme ? 'text-gray-300' : 'text-gray-600'}`}>
              Open Positions
            </div>
          </div>
          
          {userPerformance && (
            <>
              <div className={`p-4 rounded-xl text-center ${
                isDarkTheme ? 'bg-white/5' : 'bg-gray-50'
              }`}>
                <div className="text-2xl font-bold text-green-400">
                  ${userPerformance.total_profit.toFixed(2)}
                </div>
                <div className={`mt-2 ${isDarkTheme ? 'text-gray-300' : 'text-gray-600'}`}>
                  Total Realized
                </div>
              </div>
              
              <div className={`p-4 rounded-xl text-center ${
                isDarkTheme ? 'bg-white/5' : 'bg-gray-50'
              }`}>
                <div className="text-2xl font-bold text-purple-400">
                  {userPerformance.win_percentage.toFixed(1)}%
                </div>
                <div className={`mt-2 ${isDarkTheme ? 'text-gray-300' : 'text-gray-600'}`}>
                  Win Rate
                </div>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Open Positions */}
      {openPositions.length > 0 ? (
        <div className={`backdrop-blur-lg rounded-2xl border p-6 ${
          isDarkTheme 
            ? 'bg-white/5 border-white/10' 
            : 'bg-white/80 border-gray-200'
        }`}>
          <h3 className={`text-xl font-bold mb-6 ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
            📈 Open Positions
          </h3>
          <div className="space-y-4">
            {openPositions.map((position) => (
              <div key={position.id} className={`p-4 rounded-lg ${
                isDarkTheme ? 'bg-white/5' : 'bg-gray-50'
              }`}>
                <div className="flex justify-between items-center">
                  <div className="flex items-center space-x-4">
                    <div className={`font-bold text-lg ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
                      {position.symbol}
                    </div>
                    <div className={isDarkTheme ? 'text-gray-300' : 'text-gray-700'}>
                      {position.quantity} shares @ ${position.avg_price}
                    </div>
                    <div className="text-gray-400 text-sm">
                      Opened: {new Date(position.opened_at).toLocaleDateString()}
                    </div>
                  </div>
                  
                  <div className="flex items-center space-x-4">
                    <div className="text-right">
                      <div className={`font-semibold ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
                        Current: ${position.current_price || 'Loading...'}
                      </div>
                      <div className={`text-sm font-bold ${
                        position.unrealized_pnl >= 0 ? 'text-green-400' : 'text-red-400'
                      }`}>
                        {position.unrealized_pnl >= 0 ? '+' : ''}${position.unrealized_pnl || '0.00'} 
                        {position.current_price && position.avg_price && (
                          <span className="ml-2">
                            ({((position.current_price - position.avg_price) / position.avg_price * 100).toFixed(2)}%)
                          </span>
                        )}
                      </div>
                    </div>
                    
                    <button
                      onClick={() => closePosition(position.id, position.symbol)}
                      className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors text-sm"
                    >
                      Close Position
                    </button>
                  </div>
                </div>
                
                {/* Stop Loss & Take Profit Indicators */}
                {(position.stop_loss || position.take_profit) && (
                  <div className="mt-3 flex flex-wrap gap-3">
                    {position.stop_loss && (
                      <div className="flex items-center space-x-2 px-3 py-1 bg-red-500/10 border border-red-500/30 rounded-lg">
                        <span className="text-red-400 text-sm">🛑 Stop Loss:</span>
                        <span className="text-red-400 font-semibold text-sm">${position.stop_loss}</span>
                        {position.current_price && (
                          <span className="text-xs text-red-300">
                            ({((position.stop_loss - position.current_price) / position.current_price * 100).toFixed(1)}% away)
                          </span>
                        )}
                      </div>
                    )}
                    
                    {position.take_profit && (
                      <div className="flex items-center space-x-2 px-3 py-1 bg-green-500/10 border border-green-500/30 rounded-lg">
                        <span className="text-green-400 text-sm">🎯 Take Profit:</span>
                        <span className="text-green-400 font-semibold text-sm">${position.take_profit}</span>
                        {position.current_price && (
                          <span className="text-xs text-green-300">
                            ({((position.take_profit - position.current_price) / position.current_price * 100).toFixed(1)}% away)
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                )}
                
                {/* Auto-close warning if close to triggers */}
                {position.current_price && (
                  <div className="mt-2">
                    {position.stop_loss && position.current_price <= position.stop_loss * 1.02 && (
                      <div className="text-xs text-red-400 bg-red-500/10 px-2 py-1 rounded">
                        ⚠️ Approaching stop loss trigger
                      </div>
                    )}
                    {position.take_profit && position.current_price >= position.take_profit * 0.98 && (
                      <div className="text-xs text-green-400 bg-green-500/10 px-2 py-1 rounded">
                        🎯 Approaching take profit trigger
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div className={`backdrop-blur-lg rounded-2xl border p-6 text-center ${
          isDarkTheme 
            ? 'bg-white/5 border-white/10' 
            : 'bg-white/80 border-gray-200'
        }`}>
          <div className="text-6xl mb-4">📊</div>
          <h3 className={`text-xl font-bold mb-2 ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
            No Open Positions
          </h3>
          <p className={isDarkTheme ? 'text-gray-300' : 'text-gray-600'}>
            Start trading in the Practice tab to see your portfolio here!
          </p>
        </div>
      )}
    </div>
  );
};

export default PortfolioTab;
