import React, { useRef, useState, useEffect, useCallback } from 'react';
import {
  StyleSheet,
  View,
  Text,
  BackHandler,
  Platform,
  Linking,
  ScrollView,
  TouchableOpacity,
  TextInput,
  Alert,
  StatusBar,
  Modal,
  Image,
  ActivityIndicator
} from 'react-native';
import { SafeAreaProvider, SafeAreaView } from 'react-native-safe-area-context';
import { WebView } from 'react-native-webview';
import { BUNDLED_HTML } from './assets/bundled_html';

// Connection defaults
const DEFAULT_LAN_URL = 'http://192.168.10.36:8000';
const DEFAULT_EMULATOR_URL = 'http://10.0.2.2:8000';

export default function App() {
  const webViewRef = useRef(null);

  // Server configuration
  const [serverUrl, setServerUrl] = useState(DEFAULT_LAN_URL);
  const [inputUrl, setInputUrl] = useState(DEFAULT_LAN_URL);
  const [useRemoteServer, setUseRemoteServer] = useState(false);
  const [showConfigModal, setShowConfigModal] = useState(false);

  // Server health test state
  const [isTestingConnection, setIsTestingConnection] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState(null); // 'success' | 'error' | null
  const [statusMessage, setStatusMessage] = useState('');

  // WebView navigation state
  const [canGoBack, setCanGoBack] = useState(false);

  // JavaScript to inject into the web view to configure backend URL
  const injectedJavaScript = `
    (function() {
      window.SONICAM_BACKEND_URL = "${serverUrl}";
      window.SONICAM_IS_MOBILE_APP = true;
    })();
    true;
  `;

  // 1. Android Hardware Back Button Navigation
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

      Alert.alert('Exit SonicAM', 'Are you sure you want to close SonicAM?', [
        { text: 'Cancel', style: 'cancel' },
        { text: 'Exit', onPress: () => BackHandler.exitApp() }
      ]);
      return true;
    };

    const backHandler = BackHandler.addEventListener('hardwareBackPress', onBackPress);
    return () => backHandler.remove();
  }, [canGoBack, showConfigModal]);

  // 2. Test Connection to Backend
  const handleTestConnection = async (targetUrl) => {
    const testUrl = (targetUrl || inputUrl).trim().replace(/\/+$/, '');
    if (!testUrl) return;

    setIsTestingConnection(true);
    setConnectionStatus(null);
    setStatusMessage('Checking connection to ' + testUrl + '...');

    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 4500);

      const resp = await fetch(`${testUrl}/api/health`, {
        method: 'GET',
        signal: controller.signal
      });
      clearTimeout(timeoutId);

      if (resp.ok) {
        const data = await resp.json();
        setConnectionStatus('success');
        setStatusMessage(`Connected! Engine is ${data.status || 'Ready'}`);
      } else {
        setConnectionStatus('error');
        setStatusMessage(`Server responded with status: ${resp.status}`);
      }
    } catch (err) {
      setConnectionStatus('error');
      setStatusMessage(`Cannot connect. Ensure server is running on ${testUrl}`);
    } finally {
      setIsTestingConnection(false);
    }
  };

  // 3. Save & Apply Server URL
  const handleSaveUrl = (urlToApply, remoteMode = useRemoteServer) => {
    let clean = (urlToApply || inputUrl).trim();
    if (!clean) return;
    if (!clean.startsWith('http://') && !clean.startsWith('https://')) {
      clean = 'http://' + clean;
    }
    setServerUrl(clean);
    setInputUrl(clean);
    setUseRemoteServer(remoteMode);
    setShowConfigModal(false);
    setConnectionStatus(null);

    // Refresh WebView with new backend configuration
    if (webViewRef.current) {
      webViewRef.current.reload();
    }
  };

  // 4. External Link Interceptor (Spotify, Apple Music, YouTube)
  const handleShouldStartLoad = (request) => {
    const { url } = request;

    // Allow data/blob and local content
    if (
      url === 'about:blank' ||
      url.startsWith('data:') ||
      url.startsWith('blob:') ||
      url.startsWith('http://10.0.2.2') ||
      url.startsWith('http://localhost') ||
      url.startsWith('http://127.0.0.1') ||
      url.startsWith('http://192.168.') ||
      url.includes('ngrok') ||
      url.includes('vercel.app')
    ) {
      return true;
    }

    // Open external streaming apps (Spotify, Apple, Shazam) in native OS apps
    Linking.openURL(url).catch(() => {});
    return false;
  };

  return (
    <SafeAreaProvider>
      <StatusBar barStyle="light-content" backgroundColor="#0c0907" />

      <SafeAreaView style={styles.safeArea}>
        <View style={styles.container}>
          {/* Main SonicAM Interface (Loads Instantly via Bundled HTML or Remote URL) */}
          <WebView
            ref={webViewRef}
            source={
              useRemoteServer
                ? { uri: serverUrl }
                : { html: BUNDLED_HTML, baseUrl: serverUrl }
            }
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

          {/* Discreet Floating Server Settings Button */}
          <TouchableOpacity
            style={styles.floatingSettingsBtn}
            onPress={() => {
              setInputUrl(serverUrl);
              setConnectionStatus(null);
              setShowConfigModal(true);
            }}
            activeOpacity={0.8}
          >
            <View style={styles.floatingSettingsInner}>
              <Text style={styles.floatingSettingsText}>⚙️ Server</Text>
            </View>
          </TouchableOpacity>

          {/* Server Configuration Modal */}
          <Modal
            visible={showConfigModal}
            transparent={true}
            animationType="fade"
            onRequestClose={() => setShowConfigModal(false)}
          >
            <View style={styles.modalBackdrop}>
              <View style={styles.modalCard}>
                <ScrollView contentContainerStyle={styles.modalScroll}>
                  <Image
                    source={require('./assets/icon.png')}
                    style={styles.modalIcon}
                    resizeMode="contain"
                  />

                  <Text style={styles.modalTitle}>SonicAM Server Settings</Text>
                  <Text style={styles.modalSubtitle}>
                    Configure your PC backend or cloud URL for song recognition:
                  </Text>

                  {/* URL Input */}
                  <View style={styles.inputWrapper}>
                    <TextInput
                      style={styles.urlInput}
                      value={inputUrl}
                      onChangeText={(val) => {
                        setInputUrl(val);
                        setConnectionStatus(null);
                      }}
                      placeholder="e.g. http://192.168.10.36:8000"
                      placeholderTextColor="#8a7563"
                      autoCapitalize="none"
                      autoCorrect={false}
                      keyboardType="url"
                    />
                  </View>

                  {/* Status Indicator */}
                  {statusMessage !== '' && (
                    <View
                      style={[
                        styles.statusBanner,
                        connectionStatus === 'success'
                          ? styles.statusSuccess
                          : connectionStatus === 'error'
                          ? styles.statusError
                          : styles.statusTesting
                      ]}
                    >
                      <Text
                        style={[
                          styles.statusBannerText,
                          connectionStatus === 'success'
                            ? styles.statusSuccessText
                            : connectionStatus === 'error'
                            ? styles.statusErrorText
                            : styles.statusTestingText
                        ]}
                      >
                        {statusMessage}
                      </Text>
                    </View>
                  )}

                  {/* Presets */}
                  <Text style={styles.presetsLabel}>Quick Presets:</Text>
                  <View style={styles.presetsRow}>
                    <TouchableOpacity
                      style={styles.presetChip}
                      onPress={() => {
                        setInputUrl(DEFAULT_LAN_URL);
                        handleTestConnection(DEFAULT_LAN_URL);
                      }}
                    >
                      <Text style={styles.presetChipText}>🏠 Wi-Fi LAN (PC)</Text>
                    </TouchableOpacity>

                    <TouchableOpacity
                      style={styles.presetChip}
                      onPress={() => {
                        setInputUrl(DEFAULT_EMULATOR_URL);
                        handleTestConnection(DEFAULT_EMULATOR_URL);
                      }}
                    >
                      <Text style={styles.presetChipText}>💻 Emulator</Text>
                    </TouchableOpacity>
                  </View>

                  {/* Action Buttons */}
                  <View style={styles.buttonStack}>
                    <TouchableOpacity
                      style={styles.testBtn}
                      onPress={() => handleTestConnection(inputUrl)}
                      disabled={isTestingConnection}
                    >
                      {isTestingConnection ? (
                        <ActivityIndicator size="small" color="#e5a950" />
                      ) : (
                        <Text style={styles.testBtnText}>⚡ Test Connection</Text>
                      )}
                    </TouchableOpacity>

                    <TouchableOpacity
                      style={styles.saveBtn}
                      onPress={() => handleSaveUrl(inputUrl, false)}
                    >
                      <Text style={styles.saveBtnText}>Save & Apply</Text>
                    </TouchableOpacity>

                    <TouchableOpacity
                      style={styles.closeBtn}
                      onPress={() => setShowConfigModal(false)}
                    >
                      <Text style={styles.closeBtnText}>Close</Text>
                    </TouchableOpacity>
                  </View>
                </ScrollView>
              </View>
            </View>
          </Modal>
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
    top: 8,
    right: 10,
    zIndex: 50,
  },
  floatingSettingsInner: {
    backgroundColor: 'rgba(28, 20, 15, 0.88)',
    borderColor: 'rgba(229, 169, 80, 0.45)',
    borderWidth: 1,
    borderRadius: 16,
    paddingVertical: 4,
    paddingHorizontal: 10,
  },
  floatingSettingsText: {
    color: '#e5a950',
    fontSize: 11,
    fontWeight: '700',
  },
  modalBackdrop: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.85)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 16,
  },
  modalCard: {
    width: '100%',
    maxWidth: 360,
    backgroundColor: '#18110c',
    borderRadius: 20,
    borderColor: 'rgba(229, 169, 80, 0.35)',
    borderWidth: 1.5,
    overflow: 'hidden',
    paddingVertical: 20,
    paddingHorizontal: 20,
  },
  modalScroll: {
    alignItems: 'center',
  },
  modalIcon: {
    width: 68,
    height: 68,
    borderRadius: 16,
    marginBottom: 12,
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: '800',
    color: '#faf5ed',
    marginBottom: 6,
    textAlign: 'center',
  },
  modalSubtitle: {
    fontSize: 13,
    color: '#c9b7a4',
    textAlign: 'center',
    lineHeight: 18,
    marginBottom: 16,
  },
  inputWrapper: {
    width: '100%',
    marginBottom: 10,
  },
  urlInput: {
    width: '100%',
    backgroundColor: 'rgba(12, 9, 7, 0.95)',
    borderWidth: 1.5,
    borderColor: 'rgba(229, 169, 80, 0.45)',
    borderRadius: 10,
    paddingVertical: 10,
    paddingHorizontal: 14,
    color: '#faf5ed',
    fontSize: 14,
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },
  statusBanner: {
    width: '100%',
    paddingVertical: 8,
    paddingHorizontal: 12,
    borderRadius: 8,
    marginBottom: 12,
  },
  statusSuccess: {
    backgroundColor: 'rgba(16, 185, 129, 0.15)',
    borderColor: 'rgba(16, 185, 129, 0.4)',
    borderWidth: 1,
  },
  statusError: {
    backgroundColor: 'rgba(239, 68, 68, 0.15)',
    borderColor: 'rgba(239, 68, 68, 0.4)',
    borderWidth: 1,
  },
  statusTesting: {
    backgroundColor: 'rgba(229, 169, 80, 0.12)',
    borderColor: 'rgba(229, 169, 80, 0.3)',
    borderWidth: 1,
  },
  statusBannerText: {
    fontSize: 12,
    textAlign: 'center',
    fontWeight: '600',
  },
  statusSuccessText: {
    color: '#34d399',
  },
  statusErrorText: {
    color: '#f87171',
  },
  statusTestingText: {
    color: '#e5a950',
  },
  presetsLabel: {
    alignSelf: 'flex-start',
    color: '#8a7563',
    fontSize: 12,
    fontWeight: '600',
    marginBottom: 6,
  },
  presetsRow: {
    flexDirection: 'row',
    gap: 8,
    marginBottom: 16,
    width: '100%',
  },
  presetChip: {
    flex: 1,
    backgroundColor: 'rgba(229, 169, 80, 0.1)',
    borderColor: 'rgba(229, 169, 80, 0.3)',
    borderWidth: 1,
    borderRadius: 8,
    paddingVertical: 8,
    alignItems: 'center',
  },
  presetChipText: {
    color: '#e5a950',
    fontSize: 12,
    fontWeight: '600',
  },
  buttonStack: {
    width: '100%',
    gap: 8,
  },
  testBtn: {
    width: '100%',
    backgroundColor: 'rgba(229, 169, 80, 0.15)',
    borderColor: '#e5a950',
    borderWidth: 1,
    paddingVertical: 10,
    borderRadius: 10,
    alignItems: 'center',
  },
  testBtnText: {
    color: '#e5a950',
    fontWeight: '700',
    fontSize: 14,
  },
  saveBtn: {
    width: '100%',
    backgroundColor: '#e5a950',
    paddingVertical: 12,
    borderRadius: 10,
    alignItems: 'center',
  },
  saveBtnText: {
    color: '#120904',
    fontWeight: '800',
    fontSize: 15,
  },
  closeBtn: {
    paddingVertical: 8,
    alignItems: 'center',
  },
  closeBtnText: {
    color: '#8a7563',
    fontSize: 13,
  },
});
