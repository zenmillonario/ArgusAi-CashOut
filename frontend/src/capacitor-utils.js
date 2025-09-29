// Capacitor utilities for mobile app
import { Capacitor } from '@capacitor/core';
import { StatusBar, Style } from '@capacitor/status-bar';
import { SplashScreen } from '@capacitor/splash-screen';
import { Keyboard } from '@capacitor/keyboard';
import { Device } from '@capacitor/device';
import { Network } from '@capacitor/network';

class CapacitorManager {
  constructor() {
    this.isNative = Capacitor.isNativePlatform();
    this.platform = Capacitor.getPlatform();
  }

  async initializeApp() {
    if (!this.isNative) return;

    try {
      console.log('🚀 Initializing mobile app...');
      
      // Configure status bar
      await StatusBar.setStyle({ style: Style.Dark });
      await StatusBar.setBackgroundColor({ color: '#1f2937' });

      // Hide splash screen after initialization
      await SplashScreen.hide();

      // Configure keyboard
      Keyboard.addListener('keyboardWillShow', (info) => {
        console.log('Keyboard will show with height:', info.keyboardHeight);
      });

      Keyboard.addListener('keyboardDidHide', () => {
        console.log('Keyboard did hide');
      });

      // Monitor network status
      Network.addListener('networkStatusChange', (status) => {
        console.log('Network status changed:', status);
        if (!status.connected) {
          this.showNetworkError();
        }
      });

      // Get device info
      const deviceInfo = await Device.getInfo();
      console.log('📱 Device info:', deviceInfo);

      console.log('✅ Mobile app initialized successfully');
      
    } catch (error) {
      console.error('❌ Error initializing mobile app:', error);
    }
  }

  showNetworkError() {
    // You can implement a custom network error UI here
    alert('Network connection lost. Please check your internet connection.');
  }

  async getDeviceInfo() {
    if (!this.isNative) return null;
    return await Device.getInfo();
  }

  async getNetworkStatus() {
    if (!this.isNative) return { connected: true, connectionType: 'wifi' };
    return await Network.getStatus();
  }

  // Mobile-specific WebSocket URL
  getWebSocketUrl(baseUrl) {
    if (!this.isNative) {
      // Web version
      return `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/api/ws`;
    }
    
    // Mobile version - use your production backend URL
    const productionUrl = baseUrl.replace('http://', 'ws://').replace('https://', 'wss://');
    return `${productionUrl}/api/ws`;
  }

  // Mobile-specific API URL
  getApiUrl(baseUrl) {
    if (!this.isNative) {
      // Web version
      return baseUrl ? `${baseUrl}/api` : '/api';
    }
    
    // Mobile version - use your production backend URL
    return `${baseUrl}/api`;
  }

  // Haptic feedback for mobile
  async vibrate(duration = 100) {
    if (!this.isNative) return;
    
    try {
      // Simple vibration pattern
      if (navigator.vibrate) {
        navigator.vibrate(duration);
      }
    } catch (error) {
      console.log('Vibration not supported');
    }
  }

  // Handle app state changes
  addAppStateListeners(callbacks = {}) {
    if (!this.isNative) return;

    document.addEventListener('resume', () => {
      console.log('📱 App resumed');
      if (callbacks.onResume) callbacks.onResume();
    });

    document.addEventListener('pause', () => {
      console.log('📱 App paused');
      if (callbacks.onPause) callbacks.onPause();
    });
  }

  // Mobile-friendly error handling
  showMobileAlert(title, message, buttons = ['OK']) {
    if (!this.isNative) {
      alert(`${title}\n\n${message}`);
      return;
    }

    // For native platforms, you could use Capacitor's Dialog plugin
    // or implement a custom modal component
    alert(`${title}\n\n${message}`);
  }
}

export const capacitorManager = new CapacitorManager();
export default capacitorManager;