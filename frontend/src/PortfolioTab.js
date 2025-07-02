import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { formatPrice, formatPnL, formatPercentage, formatCurrency } from './utils';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const PortfolioTab = ({ 
  openPositions, 
  userPerformance, 
  closePosition, 
  handlePositionAction,
  isDarkTheme,
  currentUser
}) => {
  const [actionModal, setActionModal] = useState(null);
  const [actionQuantity, setActionQuantity] = useState('');
  const [actionPrice, setActionPrice] = useState('');
  const [tradeHistory, setTradeHistory] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  // Load trade history when component mounts or user changes
  useEffect(() => {
    const loadTradeHistory = async () => {
      if (!currentUser) return;
      
      try {
        setHistoryLoading(true);
        const response = await axios.get(`${API}/trades/${currentUser.id}/history?limit=50`);
        setTradeHistory(response.data);
      } catch (error) {
        console.error('Error loading trade history:', error);
      } finally {
        setHistoryLoading(false);
      }
    };

    loadTradeHistory();
  }, [currentUser]);

  // Reload trade history when positions change (new trades made)
  useEffect(() => {
    if (currentUser && openPositions.length >= 0) {
      // Small delay to ensure backend has processed the trade
      const timeoutId = setTimeout(() => {
        const loadTradeHistory = async () => {
          try {
            const response = await axios.get(`${API}/trades/${currentUser.id}/history?limit=50`);
            setTradeHistory(response.data);
          } catch (error) {
            console.error('Error reloading trade history:', error);
          }
        };
        loadTradeHistory();
      }, 1000);

      return () => clearTimeout(timeoutId);
    }
  }, [openPositions.length, currentUser]);

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
    <div className="h-full flex flex-col overflow-hidden" style={{ maxHeight: 'calc(100vh - 160px)' }}>
      {/* Summary Stats - Compact */}
      <div className={`backdrop-blur-lg rounded-xl border p-4 mb-4 ${
        isDarkTheme 
          ? 'bg-white/5 border-white/10' 
          : 'bg-white/80 border-gray-200'
      }`}>
        <h2 className={`text-xl font-bold mb-3 ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
          📊 Portfolio Summary
        </h2>
        
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="text-center">
            <div className={`text-sm ${isDarkTheme ? 'text-gray-400' : 'text-gray-600'}`}>Total P&L</div>
            <div className={`text-lg font-bold ${
              userPerformance?.total_pnl >= 0 ? 'text-green-500' : 'text-red-500'
            }`}>
              {formatCurrency(userPerformance?.total_pnl || 0)}
            </div>
          </div>
          
          <div className="text-center">
            <div className={`text-sm ${isDarkTheme ? 'text-gray-400' : 'text-gray-600'}`}>Win Rate</div>
            <div className={`text-lg font-bold ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
              {userPerformance?.win_percentage?.toFixed(1) || '0'}%
            </div>
          </div>
          
          <div className="text-center">
            <div className={`text-sm ${isDarkTheme ? 'text-gray-400' : 'text-gray-600'}`}>Trades</div>
            <div className={`text-lg font-bold ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
              {userPerformance?.trades_count || 0}
            </div>
          </div>
          
          <div className="text-center">
            <div className={`text-sm ${isDarkTheme ? 'text-gray-400' : 'text-gray-600'}`}>Positions</div>
            <div className={`text-lg font-bold ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
              {openPositions.length}
            </div>
          </div>
        </div>
      </div>

      {/* Split layout for positions and history */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-2 gap-4 overflow-hidden">
        {/* Open Positions - Compact List */}
        <div className={`backdrop-blur-lg rounded-xl border flex flex-col ${
          isDarkTheme 
            ? 'bg-white/5 border-white/10' 
            : 'bg-white/80 border-gray-200'
        }`}>
          <div className="p-4 border-b border-opacity-20">
            <h3 className={`text-lg font-bold ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
              💼 Open Positions ({openPositions.length})
            </h3>
          </div>
          
          <div className="flex-1 overflow-y-auto p-4 space-y-2">
            {openPositions.length > 0 ? (
              openPositions.map((position, index) => (
                <div key={position.id || index} className={`p-3 rounded-lg border ${
                  isDarkTheme 
                    ? 'bg-white/5 border-white/10' 
                    : 'bg-gray-50 border-gray-200'
                }`}>
                  {/* Compact Position Info */}
                  <div className="grid grid-cols-4 gap-2 text-xs">
                    {/* Symbol & Quantity */}
                    <div>
                      <div className={`font-bold text-sm ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
                        {position.symbol}
                      </div>
                      <div className={isDarkTheme ? 'text-gray-400' : 'text-gray-600'}>
                        {position.quantity} shares
                      </div>
                    </div>
                    
                    {/* Avg Price */}
                    <div>
                      <div className={isDarkTheme ? 'text-gray-400' : 'text-gray-600'}>Avg Price</div>
                      <div className={`font-semibold ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
                        ${formatPrice(position.avg_price)}
                      </div>
                    </div>
                    
                    {/* Current Price */}
                    <div>
                      <div className={isDarkTheme ? 'text-gray-400' : 'text-gray-600'}>Current</div>
                      <div className={`font-semibold ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
                        ${position.current_price ? formatPrice(position.current_price) : 'Loading...'}
                      </div>
                    </div>
                    
                    {/* P&L */}
                    <div>
                      <div className={isDarkTheme ? 'text-gray-400' : 'text-gray-600'}>P&L</div>
                      <div className={`font-bold text-sm ${
                        position.unrealized_pnl >= 0 ? 'text-green-400' : 'text-red-400'
                      }`}>
                        {position.unrealized_pnl >= 0 ? '+' : ''}${formatPnL(position.unrealized_pnl || 0)}
                        {position.current_price && position.avg_price && (
                          <div className="text-xs">
                            ({formatPercentage(position.current_price, position.avg_price)}%)
                          </div>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Compact Action Buttons */}
                  <div className="flex gap-1 mt-2">
                    <button
                      onClick={() => openActionModal(position, 'BUY_MORE')}
                      className="flex-1 px-2 py-1 bg-green-600 text-white rounded text-xs font-medium hover:bg-green-700 transition-colors"
                    >
                      💰 Buy More
                    </button>
                    
                    <button
                      onClick={() => openActionModal(position, 'SELL_PARTIAL')}
                      className="flex-1 px-2 py-1 bg-orange-600 text-white rounded text-xs font-medium hover:bg-orange-700 transition-colors"
                    >
                      📊 Sell Partial
                    </button>
                    
                    <button
                      onClick={() => openActionModal(position, 'SELL_ALL')}
                      className="flex-1 px-2 py-1 bg-red-600 text-white rounded text-xs font-medium hover:bg-red-700 transition-colors"
                    >
                      🔴 Sell All
                    </button>
                  </div>
                </div>
              ))
            ) : (
              <div className="text-center py-8">
                <div className="text-6xl mb-4">📊</div>
                <h4 className={`text-lg font-semibold mb-2 ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
                  No Open Positions
                </h4>
                <p className={isDarkTheme ? 'text-gray-300' : 'text-gray-600'}>
                  Start trading to see your positions here!
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Trade History - Always Visible */}
        <div className={`backdrop-blur-lg rounded-xl border flex flex-col ${
          isDarkTheme 
            ? 'bg-white/5 border-white/10' 
            : 'bg-white/80 border-gray-200'
        }`}>
          <div className="p-4 border-b border-opacity-20">
            <h3 className={`text-lg font-bold ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
              📈 Trade History (Last 50 Trades)
            </h3>
          </div>
          
          <div className="flex-1 overflow-hidden">
            {historyLoading ? (
              <div className="flex items-center justify-center h-full">
                <div className={`text-lg ${isDarkTheme ? 'text-gray-300' : 'text-gray-600'}`}>
                  Loading trade history...
                </div>
              </div>
            ) : tradeHistory.length > 0 ? (
              <div className="h-full flex flex-col">
                {/* Header */}
                <div className={`grid grid-cols-6 gap-2 px-4 py-2 text-xs font-semibold border-b ${
                  isDarkTheme ? 'text-gray-300 border-white/10' : 'text-gray-700 border-gray-200'
                }`}>
                  <div>Date</div>
                  <div>Symbol</div>
                  <div>Action</div>
                  <div>Qty</div>
                  <div>Price</div>
                  <div>P&L</div>
                </div>
                
                {/* Trade List - Scrollable */}
                <div className="flex-1 overflow-y-auto">
                  {tradeHistory.map((trade, index) => (
                    <div 
                      key={trade.id || index} 
                      className={`grid grid-cols-6 gap-2 px-4 py-2 text-xs border-b hover:bg-opacity-50 transition-colors ${
                        isDarkTheme ? 'hover:bg-white/5 border-white/5' : 'hover:bg-gray-100 border-gray-100'
                      }`}
                    >
                      {/* Date */}
                      <div className={isDarkTheme ? 'text-gray-300' : 'text-gray-700'}>
                        {new Date(trade.timestamp).toLocaleDateString('en-US', {
                          month: 'short',
                          day: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit'
                        })}
                      </div>
                      
                      {/* Symbol */}
                      <div className={`font-semibold ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
                        {trade.symbol}
                      </div>
                      
                      {/* Action */}
                      <div className={`font-medium ${
                        trade.action === 'BUY' 
                          ? 'text-green-500' 
                          : 'text-red-500'
                      }`}>
                        {trade.action}
                      </div>
                      
                      {/* Quantity */}
                      <div className={isDarkTheme ? 'text-gray-300' : 'text-gray-700'}>
                        {trade.quantity.toLocaleString()}
                      </div>
                      
                      {/* Price */}
                      <div className={isDarkTheme ? 'text-gray-300' : 'text-gray-700'}>
                        ${trade.formatted_price || formatPrice(trade.price)}
                      </div>
                      
                      {/* P&L */}
                      <div className={
                        trade.profit_loss === null 
                          ? (isDarkTheme ? 'text-gray-500' : 'text-gray-400')
                          : trade.profit_loss >= 0 
                            ? 'text-green-500 font-medium' 
                            : 'text-red-500 font-medium'
                      }>
                        {trade.profit_loss === null 
                          ? '—' 
                          : `${trade.profit_loss >= 0 ? '+' : ''}${trade.formatted_profit_loss || formatPnL(trade.profit_loss)}`
                        }
                      </div>
                    </div>
                  ))}
                </div>
                
                {/* Summary */}
                <div className={`px-4 py-2 border-t text-xs ${
                  isDarkTheme ? 'border-white/10 text-gray-300' : 'border-gray-200 text-gray-600'
                }`}>
                  <div className="flex justify-between items-center">
                    <span>Showing last {tradeHistory.length} trades</span>
                    <div className="flex items-center space-x-4">
                      <span>Total: {tradeHistory.length}</span>
                      <span>Closed: {tradeHistory.filter(t => t.is_closed).length}</span>
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="flex items-center justify-center h-full">
                <div className="text-center">
                  <div className="text-4xl mb-3">📊</div>
                  <h4 className={`text-lg font-semibold mb-2 ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
                    No Trades Yet
                  </h4>
                  <p className={isDarkTheme ? 'text-gray-300' : 'text-gray-600'}>
                    Start trading to see your history here!
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

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
                Current Position: {actionModal.position.quantity} shares @ ${formatPrice(actionModal.position.avg_price)}
              </div>
              <div className={`text-sm ${isDarkTheme ? 'text-gray-300' : 'text-gray-600'}`}>
                Current Price: ${actionModal.position.current_price ? formatPrice(actionModal.position.current_price) : 'Loading...'}
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
                  step="0.00000001"
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
                      <span>${formatPrice(parseFloat(actionPrice))}</span>
                    </div>
                    <div className="flex justify-between font-semibold border-t pt-1">
                      <span>Total Value:</span>
                      <span>${formatPrice(parseFloat(actionQuantity) * parseFloat(actionPrice))}</span>
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