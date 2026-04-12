// Merged Practice & Favorites Tab with Compact Trade Log
// Replace your existing tabs with this combined version

import React, { useState } from 'react';

const PracticeFavoritesTab = ({ 
  favorites, 
  addToFavorites, 
  removeFromFavorites,
  userTrades,
  submitTrade,
  tradeForm,
  setTradeForm,
  isDarkTheme 
}) => {
  const [activeSubTab, setActiveSubTab] = useState('practice');
  const [newFavorite, setNewFavorite] = useState('');

  const handleAddFavorite = (e) => {
    e.preventDefault();
    if (newFavorite.trim()) {
      addToFavorites(newFavorite.trim());
      setNewFavorite('');
    }
  };

  // Mock stock prices for favorites
  const getMockPrice = (symbol) => {
    const prices = {
      'TSLA': 275.50,
      'AAPL': 188.20,
      'MSFT': 420.50,
      'NVDA': 875.30,
      'GOOGL': 142.80,
      'AMZN': 155.90,
      'META': 485.60,
    };
    return prices[symbol] || 100.0;
  };

  return (
    <div className="space-y-6">
      {/* Sub-Tab Navigation */}
      <div className="flex space-x-2">
        <button
          onClick={() => setActiveSubTab('practice')}
          className={`px-6 py-3 rounded-lg font-semibold transition-colors ${
            activeSubTab === 'practice'
              ? 'bg-gradient-to-r from-green-600 to-blue-600 text-white'
              : isDarkTheme 
                ? 'bg-white/10 text-gray-300 hover:bg-white/20' 
                : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
          }`}
        >
          📈 Paper Trading
        </button>
        <button
          onClick={() => setActiveSubTab('favorites')}
          className={`px-6 py-3 rounded-lg font-semibold transition-colors ${
            activeSubTab === 'favorites'
              ? 'bg-gradient-to-r from-yellow-600 to-orange-600 text-white'
              : isDarkTheme 
                ? 'bg-white/10 text-gray-300 hover:bg-white/20' 
                : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
          }`}
        >
          ⭐ Favorites ({favorites.length})
        </button>
      </div>

      {/* Practice Sub-Tab */}
      {activeSubTab === 'practice' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Enhanced Trade Form */}
          <div className={`lg:col-span-2 backdrop-blur-lg rounded-2xl border p-6 ${
            isDarkTheme 
              ? 'bg-white/5 border-white/10' 
              : 'bg-white/80 border-gray-200'
          }`}>
            <h2 className={`text-2xl font-bold mb-6 ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
              📈 Enhanced Paper Trading
            </h2>
            <form onSubmit={submitTrade} className="space-y-4">
              <div>
                <label className={`block mb-2 font-semibold ${isDarkTheme ? 'text-gray-300' : 'text-gray-700'}`}>
                  Stock Symbol
                </label>
                <input
                  type="text"
                  placeholder="TSLA"
                  className={`w-full px-4 py-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                    isDarkTheme 
                      ? 'bg-white/10 border border-white/20 text-white placeholder-gray-400' 
                      : 'bg-white border border-gray-200 text-gray-900 placeholder-gray-500'
                  }`}
                  value={tradeForm.symbol}
                  onChange={(e) => setTradeForm({...tradeForm, symbol: e.target.value.toUpperCase()})}
                  required
                />
              </div>
              
              <div>
                <label className={`block mb-2 font-semibold ${isDarkTheme ? 'text-gray-300' : 'text-gray-700'}`}>
                  Action
                </label>
                <select
                  className={`w-full px-4 py-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                    isDarkTheme 
                      ? 'bg-white/10 border border-white/20 text-white' 
                      : 'bg-white border border-gray-200 text-gray-900'
                  }`}
                  value={tradeForm.action}
                  onChange={(e) => setTradeForm({...tradeForm, action: e.target.value})}
                >
                  <option value="BUY">Buy</option>
                  <option value="SELL">Sell</option>
                </select>
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className={`block mb-2 font-semibold ${isDarkTheme ? 'text-gray-300' : 'text-gray-700'}`}>
                    Quantity
                  </label>
                  <input
                    type="number"
                    placeholder="100"
                    className={`w-full px-4 py-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                      isDarkTheme 
                        ? 'bg-white/10 border border-white/20 text-white placeholder-gray-400' 
                        : 'bg-white border border-gray-200 text-gray-900 placeholder-gray-500'
                    }`}
                    value={tradeForm.quantity}
                    onChange={(e) => setTradeForm({...tradeForm, quantity: e.target.value})}
                    required
                  />
                </div>
                
                <div>
                  <label className={`block mb-2 font-semibold ${isDarkTheme ? 'text-gray-300' : 'text-gray-700'}`}>
                    Price
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    placeholder="250.00"
                    className={`w-full px-4 py-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                      isDarkTheme 
                        ? 'bg-white/10 border border-white/20 text-white placeholder-gray-400' 
                        : 'bg-white border border-gray-200 text-gray-900 placeholder-gray-500'
                    }`}
                    value={tradeForm.price}
                    onChange={(e) => setTradeForm({...tradeForm, price: e.target.value})}
                    required
                  />
                </div>
              </div>
              
              {/* Stop Loss & Take Profit */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className={`block mb-2 font-semibold ${isDarkTheme ? 'text-gray-300' : 'text-gray-700'}`}>
                    Stop Loss (Optional)
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    placeholder="Auto-sell if price drops"
                    className={`w-full px-4 py-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-red-500 ${
                      isDarkTheme 
                        ? 'bg-white/10 border border-white/20 text-white placeholder-gray-400' 
                        : 'bg-white border border-gray-200 text-gray-900 placeholder-gray-500'
                    }`}
                    value={tradeForm.stop_loss}
                    onChange={(e) => setTradeForm({...tradeForm, stop_loss: e.target.value})}
                  />
                </div>
                
                <div>
                  <label className={`block mb-2 font-semibold ${isDarkTheme ? 'text-gray-300' : 'text-gray-700'}`}>
                    Take Profit (Optional)
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    placeholder="Auto-sell when profit reached"
                    className={`w-full px-4 py-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500 ${
                      isDarkTheme 
                        ? 'bg-white/10 border border-white/20 text-white placeholder-gray-400' 
                        : 'bg-white border border-gray-200 text-gray-900 placeholder-gray-500'
                    }`}
                    value={tradeForm.take_profit}
                    onChange={(e) => setTradeForm({...tradeForm, take_profit: e.target.value})}
                  />
                </div>
              </div>
              
              <div>
                <label className={`block mb-2 font-semibold ${isDarkTheme ? 'text-gray-300' : 'text-gray-700'}`}>
                  Notes (Optional)
                </label>
                <textarea
                  placeholder="Trade notes and strategy..."
                  className={`w-full px-4 py-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                    isDarkTheme 
                      ? 'bg-white/10 border border-white/20 text-white placeholder-gray-400' 
                      : 'bg-white border border-gray-200 text-gray-900 placeholder-gray-500'
                  }`}
                  value={tradeForm.notes}
                  onChange={(e) => setTradeForm({...tradeForm, notes: e.target.value})}
                  rows="3"
                />
              </div>
              
              <button
                type="submit"
                className="w-full bg-gradient-to-r from-green-600 to-blue-600 text-white py-3 rounded-lg font-semibold hover:from-green-700 hover:to-blue-700 transition-all duration-200"
              >
                🎯 Record Trade
              </button>
            </form>
          </div>

          {/* COMPACT Trade Log */}
          <div className={`backdrop-blur-lg rounded-2xl border p-4 ${
            isDarkTheme 
              ? 'bg-white/5 border-white/10' 
              : 'bg-white/80 border-gray-200'
          }`}>
            <h3 className={`text-lg font-bold mb-4 ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
              📋 Trade Log
            </h3>
            <div className="space-y-2 max-h-96 overflow-y-auto">
              {userTrades.slice(0, 20).map((trade) => (
                <div key={trade.id} className={`trade-log-compact ${
                  trade.action === 'BUY' ? 'trade-log-buy' : 'trade-log-sell'
                }`}>
                  <div className="flex justify-between items-center">
                    <div className="flex items-center space-x-2">
                      <span className={`font-bold text-xs ${
                        trade.action === 'BUY' ? 'text-green-400' : 'text-red-400'
                      }`}>
                        {trade.action}
                      </span>
                      <span className={`font-semibold text-xs ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
                        {trade.symbol}
                      </span>
                      <span className={`text-xs ${isDarkTheme ? 'text-gray-300' : 'text-gray-600'}`}>
                        {trade.quantity}@${trade.price}
                      </span>
                    </div>
                    <div className="text-xs text-gray-400">
                      {new Date(trade.timestamp).toLocaleDateString()}
                    </div>
                  </div>
                  {trade.notes && (
                    <div className={`text-xs mt-1 ${isDarkTheme ? 'text-gray-400' : 'text-gray-600'}`}>
                      {trade.notes.substring(0, 50)}...
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Favorites Sub-Tab */}
      {activeSubTab === 'favorites' && (
        <div className="space-y-6">
          {/* Add New Favorite */}
          <div className={`backdrop-blur-lg rounded-2xl border p-6 ${
            isDarkTheme 
              ? 'bg-white/5 border-white/10' 
              : 'bg-white/80 border-gray-200'
          }`}>
            <h2 className={`text-2xl font-bold mb-6 ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
              ⭐ Add Stock to Favorites
            </h2>
            
            <form onSubmit={handleAddFavorite} className="flex space-x-4">
              <input
                type="text"
                placeholder="Enter stock symbol (e.g., TSLA)"
                className={`flex-1 px-4 py-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                  isDarkTheme 
                    ? 'bg-white/10 border border-white/20 text-white placeholder-gray-400' 
                    : 'bg-white border border-gray-200 text-gray-900 placeholder-gray-500'
                }`}
                value={newFavorite}
                onChange={(e) => setNewFavorite(e.target.value.toUpperCase())}
              />
              <button
                type="submit"
                className="px-6 py-3 bg-gradient-to-r from-yellow-600 to-orange-600 text-white rounded-lg font-semibold hover:from-yellow-700 hover:to-orange-700 transition-all duration-200"
              >
                Add Favorite
              </button>
            </form>
          </div>

          {/* Favorites Grid */}
          <div className={`backdrop-blur-lg rounded-2xl border p-6 ${
            isDarkTheme 
              ? 'bg-white/5 border-white/10' 
              : 'bg-white/80 border-gray-200'
          }`}>
            <h3 className={`text-xl font-bold mb-6 ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
              📋 Your Favorite Stocks
            </h3>
            
            {favorites.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {favorites.map((symbol) => (
                  <div key={symbol} className={`p-4 rounded-lg border ${
                    isDarkTheme 
                      ? 'bg-white/5 border-white/10' 
                      : 'bg-gray-50 border-gray-200'
                  }`}>
                    <div className="flex justify-between items-center">
                      <div>
                        <div className={`font-bold text-lg ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
                          ${symbol}
                        </div>
                        <div className={`text-sm ${isDarkTheme ? 'text-gray-300' : 'text-gray-600'}`}>
                          ${getMockPrice(symbol).toFixed(2)}
                        </div>
                      </div>
                      <button
                        onClick={() => removeFromFavorites(symbol)}
                        className="text-red-400 hover:text-red-300 transition-colors p-2"
                        title="Remove from favorites"
                      >
                        🗑️
                      </button>
                    </div>
                    
                    {/* Quick Actions */}
                    <div className="mt-3 flex space-x-2">
                      <button
                        onClick={() => {
                          navigator.clipboard.writeText(`$${symbol}`);
                          alert(`$${symbol} copied to clipboard!`);
                        }}
                        className="flex-1 px-3 py-1 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 transition-colors"
                      >
                        📋 Copy
                      </button>
                      <button
                        onClick={() => setTradeForm({...tradeForm, symbol: symbol})}
                        className="flex-1 px-3 py-1 bg-green-600 text-white text-sm rounded hover:bg-green-700 transition-colors"
                      >
                        📈 Trade
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-8">
                <div className="text-6xl mb-4">⭐</div>
                <h4 className={`text-lg font-semibold mb-2 ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
                  No Favorites Yet
                </h4>
                <p className={isDarkTheme ? 'text-gray-300' : 'text-gray-600'}>
                  Add stock symbols to keep track of your favorites!
                </p>
              </div>
            )}
          </div>

          {/* Quick Add Popular Stocks */}
          <div className={`backdrop-blur-lg rounded-2xl border p-6 ${
            isDarkTheme 
              ? 'bg-white/5 border-white/10' 
              : 'bg-white/80 border-gray-200'
          }`}>
            <h3 className={`text-lg font-bold mb-4 ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
              🔥 Popular Stocks
            </h3>
            
            <div className="flex flex-wrap gap-2">
              {['TSLA', 'AAPL', 'MSFT', 'NVDA', 'GOOGL', 'AMZN', 'META', 'NFLX'].map(symbol => (
                <button
                  key={symbol}
                  onClick={() => addToFavorites(symbol)}
                  disabled={favorites.includes(symbol)}
                  className={`px-3 py-2 rounded-lg text-sm font-semibold transition-colors ${
                    favorites.includes(symbol)
                      ? 'bg-gray-400 text-gray-200 cursor-not-allowed'
                      : 'bg-gradient-to-r from-purple-600 to-blue-600 text-white hover:from-purple-700 hover:to-blue-700'
                  }`}
                >
                  {favorites.includes(symbol) ? '✓' : '+'} ${symbol}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default PracticeFavoritesTab;