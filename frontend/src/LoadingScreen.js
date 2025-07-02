import React, { useState, useEffect, useRef } from 'react';

const LoadingScreen = ({ onComplete, isDarkTheme }) => {
  const [isVisible, setIsVisible] = useState(true);
  const [isVideoLoaded, setIsVideoLoaded] = useState(false);
  const [showClickToPlay, setShowClickToPlay] = useState(false);
  const videoRef = useRef(null);

  useEffect(() => {
    const video = videoRef.current;
    if (video) {
      // Handle video load
      const handleCanPlay = () => {
        setIsVideoLoaded(true);
        // Small delay to ensure smooth start
        setTimeout(async () => {
          try {
            // Start playing muted first (more likely to work)
            video.muted = true;
            await video.play();
            
            // Once playing, try to unmute for sound
            setTimeout(() => {
              try {
                video.muted = false;
              } catch (unmuteError) {
                console.log('Could not unmute video, playing silently');
              }
            }, 100);
          } catch (error) {
            console.log('Autoplay failed, showing click to play');
            setShowClickToPlay(true);
          }
        }, 100);
      };

      // Handle video end - always proceed after video completes
      const handleVideoEnd = () => {
        // Fade out and then call onComplete
        setIsVisible(false);
        setTimeout(() => {
          onComplete();
        }, 500); // Match the fade duration
      };

      video.addEventListener('canplay', handleCanPlay);
      video.addEventListener('ended', handleVideoEnd);

      // Cleanup
      return () => {
        video.removeEventListener('canplay', handleCanPlay);
        video.removeEventListener('ended', handleVideoEnd);
      };
    }
  }, [onComplete]);

  if (!isVisible) {
    return null;
  }

  return (
    <div 
      className={`fixed inset-0 z-50 flex items-center justify-center transition-opacity duration-500 ${
        isVisible ? 'opacity-100' : 'opacity-0'
      } ${isDarkTheme ? 'bg-black' : 'bg-white'}`}
      style={{
        background: isDarkTheme 
          ? 'linear-gradient(135deg, #000000 0%, #1a1a1a 50%, #000000 100%)'
          : 'linear-gradient(135deg, #ffffff 0%, #f8f9fa 50%, #ffffff 100%)'
      }}
    >
      {/* Video Container */}
      <div className="relative w-full h-full flex items-center justify-center">
        {/* Click anywhere to skip or video controls */}
        <div 
          className="absolute inset-0 flex flex-col items-center justify-center cursor-pointer z-20"
          onClick={() => {
            const video = videoRef.current;
            if (video && video.paused) {
              video.play().catch(() => {
                // If play fails, just skip to app
                onComplete();
              });
            }
          }}
        >
          {/* Skip button - always visible */}
          <div className="absolute top-8 right-8">
            <button
              onClick={(e) => {
                e.stopPropagation();
                onComplete();
              }}
              className={`px-4 py-2 rounded-lg ${
                isDarkTheme 
                  ? 'bg-white/20 text-white hover:bg-white/30' 
                  : 'bg-black/20 text-white hover:bg-black/30'
              } transition-colors text-sm backdrop-blur-sm`}
            >
              Skip Intro →
            </button>
          </div>

          {/* Click to play instruction */}
          {!isVideoLoaded && (
            <div className={`text-center ${isDarkTheme ? 'text-white' : 'text-gray-900'} mb-8`}>
              <div className="text-lg font-semibold mb-2">Loading...</div>
              <div className="text-sm opacity-75">Click anywhere to skip</div>
            </div>
          )}

          {/* Video not playing instruction */}
          {isVideoLoaded && (
            <div className={`text-center ${isDarkTheme ? 'text-white' : 'text-gray-900'} mb-8`}>
              <div className="text-lg font-semibold mb-2">▶️ Click to Play Video</div>
              <div className="text-sm opacity-75">Or use Skip button above</div>
            </div>
          )}
        </div>

        {/* Video Element */}
        <video
          ref={videoRef}
          className={`max-w-full max-h-full object-contain transition-opacity duration-300 ${
            isVideoLoaded ? 'opacity-100' : 'opacity-0'
          }`}
          muted={true} // Start muted for autoplay
          playsInline
          preload="auto"
          autoPlay
        >
          <source src="/intro-video.mp4" type="video/mp4" />
          <source src="/intro-video.webm" type="video/webm" />
          Your browser does not support the video tag.
        </video>

        {/* ArgusAI CashOut branding overlay (optional) */}
        <div className={`absolute bottom-8 left-8 text-2xl font-bold ${
          isDarkTheme ? 'text-white' : 'text-gray-900'
        }`}>
          {/* You can add text overlay here if needed */}
        </div>
      </div>
    </div>
  );
};

export default LoadingScreen;