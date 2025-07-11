import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { formatPrice } from './utils';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';
const API = BACKEND_URL ? `${BACKEND_URL}/api` : '/api';

const FavoritesTab = ({ 
  favorites, 
  addToFavorites, 
  removeFromFavorites, 
  isDarkTheme 
}) => {
  const [newFavorite, setNewFavorite] = useState('');
  const [stockPrices, setStockPrices] = useState({});
  const [loading, setLoading] = useState(false);

  // Fetch real stock prices for favorites
  const fetchStockPrice = async (symbol) => {
    try {
      const response = await axios.get(`${API}/stock/${symbol}`);
      return response.data.price;
    } catch (error) {
      console.error(`Error fetching price for ${symbol}:`, error);
      return null;
    }
  };

  // Load prices for all favorites
  useEffect(() => {
    const loadPrices = async () => {
      if (favorites.length === 0) return;
      
      setLoading(true);
      const prices = {};
      
      for (const symbol of favorites) {
        const price = await fetchStockPrice(symbol);
        if (price) {
          prices[symbol] = price;
        }
      }
      
      setStockPrices(prices);
      setLoading(false);
    };

    loadPrices();
  }, [favorites]);

  const handleAddFavorite = (e) => {
    e.preventDefault();
    if (newFavorite.trim()) {
      addToFavorites(newFavorite.trim());
      setNewFavorite('');
    }
  };

  const refreshPrice = async (symbol) => {
    const price = await fetchStockPrice(symbol);
    if (price) {
      setStockPrices(prev => ({
        ...prev,
        [symbol]: price
      }));
    }
  };

  return (
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

      {/* Favorites List */}
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
                      {loading ? (
                        'Loading...'
                      ) : stockPrices[symbol] ? (
                        <>
                          ${formatPrice(stockPrices[symbol])}
                          <button
                            onClick={() => refreshPrice(symbol)}
                            className="ml-2 text-xs hover:text-blue-500"
                            title="Refresh price"
                          >
                            🔄
                          </button>
                        </>
                      ) : (
                        'Price unavailable'
                      )}
                    </div>
                  </div>
                  <button
                    onClick={() => removeFromFavorites(symbol)}
                    className="text-red-400 hover:text-red-300 transition-colors"
                    title="Remove from favorites"
                  >
                    🗑️
                  </button>
                </div>
                
                {/* Quick Actions */}
                <div className="mt-3 flex space-x-2">
                  <button
                    onClick={() => {
                      // Copy to clipboard for easy pasting in chat
                      navigator.clipboard.writeText(`$${symbol}`);
                      alert(`$${symbol} copied to clipboard!`);
                    }}
                    className="flex-1 px-3 py-1 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 transition-colors"
                  >
                    Copy to Chat
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
  );
};

export default FavoritesTab;
