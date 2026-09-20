import React, { useRef, useState, useEffect } from 'react';
import {
  StyleSheet,
  View,
  BackHandler,
  Platform,
  Linking,
  Alert,
  StatusBar
} from 'react-native';
import { SafeAreaProvider, SafeAreaView } from 'react-native-safe-area-context';
import { WebView } from 'react-native-webview';
import { BUNDLED_HTML } from './assets/bundled_html';

// 24/7 Global Cloud Recognition Engine (No PC Connection Required)
const CLOUD_BACKEND_URL = 'https://mohammed-ashraf-shaik-sonicam.hf.space';

export default function App() {
  const webViewRef = useRef(null);
  const [canGoBack, setCanGoBack] = useState(false);

  // JavaScript injected into WebView to guarantee connection to Hugging Face Cloud backend
  const injectedJavaScript = `
    (function() {
      window.SONICAM_BACKEND_URL = "${CLOUD_BACKEND_URL}";
      window.SONICAM_IS_MOBILE_APP = true;
    })();
    true;
  `;

  // 1. Android Hardware Back Button Navigation
  useEffect(() => {
    if (Platform.OS !== 'android') return;

    const onBackPress = () => {
      if (canGoBack && webViewRef.current) {
        webViewRef.current.goBack();
        return true;
      }

      Alert.alert('Exit SonicAM', 'Are you sure you want to close SonicAM?', [
        { text: 'Cancel', style: 'cancel' },
        { text: 'Exit', onPress: () => BackHandler.exitApp() }
      ]);
      return true;
    };

    const backHandler = BackHandler.addEventListener('hardwareBackPress', onBackPress);
    return () => backHandler.remove();
  }, [canGoBack]);

  // 2. External Link Interceptor (Opens Spotify, Apple Music, Shazam in native apps)
  const handleShouldStartLoad = (request) => {
    const { url } = request;

    // Allow internal bundled webview assets and cloud backend
    if (
      url === 'about:blank' ||
      url.startsWith('data:') ||
      url.startsWith('blob:') ||
      url.includes('hf.space') ||
      url.includes('huggingface.co')
    ) {
      return true;
    }

    // Open external streaming apps (Spotify, Apple Music, YouTube) in native OS apps
    Linking.openURL(url).catch(() => {});
    return false;
  };

  return (
    <SafeAreaProvider>
      <StatusBar barStyle="light-content" backgroundColor="#0c0907" />

      <SafeAreaView style={styles.safeArea}>
        <View style={styles.container}>
          <WebView
            ref={webViewRef}
            source={{ html: BUNDLED_HTML, baseUrl: CLOUD_BACKEND_URL }}
            style={styles.webView}
            injectedJavaScript={injectedJavaScript}
            mediaPlaybackRequiresUserAction={false}
            allowsInlineMediaPlayback={true}
            userAgent="SonicAMMobile/1.0"
            domStorageEnabled={true}
            javaScriptEnabled={true}
            androidHardwareAccelerationDisabled={false}
            originWhitelist={['*']}
            onNavigationStateChange={(navState) => {
              setCanGoBack(navState.canGoBack);
            }}
            onShouldStartLoadWithRequest={handleShouldStartLoad}
          />
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
  },
  webView: {
    flex: 1,
    backgroundColor: '#0c0907',
  },
});
