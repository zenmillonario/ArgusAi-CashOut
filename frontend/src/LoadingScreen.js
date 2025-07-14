import React, { useState, useEffect, useRef } from 'react';

const LoadingScreen = ({ onComplete, isDarkTheme }) => {
  const [isVisible, setIsVisible] = useState(true);
  const [isVideoLoaded, setIsVideoLoaded] = useState(false);
  const [showClickToPlay, setShowClickToPlay] = useState(false);
  const videoRef = useRef(null);

  useEffect(() => {
    const video = videoRef.current;
    
    // Emergency timeout to prevent indefinite loading - extended for 6 second video
    const emergencyTimeout = setTimeout(() => {
      console.log('Emergency timeout: Proceeding to app after 8 seconds');
      onComplete();
    }, 8000); // 8 seconds to allow full 6 second video + buffer

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
        clearTimeout(emergencyTimeout); // Cancel emergency timeout if video completes
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
        clearTimeout(emergencyTimeout);
      };
    }

    return () => {
      clearTimeout(emergencyTimeout);
    };
  }, [onComplete]);

  if (!isVisible) {
    return null;
  }

  return (
    <div 
      className={`fixed inset-0 z-50 flex items-center justify-center transition-opacity duration-500 cursor-pointer ${
        isVisible ? 'opacity-100' : 'opacity-0'
      } ${isDarkTheme ? 'bg-black' : 'bg-white'}`}
      style={{
        background: isDarkTheme 
          ? 'linear-gradient(135deg, #000000 0%, #1a1a1a 50%, #000000 100%)'
          : 'linear-gradient(135deg, #ffffff 0%, #f8f9fa 50%, #ffffff 100%)'
      }}
      onClick={() => {
        // Emergency: Click anywhere to proceed
        onComplete();
      }}
    >
      {/* Video Container */}
      <div className="relative w-full h-full flex items-center justify-center">
        {/* Loading indicator while video loads */}
        {!isVideoLoaded && (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className={`text-center ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
              <div className={`animate-spin rounded-full h-16 w-16 border-4 mb-4 mx-auto ${
                isDarkTheme 
                  ? 'border-white/20 border-t-white' 
                  : 'border-gray-200 border-t-gray-900'
              }`}></div>
              <div className="text-lg font-semibold">Loading...</div>
            </div>
          </div>
        )}

        {/* Click to Play - only if autoplay fails */}
        {showClickToPlay && (
          <div className="absolute inset-0 flex items-center justify-center">
            <button
              onClick={() => {
                const video = videoRef.current;
                if (video) {
                  video.play().catch(console.error);
                }
                setShowClickToPlay(false);
              }}
              className={`px-8 py-4 rounded-lg text-lg font-semibold ${
                isDarkTheme 
                  ? 'bg-white text-black hover:bg-gray-200' 
                  : 'bg-black text-white hover:bg-gray-800'
              } transition-colors`}
            >
              ▶️ Play Intro Video
            </button>
          </div>
        )}

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
          crossOrigin="anonymous"
        >
          <source src="/intro-video.mp4" type="video/mp4" />
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