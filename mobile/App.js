import React, { useRef, useState, useEffect, useCallback } from 'react';
import {
  StyleSheet,
  View,
  Text,
  ActivityIndicator,
  BackHandler,
  Platform,
  Linking,
  ScrollView,
  RefreshControl,
  TouchableOpacity,
  Alert,
  StatusBar
} from 'react-native';
import { SafeAreaProvider, SafeAreaView } from 'react-native-safe-area-context';
import { WebView } from 'react-native-webview';

// ==========================================
// CONFIGURATION
// Replace with your deployed backend/web URL or LAN IP (e.g. 'http://192.168.1.10:8000')
// 'http://10.0.2.2:8000' is localhost for Android Emulator
// ==========================================
const TARGET_URL = 'http://10.0.2.2:8000';

export default function App() {
  const webViewRef = useRef(null);

  // Component States
  const [canGoBack, setCanGoBack] = useState(false);
  const [currentUrl, setCurrentUrl] = useState(TARGET_URL);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [hasError, setHasError] = useState(false);

  // ==========================================
  // 1. Android Native Back Button Support
  // ==========================================
  useEffect(() => {
    if (Platform.OS !== 'android') return;

    const onBackPress = () => {
      if (canGoBack && webViewRef.current) {
        webViewRef.current.goBack();
        return true; // Prevent app close, navigate back in WebView history
      }

      // Prompt to exit when at root page
      Alert.alert('Exit SonicAM', 'Are you sure you want to close the app?', [
        { text: 'Cancel', style: 'cancel' },
        { text: 'Exit', onPress: () => BackHandler.exitApp() }
      ]);
      return true;
    };

    const backHandler = BackHandler.addEventListener('hardwareBackPress', onBackPress);
    return () => backHandler.remove();
  }, [canGoBack]);

  // ==========================================
  // 2. Native Pull-to-Refresh
  // ==========================================
  const onRefresh = useCallback(() => {
    setIsRefreshing(true);
    setHasError(false);
    if (webViewRef.current) {
      webViewRef.current.reload();
    }
    setTimeout(() => setIsRefreshing(false), 1200);
  }, []);

  // ==========================================
  // 3. External Link Detection & Handling
  // ==========================================
  const handleShouldStartLoad = (request) => {
    const { url } = request;

    // Allow blank URLs, data URIs, or local dev server URLs
    if (
      url === 'about:blank' ||
      url.startsWith('data:') ||
      url.startsWith('blob:') ||
      url.startsWith('http://10.0.2.2') ||
      url.startsWith('http://localhost') ||
      url.startsWith('http://127.0.0.1') ||
      url.includes('ngrok') ||
      url.includes('loca.lt') ||
      url.includes('vercel.app')
    ) {
      return true;
    }

    // External social or streaming URLs: open in device default browser / apps
    Linking.openURL(url);
    return false;
  };

  return (
    <SafeAreaProvider>
      {/* Dark Theme Status Bar matching SonicAM */}
      <StatusBar barStyle="light-content" backgroundColor="#0c0907" />

      {/* Safe Area View prevents notch & home indicator overlap */}
      <SafeAreaView style={styles.safeArea}>
        <View style={styles.container}>
          {/* Main Native Full-Screen WebView */}
          <WebView
            ref={webViewRef}
            source={{ uri: TARGET_URL }}
            style={styles.webView}
            // Permissions & Audio Capabilities
            mediaPlaybackRequiresUserAction={false}
            allowsInlineMediaPlayback={true}
            userAgent="SonicAMMobile/1.0"
            // Cache & Hardware Acceleration
            domStorageEnabled={true}
            javaScriptEnabled={true}
            androidHardwareAccelerationDisabled={false}
            // Navigation tracking
            onNavigationStateChange={(navState) => {
              setCanGoBack(navState.canGoBack);
              setCurrentUrl(navState.url);
            }}
            // Link Interceptor
            onShouldStartLoadWithRequest={handleShouldStartLoad}
            // Loading Handlers
            onLoadStart={() => setIsLoading(true)}
            onLoadEnd={() => setIsLoading(false)}
            onError={() => {
              setIsLoading(false);
              setHasError(true);
            }}
          />

          {/* Loading Indicator Overlay */}
          {isLoading && (
            <View style={styles.loadingOverlay}>
              <ActivityIndicator size="large" color="#e5a950" />
              <Text style={styles.loadingText}>Loading SonicAM...</Text>
            </View>
          )}

          {/* Connection Error Fallback Screen with Pull-to-Refresh */}
          {hasError && (
            <ScrollView
              contentContainerStyle={styles.errorContainer}
              refreshControl={
                <RefreshControl
                  refreshing={isRefreshing}
                  onRefresh={onRefresh}
                  tintColor="#e5a950"
                  colors={['#e5a950']}
                />
              }
            >
              <Text style={styles.errorIcon}>📡</Text>
              <Text style={styles.errorTitle}>Connection Failed</Text>
              <Text style={styles.errorDescription}>
                Could not connect to the SonicAM server. Ensure the server is online and your mobile device is connected.
              </Text>
              <TouchableOpacity style={styles.retryButton} onPress={onRefresh}>
                <Text style={styles.retryButtonText}>Tap to Retry</Text>
              </TouchableOpacity>
            </ScrollView>
          )}
        </View>
      </SafeAreaView>
    </SafeAreaProvider>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: '#0c0907',
  },
  container: {
    flex: 1,
    backgroundColor: '#0c0907',
    position: 'relative',
  },
  webView: {
    flex: 1,
    backgroundColor: '#0c0907',
  },
  loadingOverlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: '#0c0907',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 10,
  },
  loadingText: {
    marginTop: 14,
    fontSize: 14,
    color: '#c9b7a4',
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
    letterSpacing: 1,
  },
  errorContainer: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: '#0c0907',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 24,
    zIndex: 20,
  },
  errorIcon: {
    fontSize: 54,
    marginBottom: 16,
  },
  errorTitle: {
    fontSize: 22,
    fontWeight: 'bold',
    color: '#ffffff',
    marginBottom: 8,
  },
  errorDescription: {
    fontSize: 14,
    color: '#c9b7a4',
    textAlign: 'center',
    lineHeight: 20,
    marginBottom: 24,
  },
  retryButton: {
    backgroundColor: '#e5a950',
    paddingVertical: 12,
    paddingHorizontal: 28,
    borderRadius: 8,
    shadowColor: '#e5a950',
    shadowOpacity: 0.4,
    shadowRadius: 10,
    elevation: 5,
  },
  retryButtonText: {
    color: '#120904',
    fontWeight: 'bold',
    fontSize: 16,
  },
});
