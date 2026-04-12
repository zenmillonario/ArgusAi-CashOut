// Enhanced Portfolio Tab with Buy/Add/Sell Buttons
// Replace your PortfolioTab.js with this enhanced version

import React, { useState } from 'react';

const PortfolioTab = ({ 
  openPositions, 
  userPerformance, 
  closePosition, 
  isDarkTheme,
  addSharesToPosition,
  sellSharesFromPosition
}) => {
  const [showTradeModal, setShowTradeModal] = useState(false);
  const [selectedPosition, setSelectedPosition] = useState(null);
  const [tradeAction, setTradeAction] = useState('buy');
  const [tradeForm, setTradeForm] = useState({
    quantity: '',
    price: ''
  });

  const totalUnrealizedPnL = openPositions.reduce((sum, pos) => sum + (pos.unrealized_pnl || 0), 0);

  const handlePositionAction = (position, action) => {
    setSelectedPosition(position);
    setTradeAction(action);
    setShowTradeModal(true);
    setTradeForm({ quantity: '', price: '' });
  };

  const executePositionTrade = async () => {
    if (!selectedPosition || !tradeForm.quantity || !tradeForm.price) return;

    try {
      if (tradeAction === 'buy' || tradeAction === 'add') {
        await addSharesToPosition(selectedPosition.id, {
          quantity: parseInt(tradeForm.quantity),
          price: parseFloat(tradeForm.price)
        });
      } else if (tradeAction === 'sell') {
        await sellSharesFromPosition(selectedPosition.id, {
          quantity: parseInt(tradeForm.quantity),
          price: parseFloat(tradeForm.price)
        });
      }
      setShowTradeModal(false);
    } catch (error) {
      alert('Error executing trade: ' + error.message);
    }
  };

  return (
    <div className="space-y-6">
      {/* Enhanced Portfolio Summary */}
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

      {/* Enhanced Open Positions with Action Buttons */}
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
              <div key={position.id} className="position-card-enhanced">
                {/* Position Header */}
                <div className="flex justify-between items-start mb-4">
                  <div className="flex items-center space-x-4">
                    <div className={`font-bold text-xl ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
                      {position.symbol}
                    </div>
                    <div className={`text-sm ${isDarkTheme ? 'text-gray-300' : 'text-gray-700'}`}>
                      {position.quantity} shares
                    </div>
                  </div>
                  
                  <div className="text-right">
                    <div className={`text-lg font-bold ${
                      position.unrealized_pnl >= 0 ? 'text-green-400' : 'text-red-400'
                    }`}>
                      {position.unrealized_pnl >= 0 ? '+' : ''}${position.unrealized_pnl || '0.00'}
                    </div>
                    <div className={`text-sm ${
                      position.unrealized_pnl_percentage >= 0 ? 'text-green-400' : 'text-red-400'
                    }`}>
                      {position.unrealized_pnl_percentage >= 0 ? '+' : ''}{position.unrealized_pnl_percentage || '0.00'}%
                    </div>
                  </div>
                </div>

                {/* Price Information */}
                <div className="grid grid-cols-3 gap-4 mb-4">
                  <div className={`text-center p-3 rounded-lg ${
                    isDarkTheme ? 'bg-white/5' : 'bg-gray-100'
                  }`}>
                    <div className={`text-sm ${isDarkTheme ? 'text-gray-400' : 'text-gray-600'}`}>
                      Purchase Price
                    </div>
                    <div className={`font-bold ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
                      ${position.entry_price || position.avg_price}
                    </div>
                  </div>
                  
                  <div className={`text-center p-3 rounded-lg ${
                    isDarkTheme ? 'bg-white/5' : 'bg-gray-100'
                  }`}>
                    <div className={`text-sm ${isDarkTheme ? 'text-gray-400' : 'text-gray-600'}`}>
                      Current Price
                    </div>
                    <div className={`font-bold ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
                      ${position.current_price || 'Loading...'}
                    </div>
                  </div>
                  
                  <div className={`text-center p-3 rounded-lg ${
                    isDarkTheme ? 'bg-white/5' : 'bg-gray-100'
                  }`}>
                    <div className={`text-sm ${isDarkTheme ? 'text-gray-400' : 'text-gray-600'}`}>
                      Avg Cost
                    </div>
                    <div className={`font-bold ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
                      ${position.avg_price}
                    </div>
                  </div>
                </div>

                {/* Stop Loss & Take Profit Indicators */}
                {(position.stop_loss || position.take_profit) && (
                  <div className="flex flex-wrap gap-3 mb-4">
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

                {/* Action Buttons */}
                <div className="position-actions">
                  <button
                    onClick={() => handlePositionAction(position, 'buy')}
                    className="position-btn position-btn-buy"
                  >
                    🟢 Buy More
                  </button>
                  <button
                    onClick={() => handlePositionAction(position, 'add')}
                    className="position-btn position-btn-add"
                  >
                    ➕ Add Shares
                  </button>
                  <button
                    onClick={() => handlePositionAction(position, 'sell')}
                    className="position-btn position-btn-sell"
                  >
                    🔴 Sell Shares
                  </button>
                  <button
                    onClick={() => closePosition(position.id, position.symbol)}
                    className="position-btn bg-gray-600 hover:bg-gray-700 text-white"
                  >
                    ❌ Close All
                  </button>
                </div>

                {/* Position Opened Date */}
                <div className={`text-xs mt-3 ${isDarkTheme ? 'text-gray-400' : 'text-gray-600'}`}>
                  Opened: {new Date(position.opened_at).toLocaleDateString()} at {new Date(position.opened_at).toLocaleTimeString()}
                </div>
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

      {/* Trade Modal */}
      {showTradeModal && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-white/10 backdrop-blur-lg rounded-2xl p-6 w-full max-w-md border border-white/20">
            <h2 className="text-xl font-bold text-white mb-6">
              {tradeAction === 'buy' ? '🟢 Buy More' : tradeAction === 'add' ? '➕ Add Shares' : '🔴 Sell Shares'} {selectedPosition?.symbol}
            </h2>
            
            <div className="space-y-4">
              <div>
                <label className="block text-gray-300 mb-2">Quantity</label>
                <input
                  type="number"
                  placeholder="Number of shares"
                  className="w-full px-4 py-3 bg-white/10 border border-white/20 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  value={tradeForm.quantity}
                  onChange={(e) => setTradeForm({...tradeForm, quantity: e.target.value})}
                />
              </div>
              
              <div>
                <label className="block text-gray-300 mb-2">Price per Share</label>
                <input
                  type="number"
                  step="0.01"
                  placeholder="Price per share"
                  className="w-full px-4 py-3 bg-white/10 border border-white/20 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  value={tradeForm.price}
                  onChange={(e) => setTradeForm({...tradeForm, price: e.target.value})}
                />
              </div>

              {/* Trade Summary */}
              {tradeForm.quantity && tradeForm.price && (
                <div className="p-4 bg-white/10 rounded-lg">
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-300">Total Value:</span>
                    <span className="text-white font-bold">
                      ${(parseInt(tradeForm.quantity || 0) * parseFloat(tradeForm.price || 0)).toFixed(2)}
                    </span>
                  </div>
                  {tradeAction === 'sell' && selectedPosition && (
                    <div className="flex justify-between text-sm mt-2">
                      <span className="text-gray-300">Estimated P&L:</span>
                      <span className={`font-bold ${
                        (parseFloat(tradeForm.price) - selectedPosition.avg_price) >= 0 ? 'text-green-400' : 'text-red-400'
                      }`}>
                        ${((parseFloat(tradeForm.price || 0) - selectedPosition.avg_price) * parseInt(tradeForm.quantity || 0)).toFixed(2)}
                      </span>
                    </div>
                  )}
                </div>
              )}
            </div>
            
            <div className="flex space-x-4 mt-6">
              <button
                onClick={executePositionTrade}
                disabled={!tradeForm.quantity || !tradeForm.price}
                className="flex-1 bg-gradient-to-r from-blue-600 to-purple-600 text-white py-3 rounded-lg font-semibold hover:from-blue-700 hover:to-purple-700 transition-all duration-200 disabled:opacity-50"
              >
                Execute Trade
              </button>
              <button
                onClick={() => setShowTradeModal(false)}
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

export default PortfolioTab;