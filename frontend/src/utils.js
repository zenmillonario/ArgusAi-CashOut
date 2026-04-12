// Utility functions for formatting prices and P&L

export const formatPrice = (price) => {
  if (price === null || price === undefined) {
    return "0.00";
  }
  
  const numPrice = parseFloat(price);
  
  if (numPrice === 0) {
    return "0.00";
  } else if (numPrice < 0.01) {
    // For very small prices, show up to 8 decimal places (remove trailing zeros)
    return numPrice.toFixed(8).replace(/\.?0+$/, '');
  } else if (numPrice < 1) {
    // For prices under $1, show up to 4 decimal places
    return numPrice.toFixed(4).replace(/\.?0+$/, '');
  } else {
    // For regular prices, show 2 decimal places
    return numPrice.toFixed(2);
  }
};

export const formatPnL = (pnl) => {
  if (pnl === null || pnl === undefined) {
    return "0.00";
  }
  
  const numPnL = parseFloat(pnl);
  
  if (Math.abs(numPnL) < 0.01) {
    // For very small P&L, show more precision
    return numPnL.toFixed(6).replace(/\.?0+$/, '');
  } else {
    // For regular P&L, show 2 decimal places
    return numPnL.toFixed(2);
  }
};

export const formatPercentage = (current, original) => {
  if (!current || !original || original === 0) {
    return "0.00";
  }
  
  const percentage = ((current - original) / original) * 100;
  
  if (Math.abs(percentage) < 0.01) {
    return percentage.toFixed(4).replace(/\.?0+$/, '');
  } else {
    return percentage.toFixed(2);
  }
};

export const formatCurrency = (amount) => {
  if (amount === null || amount === undefined) {
    return "$0.00";
  }
  
  const numAmount = parseFloat(amount);
  return `$${formatPnL(numAmount)}`;
};