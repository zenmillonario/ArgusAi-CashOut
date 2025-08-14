import React, { useState, useEffect } from 'react';

const LoadingScreen = ({ onComplete, isDarkTheme }) => {
  const [isVisible, setIsVisible] = useState(true);
  const [dots, setDots] = useState('');

  // Matrix code characters
  const matrixChars = '01アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン';

  // Generate matrix columns - bidirectional (top to bottom and bottom to top)
  const generateMatrixColumns = () => {
    const topToBottomColumns = [];
    const bottomToTopColumns = [];
    const columnCount = Math.floor(window.innerWidth / 20);
    
    for (let i = 0; i < columnCount; i++) {
      const columnHeight = Math.floor(Math.random() * 25) + 15;
      
      // Generate characters for column
      const column = [];
      for (let j = 0; j < columnHeight; j++) {
        column.push({
          char: matrixChars[Math.floor(Math.random() * matrixChars.length)],
          opacity: Math.random() * 0.8 + 0.2,
          delay: Math.random() * 2
        });
      }
      
      // Randomly assign to top-to-bottom or bottom-to-top
      if (Math.random() > 0.5) {
        topToBottomColumns.push({
          chars: column,
          left: i * 20,
          animationDelay: Math.random() * 8 // Increased animation delay range
        });
      } else {
        bottomToTopColumns.push({
          chars: column,
          left: i * 20,
          animationDelay: Math.random() * 8 // Increased animation delay range
        });
      }
    }
    
    return { topToBottom: topToBottomColumns, bottomToTop: bottomToTopColumns };
  };

  const [matrixColumns] = useState(() => generateMatrixColumns());

  useEffect(() => {
    // Matrix code rain animation duration: 10 seconds (extended for better effect)
    const timeout = setTimeout(() => {
      setIsVisible(false);
      setTimeout(() => {
        onComplete();
      }, 500);
    }, 10000); // Extended from 6000 to 10000ms

    // Animated dots for loading effect
    const dotInterval = setInterval(() => {
      setDots(prev => prev.length >= 3 ? '' : prev + '.');
    }, 500);

    return () => {
      clearTimeout(timeout);
      clearInterval(dotInterval);
    };
  }, [onComplete]);

  // Early return AFTER all hooks are called
  if (!isVisible) {
    return null;
  }

  return (
    <div 
      className={`fixed inset-0 z-50 flex items-center justify-center transition-opacity duration-500 overflow-hidden ${
        isVisible ? 'opacity-100' : 'opacity-0'
      } ${isDarkTheme ? 'bg-black' : 'bg-gray-900'}`}
    >
      {/* Matrix Code Rain Background - Bidirectional */}
      <div className="absolute inset-0">
        {/* Top to Bottom Rain */}
        {matrixColumns.topToBottom.map((column, columnIndex) => (
          <div
            key={`ttb-${columnIndex}`}
            className="absolute top-0 flex flex-col text-green-400 font-mono text-sm leading-tight"
            style={{
              left: `${column.left}px`,
              animationDelay: `${column.animationDelay}s`,
              animation: 'matrixFallDown 10s linear infinite' // Extended duration
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
        
        {/* Bottom to Top Rain */}
        {matrixColumns.bottomToTop.map((column, columnIndex) => (
          <div
            key={`btt-${columnIndex}`}
            className="absolute bottom-0 flex flex-col-reverse text-blue-400 font-mono text-sm leading-tight"
            style={{
              left: `${column.left}px`,
              animationDelay: `${column.animationDelay}s`,
              animation: 'matrixFallUp 10s linear infinite' // Extended duration
            }}
          >
            {column.chars.map((item, charIndex) => (
              <span
                key={charIndex}
                className="block"
                style={{
                  opacity: item.opacity,
                  animationDelay: `${item.delay}s`,
                  color: charIndex === 0 ? '#0088ff' : `rgba(0, 136, 255, ${item.opacity})`
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
        <div className="relative p-6">
          {/* Animated Neon Border */}
          <div 
            className="absolute inset-0 rounded-lg border-4 border-transparent"
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
          <div className="absolute inset-2 rounded-lg bg-gradient-to-r from-green-400/20 to-blue-400/20 blur-lg" />
          
          {/* Peacock Animation Video */}
          <div className="relative w-48 h-32 flex items-center justify-center bg-black/80 rounded-lg backdrop-blur-sm overflow-hidden">
            <video
              autoPlay
              loop
              muted
              playsInline
              className="w-full h-full object-cover rounded-lg"
              style={{ filter: 'brightness(1.2) contrast(1.1)' }}
            >
              <source src="/peacock-animation.mov" type="video/quicktime" />
              <source src="/peacock-animation.mov" type="video/mp4" />
              {/* Fallback content */}
              <div className="text-center flex items-center justify-center h-full">
                <div className="text-2xl font-bold text-green-400 mb-2">
                  🦚 ARGUS AI
                </div>
              </div>
            </video>
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