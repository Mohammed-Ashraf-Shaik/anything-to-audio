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
  TextInput,
  Alert,
  StatusBar,
  Image
} from 'react-native';
import { SafeAreaProvider, SafeAreaView } from 'react-native-safe-area-context';
import { WebView } from 'react-native-webview';

// Default connection options
const DEFAULT_LAN_URL = 'http://192.168.10.36:8000';
const DEFAULT_EMULATOR_URL = 'http://10.0.2.2:8000';

export default function App() {
  const webViewRef = useRef(null);

  // Server URL configuration state
  const [serverUrl, setServerUrl] = useState(DEFAULT_LAN_URL);
  const [inputUrl, setInputUrl] = useState(DEFAULT_LAN_URL);
  const [showConfigModal, setShowConfigModal] = useState(false);

  // WebView navigation states
  const [canGoBack, setCanGoBack] = useState(false);
  const [currentUrl, setCurrentUrl] = useState(serverUrl);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [hasError, setHasError] = useState(false);

  // 1. Loading Timeout Guard: If page does not finish in 7 seconds, display config prompt
  useEffect(() => {
    let timer = null;
    if (isLoading) {
      timer = setTimeout(() => {
        if (isLoading) {
          setIsLoading(false);
          setHasError(true);
        }
      }, 7000);
    }
    return () => {
      if (timer) clearTimeout(timer);
    };
  }, [isLoading, serverUrl]);

  // 2. Android Hardware Back Button Navigation
  useEffect(() => {
    if (Platform.OS !== 'android') return;

    const onBackPress = () => {
      if (showConfigModal) {
        setShowConfigModal(false);
        return true;
      }
      if (canGoBack && webViewRef.current) {
        webViewRef.current.goBack();
        return true;
      }

      Alert.alert('Exit SonicAM', 'Are you sure you want to close the app?', [
        { text: 'Cancel', style: 'cancel' },
        { text: 'Exit', onPress: () => BackHandler.exitApp() }
      ]);
      return true;
    };

    const backHandler = BackHandler.addEventListener('hardwareBackPress', onBackPress);
    return () => backHandler.remove();
  }, [canGoBack, showConfigModal]);

  // 3. Native Pull-to-Refresh
  const onRefresh = useCallback(() => {
    setIsRefreshing(true);
    setHasError(false);
    setIsLoading(true);
    if (webViewRef.current) {
      webViewRef.current.reload();
    }
    setTimeout(() => setIsRefreshing(false), 1200);
  }, []);

  // 4. Change and Apply Server URL
  const handleConnectUrl = (urlToConnect) => {
    let clean = (urlToConnect || inputUrl).trim();
    if (!clean) return;
    if (!clean.startsWith('http://') && !clean.startsWith('https://')) {
      clean = 'http://' + clean;
    }
    setServerUrl(clean);
    setInputUrl(clean);
    setShowConfigModal(false);
    setHasError(false);
    setIsLoading(true);
  };

  // 5. External Link Interceptor
  const handleShouldStartLoad = (request) => {
    const { url } = request;

    if (
      url === 'about:blank' ||
      url.startsWith('data:') ||
      url.startsWith('blob:') ||
      url.startsWith('http://10.0.2.2') ||
      url.startsWith('http://localhost') ||
      url.startsWith('http://127.0.0.1') ||
      url.startsWith('http://192.168.') ||
      url.includes('ngrok') ||
      url.includes('loca.lt') ||
      url.includes('vercel.app')
    ) {
      return true;
    }

    // Open external links (Spotify, Apple, YouTube, Shazam) in native device apps
    Linking.openURL(url);
    return false;
  };

  return (
    <SafeAreaProvider>
      <StatusBar barStyle="light-content" backgroundColor="#0c0907" />

      <SafeAreaView style={styles.safeArea}>
        <View style={styles.container}>
          {/* Main Native Full-Screen WebView */}
          <WebView
            ref={webViewRef}
            source={{ uri: serverUrl }}
            style={styles.webView}
            mediaPlaybackRequiresUserAction={false}
            allowsInlineMediaPlayback={true}
            userAgent="SonicAMMobile/1.0"
            domStorageEnabled={true}
            javaScriptEnabled={true}
            androidHardwareAccelerationDisabled={false}
            onNavigationStateChange={(navState) => {
              setCanGoBack(navState.canGoBack);
              setCurrentUrl(navState.url);
            }}
            onShouldStartLoadWithRequest={handleShouldStartLoad}
            onLoadStart={() => {
              setIsLoading(true);
              setHasError(false);
            }}
            onLoadEnd={() => {
              setIsLoading(false);
              setHasError(false);
            }}
            onError={() => {
              setIsLoading(false);
              setHasError(true);
            }}
          />

          {/* Quick Floating Server Settings Button */}
          <TouchableOpacity
            style={styles.floatingSettingsBtn}
            onPress={() => setShowConfigModal(true)}
            activeOpacity={0.8}
          >
            <Text style={styles.floatingSettingsText}>⚙️ Server</Text>
          </TouchableOpacity>

          {/* Loading Indicator Overlay */}
          {isLoading && !hasError && (
            <View style={styles.loadingOverlay}>
              <Image
                source={require('./assets/icon.png')}
                style={styles.loadingIcon}
                resizeMode="contain"
              />
              <ActivityIndicator size="large" color="#e5a950" style={{ marginTop: 20 }} />
              <Text style={styles.loadingText}>Connecting to SonicAM...</Text>
              <Text style={styles.loadingUrl}>{serverUrl}</Text>

              <TouchableOpacity
                style={styles.loadingConfigBtn}
                onPress={() => setShowConfigModal(true)}
              >
                <Text style={styles.loadingConfigBtnText}>Change Server Address</Text>
              </TouchableOpacity>
            </View>
          )}

          {/* Connection Error or Server Config Screen */}
          {(hasError || showConfigModal) && (
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
              <Image
                source={require('./assets/icon.png')}
                style={styles.snowflakeIcon}
                resizeMode="contain"
              />

              <Text style={styles.errorTitle}>
                {showConfigModal ? 'Server Settings' : 'Connection Required'}
              </Text>

              <Text style={styles.errorDescription}>
                {showConfigModal
                  ? 'Connect SonicAM to your local network computer or cloud URL:'
                  : `Cannot reach server at:\n${serverUrl}\n\nEnsure your PC server is running and enter your Wi-Fi IP or cloud URL:`}
              </Text>

              {/* Server URL Input */}
              <View style={styles.inputWrapper}>
                <TextInput
                  style={styles.urlInput}
                  value={inputUrl}
                  onChangeText={setInputUrl}
                  placeholder="e.g. http://192.168.1.50:8000"
                  placeholderTextColor="#8a7563"
                  autoCapitalize="none"
                  autoCorrect={false}
                  keyboardType="url"
                />
              </View>

              {/* Quick Preset Buttons */}
              <View style={styles.presetsRow}>
                <TouchableOpacity
                  style={styles.presetChip}
                  onPress={() => handleConnectUrl(DEFAULT_LAN_URL)}
                >
                  <Text style={styles.presetChipText}>🏠 Wi-Fi LAN</Text>
                </TouchableOpacity>

                <TouchableOpacity
                  style={styles.presetChip}
                  onPress={() => handleConnectUrl(DEFAULT_EMULATOR_URL)}
                >
                  <Text style={styles.presetChipText}>💻 Emulator</Text>
                </TouchableOpacity>
              </View>

              {/* Connect Button */}
              <TouchableOpacity
                style={styles.connectButton}
                onPress={() => handleConnectUrl(inputUrl)}
              >
                <Text style={styles.connectButtonText}>Connect to SonicAM</Text>
              </TouchableOpacity>

              {showConfigModal && (
                <TouchableOpacity
                  style={styles.cancelButton}
                  onPress={() => setShowConfigModal(false)}
                >
                  <Text style={styles.cancelButtonText}>Close Settings</Text>
                </TouchableOpacity>
              )}
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
  floatingSettingsBtn: {
    position: 'absolute',
    top: 10,
    right: 12,
    backgroundColor: 'rgba(28, 20, 15, 0.88)',
    borderColor: 'rgba(229, 169, 80, 0.4)',
    borderWidth: 1,
    borderRadius: 20,
    paddingVertical: 5,
    paddingHorizontal: 12,
    zIndex: 50,
  },
  floatingSettingsText: {
    color: '#e5a950',
    fontSize: 12,
    fontWeight: '700',
  },
  loadingOverlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: '#0c0907',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 24,
    zIndex: 20,
  },
  loadingIcon: {
    width: 90,
    height: 90,
    borderRadius: 20,
  },
  loadingText: {
    marginTop: 16,
    fontSize: 16,
    fontWeight: '600',
    color: '#faf5ed',
    letterSpacing: 0.5,
  },
  loadingUrl: {
    marginTop: 6,
    fontSize: 12,
    color: '#8a7563',
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },
  loadingConfigBtn: {
    marginTop: 28,
    paddingVertical: 8,
    paddingHorizontal: 18,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: 'rgba(229, 169, 80, 0.35)',
    backgroundColor: 'rgba(28, 20, 15, 0.8)',
  },
  loadingConfigBtnText: {
    color: '#e5a950',
    fontSize: 13,
    fontWeight: '600',
  },
  errorContainer: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: '#0c0907',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 24,
    zIndex: 30,
  },
  snowflakeIcon: {
    width: 100,
    height: 100,
    borderRadius: 22,
    marginBottom: 16,
  },
  errorTitle: {
    fontSize: 22,
    fontWeight: '800',
    color: '#faf5ed',
    marginBottom: 8,
  },
  errorDescription: {
    fontSize: 14,
    color: '#c9b7a4',
    textAlign: 'center',
    lineHeight: 20,
    marginBottom: 20,
  },
  inputWrapper: {
    width: '100%',
    maxWidth: 340,
    marginBottom: 12,
  },
  urlInput: {
    width: '100%',
    backgroundColor: 'rgba(28, 20, 15, 0.95)',
    borderWidth: 1.5,
    borderColor: 'rgba(229, 169, 80, 0.45)',
    borderRadius: 10,
    paddingVertical: 12,
    paddingHorizontal: 16,
    color: '#faf5ed',
    fontSize: 15,
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },
  presetsRow: {
    flexDirection: 'row',
    gap: 10,
    marginBottom: 18,
  },
  presetChip: {
    backgroundColor: 'rgba(229, 169, 80, 0.12)',
    borderColor: 'rgba(229, 169, 80, 0.3)',
    borderWidth: 1,
    borderRadius: 16,
    paddingVertical: 6,
    paddingHorizontal: 14,
  },
  presetChipText: {
    color: '#e5a950',
    fontSize: 12,
    fontWeight: '600',
  },
  connectButton: {
    width: '100%',
    maxWidth: 340,
    backgroundColor: '#e5a950',
    paddingVertical: 14,
    borderRadius: 10,
    alignItems: 'center',
    shadowColor: '#e5a950',
    shadowOpacity: 0.35,
    shadowRadius: 10,
    elevation: 4,
    marginBottom: 12,
  },
  connectButtonText: {
    color: '#120904',
    fontWeight: '800',
    fontSize: 16,
  },
  cancelButton: {
    paddingVertical: 8,
    paddingHorizontal: 20,
  },
  cancelButtonText: {
    color: '#8a7563',
    fontSize: 14,
  },
});
