import React, { useRef, useState, useEffect } from 'react';
import {
  StyleSheet,
  View,
  BackHandler,
  Platform,
  Linking,
  Alert,
  StatusBar,
  PermissionsAndroid
} from 'react-native';
import { SafeAreaProvider, SafeAreaView } from 'react-native-safe-area-context';
import { WebView } from 'react-native-webview';
import { BUNDLED_HTML } from './assets/bundled_html';

// 24/7 Global Cloud Recognition Engine (Live Vercel Production Deployment)
const CLOUD_BACKEND_URL = 'https://anything-to-audio-am.vercel.app';

export default function App() {
  const webViewRef = useRef(null);
  const [canGoBack, setCanGoBack] = useState(false);

  // Request Microphone and Media permissions on Android app startup
  useEffect(() => {
    async function requestAndroidPermissions() {
      if (Platform.OS !== 'android') return;
      try {
        const permissions = [
          PermissionsAndroid.PERMISSIONS.RECORD_AUDIO,
          PermissionsAndroid.PERMISSIONS.MODIFY_AUDIO_SETTINGS,
        ];

        // Android 13+ (API 33+) granular media permissions
        if (Platform.Version >= 33) {
          if (PermissionsAndroid.PERMISSIONS.READ_MEDIA_AUDIO) {
            permissions.push(PermissionsAndroid.PERMISSIONS.READ_MEDIA_AUDIO);
          }
          if (PermissionsAndroid.PERMISSIONS.READ_MEDIA_VIDEO) {
            permissions.push(PermissionsAndroid.PERMISSIONS.READ_MEDIA_VIDEO);
          }
        } else {
          if (PermissionsAndroid.PERMISSIONS.READ_EXTERNAL_STORAGE) {
            permissions.push(PermissionsAndroid.PERMISSIONS.READ_EXTERNAL_STORAGE);
          }
        }

        await PermissionsAndroid.requestMultiple(permissions);
      } catch (err) {
        console.warn('Android permissions request error:', err);
      }
    }

    requestAndroidPermissions();
  }, []);

  // Handle messages from WebView (e.g. explicit microphone re-request)
  const handleMessage = async (event) => {
    try {
      const data = JSON.parse(event.nativeEvent.data);
      if (data.type === 'REQUEST_MIC_PERMISSION' && Platform.OS === 'android') {
        await PermissionsAndroid.request(PermissionsAndroid.PERMISSIONS.RECORD_AUDIO, {
          title: 'Microphone Permission',
          message: 'SonicAM needs microphone access to listen to ambient songs and detect music.',
          buttonPositive: 'Allow',
          buttonNegative: 'Deny'
        });
      }
    } catch (_) {}
  };

  // Pre-load script to define environment variables before any page script executes
  const injectedJavaScriptBeforeContentLoaded = `
    (function() {
      window.SONICAM_BACKEND_URL = "${CLOUD_BACKEND_URL}";
      window.SONICAM_IS_MOBILE_APP = true;
    })();
    true;
  `;

  // Post-load script: guarantees cloud connection and completely removes any APK download UI
  const injectedJavaScript = `
    (function() {
      window.SONICAM_BACKEND_URL = "${CLOUD_BACKEND_URL}";
      window.SONICAM_IS_MOBILE_APP = true;

      // Ensure body has mobile app marker
      if (document.body) {
        document.body.classList.add('is-mobile-app');
      }

      // Add strict styling to hide any external repo, Hugging Face, or APK download badges inside the APK
      var styleEl = document.createElement('style');
      styleEl.innerHTML = [
        '#btnDirectDownloadApk,',
        '.hero-apk-badge-wrapper,',
        '.hero-apk-badge,',
        'a[href*="SonicAM.apk"],',
        '.footer-link[href*="SonicAM.apk"],',
        'a[href*="github.com"],',
        'a[href*="huggingface.co"],',
        '.footer-links,',
        '.dev-link {',
        '  display: none !important;',
        '  visibility: hidden !important;',
        '  height: 0 !important;',
        '  max-height: 0 !important;',
        '  margin: 0 !important;',
        '  padding: 0 !important;',
        '  overflow: hidden !important;',
        '  pointer-events: none !important;',
        '}'
      ].join('\\n');
      (document.head || document.documentElement).appendChild(styleEl);

      // Permanently remove elements from DOM
      function purgeApkElements() {
        var selectors = [
          '#btnDirectDownloadApk',
          '.hero-apk-badge-wrapper',
          '.hero-apk-badge',
          'a[href*="SonicAM.apk"]',
          '.footer-link[href*="SonicAM.apk"]',
          'a[href*="github.com"]',
          'a[href*="huggingface.co"]',
          '.footer-links',
          '.dev-link'
        ];
        selectors.forEach(function(sel) {
          document.querySelectorAll(sel).forEach(function(el) {
            if (el && el.parentNode) {
              el.parentNode.removeChild(el);
            }
          });
        });
      }

      purgeApkElements();
      if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', purgeApkElements);
      }
      window.addEventListener('load', purgeApkElements);
      setTimeout(purgeApkElements, 300);
      setTimeout(purgeApkElements, 1000);
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
      url.includes('anything-to-audio-am.vercel.app') ||
      url.includes('vercel.app') ||
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
            injectedJavaScriptBeforeContentLoaded={injectedJavaScriptBeforeContentLoaded}
            injectedJavaScript={injectedJavaScript}
            onMessage={handleMessage}
            mediaPlaybackRequiresUserAction={false}
            allowsInlineMediaPlayback={true}
            mediaCapturePermissionGrantType="grant"
            allowFileAccess={true}
            allowFileAccessFromFileURLs={true}
            allowUniversalAccessFromFileURLs={true}
            userAgent="SonicAMMobile/1.2.1"
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
