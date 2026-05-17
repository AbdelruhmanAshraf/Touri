import { useState, useEffect } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  ScrollView,
  ActivityIndicator,
  StyleSheet,
  Image,
  Dimensions,
  Modal,
  Platform,
  TextInput,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useAuth } from '@/hooks/useAuth';
import { Redirect } from 'expo-router';
import { Feather, FontAwesome, Ionicons } from '@expo/vector-icons';
import { useTranslation } from 'react-i18next';
import { applyLanguage, AppLanguage } from '@/i18n';
import { api, getOrCreateUserId } from '@/services/api';

const { width, height } = Dimensions.get('window');

export default function HomeScreen() {
  const {
    user,
    loading,
    isAuthed,
    continueAsGuest,
    signInWithGoogle,
    signInWithEmail,
    signUpWithEmail,
    notConfigured,
  } = useAuth();

  const [showLangMenu, setShowLangMenu] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [authMode, setAuthMode] = useState<'signin' | 'signup'>('signin');
  const [authBusy, setAuthBusy] = useState(false);
  const [authErr, setAuthErr] = useState<string | null>(null);

  const [checkingPersona, setCheckingPersona] = useState(false);
  const [hasPersona, setHasPersona] = useState<boolean | null>(null);

  const { t, i18n } = useTranslation();
  const currentLang = i18n.language as AppLanguage;
  const isAr = currentLang === 'ar';

  useEffect(() => {
    if (isAuthed) {
      let isMounted = true;
      const checkPersona = async () => {
        setCheckingPersona(true);
        try {
          const uid = user?.uid ?? (await getOrCreateUserId());
          const p = await api.getPersona(uid);
          if (isMounted) {
            setHasPersona(!!p?.preferred_destination);
          }
        } catch (e) {
          if (isMounted) setHasPersona(false);
        } finally {
          if (isMounted) setCheckingPersona(false);
        }
      };
      checkPersona();
      return () => { isMounted = false; };
    }
  }, [isAuthed, user]);

  const selectLanguage = async (lang: AppLanguage) => {
    setShowLangMenu(false);
    if (currentLang !== lang) {
      await applyLanguage(lang);
    }
  };

  const handleEmailAuth = async () => {
    if (!email.trim() || !password) {
      setAuthErr('Email and password are required.');
      return;
    }
    setAuthBusy(true);
    setAuthErr(null);
    try {
      if (authMode === 'signin') {
        await signInWithEmail(email, password);
      } else {
        await signUpWithEmail(email, password);
      }
    } catch (e: any) {
      setAuthErr(e?.message ?? 'Authentication failed.');
    } finally {
      setAuthBusy(false);
    }
  };

  if (loading || authBusy || checkingPersona) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#1A1C1E" />
      </View>
    );
  }

  if (isAuthed && hasPersona !== null) {
    if (hasPersona) return <Redirect href="/(tabs)" />;
    return <Redirect href="/onboarding" />;
  }

  return (
    <SafeAreaView style={styles.container}>
      {/* Top Header with Globe Icon */}
      <View style={styles.header}>
        <View style={{ flex: 1 }} />
        <TouchableOpacity 
          style={styles.globeButton} 
          onPress={() => setShowLangMenu(true)}
        >
          <Feather name="globe" size={24} color="#1A1C1E" />
        </TouchableOpacity>
      </View>

      {/* Language Dropdown Modal */}
      <Modal visible={showLangMenu} transparent animationType="fade">
        <TouchableOpacity 
          style={styles.modalOverlay} 
          activeOpacity={1} 
          onPress={() => setShowLangMenu(false)}
        >
          <View style={styles.dropdownMenu}>
            <TouchableOpacity style={styles.dropdownItem} onPress={() => selectLanguage('en')}>
              <Text style={[styles.dropdownText, currentLang === 'en' && styles.dropdownTextActive]}>English</Text>
            </TouchableOpacity>
            <View style={styles.dropdownDivider} />
            <TouchableOpacity style={styles.dropdownItem} onPress={() => selectLanguage('ar')}>
              <Text style={[styles.dropdownText, currentLang === 'ar' && styles.dropdownTextActive]}>العربية</Text>
            </TouchableOpacity>
          </View>
        </TouchableOpacity>
      </Modal>

      <ScrollView contentContainerStyle={styles.scrollContent} bounces={false}>
        <View style={styles.contentWrapper}>
          
          <View style={styles.textContainer}>
            <Text style={[styles.title, { textAlign: isAr ? 'right' : 'left' }]}>
              {currentLang === 'ar' ? 'مرشدك الشخصي' : 'Your personal AI'}
            </Text>
            <Text style={[styles.title, { textAlign: isAr ? 'right' : 'left' }]}>
              {currentLang === 'ar' ? 'بالذكاء الاصطناعي' : 'travel guide to'}
            </Text>
            <Text style={[styles.titleHighlight, { textAlign: isAr ? 'right' : 'left' }]}>
              {currentLang === 'ar' ? 'لاستكشاف مصر' : 'explore Egypt'}
            </Text>
          </View>

          <View style={styles.imageContainer}>
            <Image 
              source={require('../assets/images/auth_welcome.png')}
              style={styles.heroImage}
              resizeMode="contain"
            />
          </View>

        </View>
      </ScrollView>

      {/* Bottom Auth Sheet */}
      <View style={styles.bottomSheet}>
        <Text style={[styles.sheetTitle, { textAlign: isAr ? 'right' : 'left' }]}>
          {currentLang === 'ar' ? 'تسجيل الدخول' : 'Sign in'}
        </Text>
        
        {authErr && <Text style={styles.errorText}>{authErr}</Text>}

        <View style={styles.inputContainer}>
          <TextInput
            style={[styles.input, { textAlign: isAr ? 'right' : 'left' }]}
            placeholder={currentLang === 'ar' ? 'البريد الإلكتروني' : 'Email'}
            placeholderTextColor="#8E8E93"
            autoCapitalize="none"
            keyboardType="email-address"
            value={email}
            onChangeText={setEmail}
          />
          <TextInput
            style={[styles.input, { textAlign: isAr ? 'right' : 'left' }]}
            placeholder={currentLang === 'ar' ? 'كلمة المرور' : 'Password'}
            placeholderTextColor="#8E8E93"
            secureTextEntry
            value={password}
            onChangeText={setPassword}
          />
        </View>

        <TouchableOpacity style={styles.emailAuthButton} onPress={handleEmailAuth}>
          <Text style={styles.emailAuthText}>
            {authMode === 'signin' 
              ? (currentLang === 'ar' ? 'تسجيل الدخول بالبريد' : 'Continue with Email')
              : (currentLang === 'ar' ? 'إنشاء حساب بالبريد' : 'Sign Up with Email')}
          </Text>
        </TouchableOpacity>

        <TouchableOpacity 
          style={styles.switchModeButton}
          onPress={() => setAuthMode(m => m === 'signin' ? 'signup' : 'signin')}
        >
          <Text style={styles.switchModeText}>
            {authMode === 'signin'
              ? (currentLang === 'ar' ? 'لا تملك حساب؟ أنشئ حساباً' : "Don't have an account? Sign Up")
              : (currentLang === 'ar' ? 'لديك حساب؟ سجل دخولك' : 'Already have an account? Sign In')}
          </Text>
        </TouchableOpacity>

        <View style={styles.dividerContainer}>
          <View style={styles.dividerLine} />
          <Text style={styles.dividerText}>OR</Text>
          <View style={styles.dividerLine} />
        </View>

        <TouchableOpacity
          style={[styles.socialButton, notConfigured && { opacity: 0.6 }]}
          onPress={signInWithGoogle}
          disabled={notConfigured}
        >
          <FontAwesome name="google" size={20} color="#1A1C1E" />
          <Text style={styles.socialButtonText}>
            {currentLang === 'ar' ? 'المتابعة بحساب جوجل' : 'Continue with Google'}
          </Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={styles.socialButton}
          onPress={continueAsGuest}
        >
          <Feather name="user" size={20} color="#1A1C1E" />
          <Text style={styles.socialButtonText}>
            {currentLang === 'ar' ? 'المتابعة كضيف' : 'Continue as Guest'}
          </Text>
        </TouchableOpacity>

        <Text style={styles.termsText}>
          {currentLang === 'ar' ? 'شروط الاستخدام وسياسة الخصوصية' : 'Terms of Use (EULA) & Privacy Policy'}
        </Text>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#FAFAFA',
  },
  container: {
    flex: 1,
    backgroundColor: '#FAFAFA',
  },
  header: {
    flexDirection: 'row',
    paddingHorizontal: 24,
    paddingTop: 16,
    zIndex: 10,
  },
  globeButton: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: '#F0F0F0',
    alignItems: 'center',
    justifyContent: 'center',
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.1)',
  },
  dropdownMenu: {
    position: 'absolute',
    top: 100, // Roughly below the globe icon
    right: 24,
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    width: 160,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.1,
    shadowRadius: 16,
    elevation: 8,
    overflow: 'hidden',
  },
  dropdownItem: {
    paddingVertical: 14,
    paddingHorizontal: 20,
  },
  dropdownText: {
    fontSize: 16,
    color: '#1A1C1E',
    fontWeight: '500',
  },
  dropdownTextActive: {
    color: '#007AFF',
    fontWeight: '700',
  },
  dropdownDivider: {
    height: 1,
    backgroundColor: '#F0F0F0',
  },
  scrollContent: {
    flexGrow: 1,
  },
  contentWrapper: {
    flex: 1,
    paddingHorizontal: 32,
    paddingTop: 40,
  },
  textContainer: {
    marginBottom: 40,
  },
  title: {
    fontSize: 40,
    fontWeight: '800',
    color: '#1A1C1E',
    letterSpacing: -1,
    lineHeight: 48,
  },
  titleHighlight: {
    fontSize: 40,
    fontWeight: '800',
    color: '#003366',
    letterSpacing: -1,
    lineHeight: 48,
  },
  imageContainer: {
    alignItems: 'center',
    justifyContent: 'center',
    height: height * 0.4,
  },
  heroImage: {
    width: width * 0.8,
    height: '100%',
  },
  bottomSheet: {
    backgroundColor: '#FFFFFF',
    borderTopLeftRadius: 32,
    borderTopRightRadius: 32,
    paddingHorizontal: 24,
    paddingTop: 32,
    paddingBottom: Platform.OS === 'ios' ? 40 : 24,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: -4 },
    shadowOpacity: 0.05,
    shadowRadius: 12,
    elevation: 10,
  },
  sheetTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: '#1A1C1E',
    marginBottom: 24,
  },
  socialButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#1A1C1E',
    paddingVertical: 18,
    borderRadius: 24,
    marginBottom: 16,
    gap: 12,
  },
  socialButtonText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '600',
  },
  inputContainer: {
    gap: 12,
    marginBottom: 16,
  },
  input: {
    backgroundColor: '#F5F5F7',
    paddingHorizontal: 16,
    paddingVertical: 14,
    borderRadius: 16,
    fontSize: 15,
    color: '#1A1C1E',
  },
  emailAuthButton: {
    backgroundColor: '#007AFF',
    paddingVertical: 16,
    borderRadius: 24,
    alignItems: 'center',
    marginBottom: 12,
  },
  emailAuthText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '700',
  },
  switchModeButton: {
    alignItems: 'center',
    marginBottom: 20,
  },
  switchModeText: {
    color: '#007AFF',
    fontSize: 14,
    fontWeight: '600',
  },
  dividerContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 20,
  },
  dividerLine: {
    flex: 1,
    height: 1,
    backgroundColor: '#E5E5EA',
  },
  dividerText: {
    color: '#8E8E93',
    marginHorizontal: 12,
    fontSize: 12,
    fontWeight: '600',
  },
  errorText: {
    color: '#FF3B30',
    fontSize: 14,
    marginBottom: 12,
    textAlign: 'center',
  },
  termsText: {
    textAlign: 'center',
    fontSize: 12,
    color: '#8E8E93',
    marginTop: 16,
  },
});
