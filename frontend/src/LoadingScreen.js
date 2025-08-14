import React, { useState, useEffect } from 'react';

const LoadingScreen = ({ onComplete, isDarkTheme }) => {
  const [isVisible, setIsVisible] = useState(true);
  const [dots, setDots] = useState('');

  useEffect(() => {
    // Matrix code rain animation duration: 4 seconds
    const timeout = setTimeout(() => {
      setIsVisible(false);
      setTimeout(() => {
        onComplete();
      }, 500);
    }, 4000);

    // Animated dots for loading effect
    const dotInterval = setInterval(() => {
      setDots(prev => prev.length >= 3 ? '' : prev + '.');
    }, 500);

    return () => {
      clearTimeout(timeout);
      clearInterval(dotInterval);
    };
  }, [onComplete]);

  if (!isVisible) {
    return null;
  }

  // Matrix code characters
  const matrixChars = '01アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン';

  // Generate matrix columns
  const generateMatrixColumns = () => {
    const columns = [];
    const columnCount = Math.floor(window.innerWidth / 20);
    
    for (let i = 0; i < columnCount; i++) {
      const column = [];
      const columnHeight = Math.floor(Math.random() * 20) + 10;
      
      for (let j = 0; j < columnHeight; j++) {
        column.push({
          char: matrixChars[Math.floor(Math.random() * matrixChars.length)],
          opacity: Math.random() * 0.8 + 0.2,
          delay: Math.random() * 2
        });
      }
      
      columns.push({
        chars: column,
        left: i * 20,
        animationDelay: Math.random() * 4
      });
    }
    
    return columns;
  };

  const [matrixColumns] = useState(() => generateMatrixColumns());

  return (
    <div 
      className={`fixed inset-0 z-50 flex items-center justify-center transition-opacity duration-500 overflow-hidden ${
        isVisible ? 'opacity-100' : 'opacity-0'
      } ${isDarkTheme ? 'bg-black' : 'bg-gray-900'}`}
    >
      {/* Matrix Code Rain Background */}
      <div className="absolute inset-0">
        {matrixColumns.map((column, columnIndex) => (
          <div
            key={columnIndex}
            className="absolute top-0 flex flex-col text-green-400 font-mono text-sm leading-tight"
            style={{
              left: `${column.left}px`,
              animationDelay: `${column.animationDelay}s`,
              animation: 'matrixFall 4s linear infinite'
            }}
          >
            {column.chars.map((item, charIndex) => (
              <span
                key={charIndex}
                className="block"
                style={{
                  opacity: item.opacity,
                  animationDelay: `${item.delay}s`,
                  color: charIndex === 0 ? '#00ff00' : `rgba(0, 255, 0, ${item.opacity})`
                }}
              >
                {item.char}
              </span>
            ))}
          </div>
        ))}
      </div>

      {/* Main Logo Container with Neon Border */}
      <div className="relative z-10 flex flex-col items-center justify-center">
        {/* Neon Border Container */}
        <div className="relative p-8">
          {/* Animated Neon Border */}
          <div 
            className="absolute inset-0 rounded-full border-4 border-transparent"
            style={{
              background: 'linear-gradient(45deg, #00ff00, #0088ff, #ff00ff, #ffff00, #00ff00) border-box',
              WebkitMask: 'linear-gradient(#fff 0 0) padding-box, linear-gradient(#fff 0 0)',
              WebkitMaskComposite: 'subtract',
              mask: 'linear-gradient(#fff 0 0) padding-box, linear-gradient(#fff 0 0)',
              maskComposite: 'subtract',
              animation: 'neonRotate 2s linear infinite'
            }}
          />
          
          {/* Inner Glow */}
          <div className="absolute inset-2 rounded-full bg-gradient-to-r from-green-400/20 to-blue-400/20 blur-lg" />
          
          {/* Logo Container */}
          <div className="relative w-32 h-32 flex items-center justify-center bg-black/80 rounded-full backdrop-blur-sm">
            {/* Logo Text - Replace with your actual logo */}
            <div className="text-center">
              <div className="text-3xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-green-400 to-blue-400 mb-1">
                💰
              </div>
              <div className="text-sm font-bold text-green-400 tracking-wider">
                CashoutAI
              </div>
            </div>
          </div>
        </div>

        {/* Loading Text */}
        <div className="mt-8 text-center">
          <div className="text-lg font-semibold text-green-400 mb-2">
            Initializing Trading Platform{dots}
          </div>
          <div className="text-sm text-green-300/70">
            Connecting to market data streams
          </div>
        </div>
      </div>

      {/* CSS Animations */}
      <style jsx>{`
        @keyframes matrixFall {
          0% { transform: translateY(-100vh); }
          100% { transform: translateY(100vh); }
        }
        
        @keyframes neonRotate {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
        
        @keyframes pulse {
          0%, 100% { opacity: 0.4; }
          50% { opacity: 1; }
        }
      `}</style>
    </div>
  );
};

export default LoadingScreen;