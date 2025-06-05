import React, { useState } from 'react';

const PortfolioTab = ({ 
  openPositions, 
  userPerformance, 
  closePosition, 
  handlePositionAction,
  isDarkTheme 
}) => {
  const totalUnrealizedPnL = openPositions.reduce((sum, pos) => sum + (pos.unrealized_pnl || 0), 0);
  const [actionModal, setActionModal] = useState(null);
  const [actionQuantity, setActionQuantity] = useState('');
  const [actionPrice, setActionPrice] = useState('');

  const openActionModal = (position, action) => {
    setActionModal({ position, action });
    setActionQuantity('');
    setActionPrice(position.current_price || '');
  };

  const executeAction = async () => {
    if (!actionModal) return;
    
    const { position, action } = actionModal;
    let quantity = null;
    let price = parseFloat(actionPrice) || null;
    
    if (action === 'BUY_MORE') {
      quantity = parseInt(actionQuantity);
      if (!quantity || quantity <= 0) {
        alert('Please enter a valid quantity');
        return;
      }
    } else if (action === 'SELL_PARTIAL') {
      quantity = parseInt(actionQuantity);
      if (!quantity || quantity <= 0 || quantity >= position.quantity) {
        alert('Please enter a valid quantity (less than current position)');
        return;
      }
    }
    
    await handlePositionAction(position.id, action, quantity, price);
    setActionModal(null);
  };

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
              <div key={position.id} className={`p-4 rounded-lg border ${
                isDarkTheme ? 'bg-white/5 border-white/10' : 'bg-gray-50 border-gray-200'
              }`}>
                {/* Position Header */}
                <div className="flex justify-between items-start mb-3">
                  <div className="flex items-center space-x-4">
                    <div className={`font-bold text-xl ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
                      {position.symbol}
                    </div>
                    <div className={isDarkTheme ? 'text-gray-300' : 'text-gray-700'}>
                      {position.quantity} shares
                    </div>
                  </div>
                  
                  <div className="text-right">
                    <div className={`text-sm ${isDarkTheme ? 'text-gray-400' : 'text-gray-600'}`}>
                      Opened: {new Date(position.opened_at).toLocaleDateString()}
                    </div>
                  </div>
                </div>

                {/* Price Information */}
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4">
                  <div className={`p-3 rounded ${isDarkTheme ? 'bg-white/5' : 'bg-white'}`}>
                    <div className={`text-xs ${isDarkTheme ? 'text-gray-400' : 'text-gray-600'}`}>
                      Purchase Price
                    </div>
                    <div className={`font-semibold ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
                      ${position.avg_price.toFixed(2)}
                    </div>
                  </div>
                  
                  <div className={`p-3 rounded ${isDarkTheme ? 'bg-white/5' : 'bg-white'}`}>
                    <div className={`text-xs ${isDarkTheme ? 'text-gray-400' : 'text-gray-600'}`}>
                      Current Price
                    </div>
                    <div className={`font-semibold ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
                      ${position.current_price ? position.current_price.toFixed(2) : 'Loading...'}
                    </div>
                  </div>
                  
                  <div className={`p-3 rounded ${isDarkTheme ? 'bg-white/5' : 'bg-white'}`}>
                    <div className={`text-xs ${isDarkTheme ? 'text-gray-400' : 'text-gray-600'}`}>
                      Total Value
                    </div>
                    <div className={`font-semibold ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
                      ${position.current_price ? (position.current_price * position.quantity).toFixed(2) : 'Loading...'}
                    </div>
                  </div>
                  
                  <div className={`p-3 rounded ${position.unrealized_pnl >= 0 ? 'bg-green-500/10' : 'bg-red-500/10'}`}>
                    <div className={`text-xs ${isDarkTheme ? 'text-gray-400' : 'text-gray-600'}`}>
                      Profit/Loss
                    </div>
                    <div className={`font-bold ${
                      position.unrealized_pnl >= 0 ? 'text-green-400' : 'text-red-400'
                    }`}>
                      {position.unrealized_pnl >= 0 ? '+' : ''}${position.unrealized_pnl ? position.unrealized_pnl.toFixed(2) : '0.00'}
                      {position.current_price && position.avg_price && (
                        <div className="text-xs">
                          ({((position.current_price - position.avg_price) / position.avg_price * 100).toFixed(2)}%)
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                {/* Action Buttons */}
                <div className="flex flex-wrap gap-2 mb-3">
                  <button
                    onClick={() => openActionModal(position, 'BUY_MORE')}
                    className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors text-sm font-medium"
                  >
                    💰 Buy More
                  </button>
                  
                  <button
                    onClick={() => openActionModal(position, 'SELL_PARTIAL')}
                    className="px-4 py-2 bg-orange-600 text-white rounded-lg hover:bg-orange-700 transition-colors text-sm font-medium"
                  >
                    📊 Sell Partial
                  </button>
                  
                  <button
                    onClick={() => openActionModal(position, 'SELL_ALL')}
                    className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors text-sm font-medium"
                  >
                    🔴 Sell All
                  </button>
                  
                  <button
                    onClick={() => closePosition(position.id, position.symbol)}
                    className="px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition-colors text-sm font-medium"
                  >
                    ❌ Close Position
                  </button>
                </div>
                
                {/* Stop Loss & Take Profit Indicators */}
                {(position.stop_loss || position.take_profit) && (
                  <div className="flex flex-wrap gap-3">
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

      {/* Action Modal */}
      {actionModal && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className={`backdrop-blur-lg rounded-2xl p-6 w-full max-w-md border ${
            isDarkTheme 
              ? 'bg-white/10 border-white/20' 
              : 'bg-white/90 border-gray-200'
          }`}>
            <h3 className={`text-xl font-bold mb-4 ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
              {actionModal.action === 'BUY_MORE' && '💰 Buy More Shares'}
              {actionModal.action === 'SELL_PARTIAL' && '📊 Sell Partial Position'}
              {actionModal.action === 'SELL_ALL' && '🔴 Sell All Shares'}
            </h3>
            
            <div className={`mb-4 p-3 rounded ${isDarkTheme ? 'bg-white/5' : 'bg-gray-50'}`}>
              <div className={`font-semibold ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
                {actionModal.position.symbol}
              </div>
              <div className={`text-sm ${isDarkTheme ? 'text-gray-300' : 'text-gray-600'}`}>
                Current Position: {actionModal.position.quantity} shares @ ${actionModal.position.avg_price.toFixed(2)}
              </div>
              <div className={`text-sm ${isDarkTheme ? 'text-gray-300' : 'text-gray-600'}`}>
                Current Price: ${actionModal.position.current_price ? actionModal.position.current_price.toFixed(2) : 'Loading...'}
              </div>
            </div>

            <form onSubmit={(e) => { e.preventDefault(); executeAction(); }} className="space-y-4">
              {(actionModal.action === 'BUY_MORE' || actionModal.action === 'SELL_PARTIAL') && (
                <div>
                  <label className={`block mb-2 ${isDarkTheme ? 'text-gray-300' : 'text-gray-700'}`}>
                    Quantity
                  </label>
                  <input
                    type="number"
                    min="1"
                    max={actionModal.action === 'SELL_PARTIAL' ? actionModal.position.quantity - 1 : undefined}
                    className={`w-full px-4 py-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                      isDarkTheme 
                        ? 'bg-white/10 border border-white/20 text-white placeholder-gray-400' 
                        : 'bg-white border border-gray-200 text-gray-900 placeholder-gray-500'
                    }`}
                    value={actionQuantity}
                    onChange={(e) => setActionQuantity(e.target.value)}
                    placeholder={actionModal.action === 'BUY_MORE' ? 'Shares to buy' : 'Shares to sell'}
                    required
                  />
                </div>
              )}
              
              <div>
                <label className={`block mb-2 ${isDarkTheme ? 'text-gray-300' : 'text-gray-700'}`}>
                  Price per Share
                </label>
                <input
                  type="number"
                  step="0.01"
                  className={`w-full px-4 py-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                    isDarkTheme 
                      ? 'bg-white/10 border border-white/20 text-white placeholder-gray-400' 
                      : 'bg-white border border-gray-200 text-gray-900 placeholder-gray-500'
                  }`}
                  value={actionPrice}
                  onChange={(e) => setActionPrice(e.target.value)}
                  placeholder="Current market price"
                />
              </div>

              {/* Order Summary */}
              {actionQuantity && actionPrice && (
                <div className={`p-3 rounded ${isDarkTheme ? 'bg-white/5' : 'bg-gray-50'}`}>
                  <div className={`font-semibold mb-2 ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
                    Order Summary
                  </div>
                  <div className={`text-sm space-y-1 ${isDarkTheme ? 'text-gray-300' : 'text-gray-700'}`}>
                    <div className="flex justify-between">
                      <span>Shares:</span>
                      <span>{actionQuantity}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Price per Share:</span>
                      <span>${parseFloat(actionPrice).toFixed(2)}</span>
                    </div>
                    <div className="flex justify-between font-semibold border-t pt-1">
                      <span>Total Value:</span>
                      <span>${(parseFloat(actionQuantity) * parseFloat(actionPrice)).toFixed(2)}</span>
                    </div>
                  </div>
                </div>
              )}
              
              <div className="flex space-x-4">
                <button
                  type="submit"
                  className={`flex-1 py-3 rounded-lg font-semibold transition-colors ${
                    actionModal.action === 'BUY_MORE' 
                      ? 'bg-green-600 hover:bg-green-700 text-white'
                      : 'bg-red-600 hover:bg-red-700 text-white'
                  }`}
                >
                  {actionModal.action === 'BUY_MORE' && 'Buy More'}
                  {actionModal.action === 'SELL_PARTIAL' && 'Sell Partial'}
                  {actionModal.action === 'SELL_ALL' && 'Sell All'}
                </button>
                
                <button
                  type="button"
                  onClick={() => setActionModal(null)}
                  className="flex-1 bg-gray-600 text-white py-3 rounded-lg font-semibold hover:bg-gray-700 transition-colors"
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default PortfolioTab;