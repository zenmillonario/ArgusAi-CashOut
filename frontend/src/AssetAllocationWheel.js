import React, { useState, useEffect } from 'react';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from 'recharts';

const AssetAllocationWheel = ({ positions, isDarkTheme }) => {
  const [allocationData, setAllocationData] = useState([]);
  const [totalValue, setTotalValue] = useState(0);

  const sectorColors = {
    'Technology': '#3B82F6',
    'Healthcare': '#10B981', 
    'Finance': '#F59E0B',
    'Consumer': '#EF4444',
    'Energy': '#8B5CF6',
    'Industrial': '#6B7280',
    'Real Estate': '#F97316',
    'Materials': '#14B8A6',
    'Utilities': '#84CC16',
    'Telecom': '#EC4899',
    'Other': '#6366F1'
  };

  // Simplified sector mapping (you can expand this)
  const getSector = (symbol) => {
    const sectorMap = {
      'AAPL': 'Technology', 'MSFT': 'Technology', 'GOOGL': 'Technology', 'NVDA': 'Technology',
      'TSLA': 'Technology', 'META': 'Technology', 'NFLX': 'Technology', 'AMD': 'Technology',
      'JPM': 'Finance', 'BAC': 'Finance', 'WFC': 'Finance', 'GS': 'Finance',
      'JNJ': 'Healthcare', 'PFE': 'Healthcare', 'UNH': 'Healthcare', 'ABBV': 'Healthcare',
      'XOM': 'Energy', 'CVX': 'Energy', 'COP': 'Energy', 'SLB': 'Energy',
      'DIS': 'Consumer', 'AMZN': 'Consumer', 'WMT': 'Consumer', 'HD': 'Consumer'
    };
    return sectorMap[symbol.toUpperCase()] || 'Other';
  };

  useEffect(() => {
    if (!positions || positions.length === 0) {
      setAllocationData([]);
      setTotalValue(0);
      return;
    }

    // Group positions by sector
    const sectorAllocation = {};
    let total = 0;

    positions.forEach(position => {
      const sector = getSector(position.symbol);
      const value = (position.current_price || position.avg_price) * position.quantity;
      
      if (sectorAllocation[sector]) {
        sectorAllocation[sector] += value;
      } else {
        sectorAllocation[sector] = value;
      }
      total += value;
    });

    // Convert to chart data
    const chartData = Object.entries(sectorAllocation).map(([sector, value]) => ({
      name: sector,
      value: value,
      percentage: ((value / total) * 100).toFixed(1),
      color: sectorColors[sector] || sectorColors.Other
    }));

    // Sort by value (largest first)
    chartData.sort((a, b) => b.value - a.value);

    setAllocationData(chartData);
    setTotalValue(total);
  }, [positions]);

  const CustomTooltip = ({ active, payload }) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <div className={`p-3 rounded-lg border shadow-lg ${
          isDarkTheme ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'
        }`}>
          <p className={`font-medium ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
            {data.name}
          </p>
          <p className={`text-sm ${isDarkTheme ? 'text-gray-300' : 'text-gray-600'}`}>
            Value: ${data.value.toLocaleString()}
          </p>
          <p className={`text-sm ${isDarkTheme ? 'text-gray-300' : 'text-gray-600'}`}>
            Allocation: {data.percentage}%
          </p>
        </div>
      );
    }
    return null;
  };

  const CustomLegend = ({ payload }) => {
    return (
      <div className="flex flex-wrap justify-center gap-4 mt-4">
        {payload.map((entry, index) => (
          <div key={index} className="flex items-center space-x-2">
            <div
              className="w-4 h-4 rounded"
              style={{ backgroundColor: entry.color }}
            ></div>
            <span className={`text-sm ${isDarkTheme ? 'text-gray-300' : 'text-gray-700'}`}>
              {entry.value} ({entry.payload.percentage}%)
            </span>
          </div>
        ))}
      </div>
    );
  };

  if (allocationData.length === 0) {
    return (
      <div className={`p-6 rounded-lg border ${
        isDarkTheme ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'
      }`}>
        <h3 className={`text-lg font-bold mb-4 ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
          📊 Asset Allocation
        </h3>
        <div className={`text-center py-12 ${isDarkTheme ? 'text-gray-400' : 'text-gray-600'}`}>
          <div className="text-4xl mb-2">📊</div>
          <p>No positions to display</p>
          <p className="text-sm">Start trading to see your asset allocation</p>
        </div>
      </div>
    );
  }

  return (
    <div className={`p-6 rounded-lg border ${
      isDarkTheme ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'
    }`}>
      <div className="flex items-center justify-between mb-4">
        <h3 className={`text-lg font-bold ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
          📊 Asset Allocation
        </h3>
        <div className={`text-sm ${isDarkTheme ? 'text-gray-400' : 'text-gray-600'}`}>
          Total: ${totalValue.toLocaleString()}
        </div>
      </div>

      <div className="h-80">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={allocationData}
              cx="50%"
              cy="50%"
              outerRadius={80}
              innerRadius={40}
              paddingAngle={2}
              dataKey="value"
            >
              {allocationData.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={entry.color} />
              ))}
            </Pie>
            <Tooltip content={<CustomTooltip />} />
            <Legend content={<CustomLegend />} />
          </PieChart>
        </ResponsiveContainer>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-4">
        <div className={`p-3 rounded ${isDarkTheme ? 'bg-gray-700' : 'bg-gray-100'}`}>
          <div className={`text-lg font-bold ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
            {allocationData.length}
          </div>
          <div className={`text-sm ${isDarkTheme ? 'text-gray-400' : 'text-gray-600'}`}>
            Sectors
          </div>
        </div>

        <div className={`p-3 rounded ${isDarkTheme ? 'bg-gray-700' : 'bg-gray-100'}`}>
          <div className={`text-lg font-bold ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
            {positions.length}
          </div>
          <div className={`text-sm ${isDarkTheme ? 'text-gray-400' : 'text-gray-600'}`}>
            Positions
          </div>
        </div>

        <div className={`p-3 rounded ${isDarkTheme ? 'bg-gray-700' : 'bg-gray-100'}`}>
          <div className={`text-lg font-bold ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
            {allocationData[0]?.name || 'N/A'}
          </div>
          <div className={`text-sm ${isDarkTheme ? 'text-gray-400' : 'text-gray-600'}`}>
            Top Sector
          </div>
        </div>

        <div className={`p-3 rounded ${isDarkTheme ? 'bg-gray-700' : 'bg-gray-100'}`}>
          <div className={`text-lg font-bold ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
            {allocationData[0]?.percentage || 0}%
          </div>
          <div className={`text-sm ${isDarkTheme ? 'text-gray-400' : 'text-gray-600'}`}>
            Concentration
          </div>
        </div>
      </div>
    </div>
  );
};

export default AssetAllocationWheel;