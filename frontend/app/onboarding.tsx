import React, { useEffect, useRef, useState } from 'react';
import {
  View, Text, TouchableOpacity, StyleSheet, Dimensions,
  ScrollView, Animated, TextInput, ActivityIndicator, Platform,
} from 'react-native';
import { Image } from 'expo-image';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import { Feather, FontAwesome } from '@expo/vector-icons';
import { api, getOrCreateUserId, setIntake, type IntakeData } from '@/services/api';
import { applyLanguage } from '@/i18n';
import { useAuth } from '@/hooks/useAuth';
import { prefetchDestinationImages, DESTINATION_WIKI_TITLES, getWikipediaImage } from '@/services/wikipedia';
import { EGYPT_GOVERNORATES, COUNTRY_CODE } from '@/constants/Governorates';
import { SURFACE, BORDER_COLOR, PRIMARY, PRIMARY_DARK, MUTED, PLACEHOLDER, ERROR, RADIUS_SM, flatCard, flatInput } from '@/theme/tokens';

const { width, height } = Dimensions.get('window');
const TOURISM_TYPE: Record<string, IntakeData['tourism_type']> = {
  'Leisure & Exploration': 'standard', 'Medical & Wellness Tourism': 'medical',
};
const COMPANIONS_TO_NUM: Record<string, number> = {
  'Single (فردية)': 1, 'Couples (ثنائية)': 2, 'Family/Group (أسرة)': 4,
};
const BUDGET_TO_USD: Record<string, number> = {
  Economy: 800, 'Mid-Range': 2000, Luxury: 5000,
};

const DESTINATIONS = EGYPT_GOVERNORATES;

// Steps: 0=auth, 1=welcome, 2=destination, 3=purpose, 4=companions, 5=budget, 6=pace, 7=dietary, 8=language
const STEPS = [
  { id: 0, title: 'Welcome to Touri', icon: 'user' },
  { id: 1, title: 'Your personal AI Travel Coach', icon: 'globe' },
  { id: 2, title: 'Where to next?', subtitle: 'Target Destination', icon: 'map-pin' },
  { id: 3, title: 'Define your style', subtitle: 'Travel Purpose', icon: 'camera' },
  { id: 4, title: 'Who is joining?', subtitle: 'Companionship', icon: 'users' },
  { id: 5, title: 'Set your budget range', subtitle: 'Financial Class', icon: 'pie-chart' },
  { id: 6, title: 'Select your daily pace', subtitle: 'Pace & Activity', icon: 'activity' },
  { id: 7, title: 'Dietary Preferences', subtitle: 'Food Requirements', icon: 'coffee' },
  { id: 8, title: 'Choose your UI language', subtitle: 'Language Preference', icon: 'type' },
];

export default function OnboardingScreen() {
  const router = useRouter();
  const { user, isAuthed, isGuest, continueAsGuest, signInWithGoogle, signInWithEmail, signUpWithEmail, notConfigured } = useAuth();

  // If user is already authenticated, skip auth step (step 0) → start at step 1
  const initialStep = isAuthed ? 1 : 0;
  const [step, setStep] = useState(initialStep);
  const [direction, setDirection] = useState<'right' | 'left'>('right');

  // Auth state
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [authMode, setAuthMode] = useState<'signin' | 'signup'>('signin');
  const [authBusy, setAuthBusy] = useState(false);
  const [authErr, setAuthErr] = useState<string | null>(null);

  // Wikipedia images for destinations
  const [wikiImages, setWikiImages] = useState<Record<string, string>>({});

  const [persona, setPersona] = useState({
    destination: '', purpose: '', companions: '',
    budget: '', pace: '', dietary: '', language: 'en',
  });

  // Prefetch Wikipedia images on mount
  useEffect(() => {
    prefetchDestinationImages().then(setWikiImages).catch(() => {});
  }, []);

  // When user authenticates at step 0, check if they already have a persona.
  // Existing users (signin) → go straight to app. New users (signup) → continue onboarding.
  useEffect(() => {
    if (isAuthed && step === 0) {
      const checkAndRoute = async () => {
        try {
          const uid = user?.uid ?? (await getOrCreateUserId());
          const p = await api.getPersona(uid).catch(() => null);
          if (p?.preferred_destination) {
            router.replace('/(tabs)');
            return;
          }
        } catch {
          /* continue to onboarding if check fails */
        }
        setDirection('right');
        setStep(1);
      };
      checkAndRoute();
    }
  }, [isAuthed, step]);

  // Animation
  const opacity = useRef(new Animated.Value(1)).current;
  const translateX = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    opacity.setValue(0);
    translateX.setValue(direction === 'right' ? 40 : -40);
    Animated.parallel([
      Animated.timing(opacity, { toValue: 1, duration: 280, useNativeDriver: true }),
      Animated.timing(translateX, { toValue: 0, duration: 280, useNativeDriver: true }),
    ]).start();
  }, [step, direction]);

  // Dots (only show for steps 1–8)
  const visibleSteps = STEPS.slice(1);
  const dotAnims = useRef(visibleSteps.map(() => new Animated.Value(8))).current;
  useEffect(() => {
    dotAnims.forEach((val, idx) => {
      Animated.spring(val, {
        toValue: step === idx + 1 ? 24 : 8,
        friction: 6, tension: 80, useNativeDriver: false,
      }).start();
    });
  }, [step, dotAnims]);

  const handleEmailAuth = async () => {
    if (!email.trim() || !password) { setAuthErr('Email and password are required.'); return; }
    setAuthBusy(true); setAuthErr(null);
    try {
      if (authMode === 'signin') await signInWithEmail(email, password);
      else await signUpWithEmail(email, password);
    } catch (e: any) {
      setAuthErr(e?.message ?? 'Authentication failed.');
    } finally { setAuthBusy(false); }
  };

  const handleGuestContinue = async () => {
    await continueAsGuest();
  };

  const nextStep = async () => {
    if (step < 8) {
      setDirection('right');
      setStep(step + 1);
    } else {
      try {
        const country = COUNTRY_CODE[persona.destination] ?? 'egypt';
        const tourism_type = TOURISM_TYPE[persona.purpose] ?? 'standard';
        const num_travelers = COMPANIONS_TO_NUM[persona.companions] ?? 2;
        const total_budget_usd = BUDGET_TO_USD[persona.budget] ?? 2000;
        await setIntake({ country, num_travelers, total_budget_usd, tourism_type });
        const uid = user?.uid ?? (await getOrCreateUserId());
        await api.updatePersona(uid, {
          preferred_destination: persona.destination || country,
          party_size: num_travelers,
          tourism_type: tourism_type === 'medical' ? 'medical' : 'leisure',
          budget_bracket: persona.budget === 'Luxury' ? 'luxury' : persona.budget === 'Economy' ? 'economy' : 'mid_range',
          extras: {
            activity_level: persona.pace || undefined,
            dietary_preference: persona.dietary || undefined,
            language_preference: persona.language === 'ar' ? 'ar' : 'en',
          },
        }).catch((e) => console.warn('[onboarding] persona sync failed:', e?.message ?? e));
      } catch (e) { console.warn('[onboarding] failed to persist intake:', e); }
      await applyLanguage(persona.language as 'ar' | 'en');
      router.replace('/(tabs)');
    }
  };

  const prevStep = () => {
    if (step > (isAuthed ? 1 : 0)) {
      setDirection('left');
      setStep(step - 1);
    }
  };

  const renderOptions = (field: keyof typeof persona, options: string[], isVertical = false) => (
    <View style={[styles.optionsContainer, !isVertical && styles.optionsGrid]}>
      {options.map((opt) => {
        const isSelected = persona[field] === opt;
        return (
          <TouchableOpacity
            key={opt}
            style={[styles.optionCard, isSelected && styles.optionCardSelected, !isVertical && { width: '48%', marginBottom: 16 }]}
            onPress={() => setPersona({ ...persona, [field]: opt })}
          >
            {isSelected && (
              <View style={styles.optionCheck}>
                <Feather name="check" size={14} color="#fff" />
              </View>
            )}
            <Text style={[styles.optionText, isSelected && styles.optionTextSelected]}>{opt}</Text>
          </TouchableOpacity>
        );
      })}
    </View>
  );

  const renderDestinationCards = () => (
    <View style={styles.destGrid}>
      {DESTINATIONS.map((dest) => {
        const isSelected = persona.destination === dest;
        const wikiTitle = DESTINATION_WIKI_TITLES[dest];
        const imgUri = wikiImages[dest] || undefined;
        return (
          <TouchableOpacity
            key={dest}
            style={[styles.destCard, isSelected && styles.destCardSelected]}
            onPress={() => setPersona({ ...persona, destination: dest })}
            activeOpacity={0.85}
          >
            <View style={styles.destImgWrap}>
              {imgUri ? (
                <Image source={{ uri: imgUri }} style={styles.destImg} contentFit="cover" transition={300} cachePolicy="memory-disk" />
              ) : (
                <View style={[styles.destImg, { backgroundColor: '#E8E8ED', alignItems: 'center', justifyContent: 'center' }]}>
                  <Feather name="image" size={20} color={PLACEHOLDER} />
                </View>
              )}
              <LinearGradient colors={['transparent', 'rgba(0,0,0,0.55)']} style={styles.destGrad}>
                <Text style={styles.destLabel}>{dest}</Text>
              </LinearGradient>
              {isSelected && (
                <View style={styles.destCheck}>
                  <Feather name="check" size={14} color="#fff" />
                </View>
              )}
            </View>
          </TouchableOpacity>
        );
      })}
    </View>
  );

  const currentStepData = STEPS[step];
  const canGoBack = step > (isAuthed ? 1 : 0);

  // Disable Continue until the required field for that step is filled
  const canContinue = (() => {
    if (step === 2) return !!persona.destination;
    if (step === 3) return !!persona.purpose;
    if (step === 4) return !!persona.companions;
    if (step === 5) return !!persona.budget;
    if (step === 6) return !!persona.pace;
    if (step === 7) return !!persona.dietary;
    return true;
  })();

  // ── Auth step (step 0) ──────────────────────────────────────────────────────
  if (step === 0) {
    return (
      <View style={styles.container}>
        <LinearGradient colors={['#FFFFFF', '#F5F5F7']} style={StyleSheet.absoluteFill} />
        <SafeAreaView style={styles.safeArea}>
          <View style={styles.header}>
            <View style={{ width: 44 }} />
            <TouchableOpacity onPress={handleGuestContinue}>
              <Text style={styles.skipText}>Skip</Text>
            </TouchableOpacity>
          </View>

          <ScrollView contentContainerStyle={styles.authScrollContent} showsVerticalScrollIndicator={false} bounces={false}>
            <View style={styles.authAssetContainer}>
              <Image source={require('../assets/images/onboarding/auth_welcome_v2.png.png')} style={styles.transparentAssetImage} contentFit="contain" transition={200} cachePolicy="memory-disk" />
            </View>

            <View style={styles.authTitleContainer}>
              <Text style={styles.authTitle}>
                {authMode === 'signin' ? 'Welcome Back' : 'Create Account'}
              </Text>
              <Text style={styles.authSubtitle}>
                {authMode === 'signin'
                  ? 'Sign in to continue your travel journey'
                  : 'Join Touri for personalized AI travel planning'}
              </Text>
            </View>

            {authErr && <Text style={styles.errorText}>{authErr}</Text>}

            <View style={styles.authInputContainer}>
              <View style={styles.inputWrapper}>
                <Feather name="mail" size={18} color={MUTED} style={{ marginRight: 10 }} />
                <TextInput
                  style={styles.authInput}
                  placeholder="Email address"
                  placeholderTextColor={MUTED}
                  autoCapitalize="none"
                  keyboardType="email-address"
                  value={email}
                  onChangeText={setEmail}
                />
              </View>
              <View style={styles.inputWrapper}>
                <Feather name="lock" size={18} color={MUTED} style={{ marginRight: 10 }} />
                <TextInput
                  style={styles.authInput}
                  placeholder="Password"
                  placeholderTextColor={MUTED}
                  secureTextEntry
                  value={password}
                  onChangeText={setPassword}
                />
              </View>
            </View>

            <TouchableOpacity style={styles.emailButton} onPress={handleEmailAuth} disabled={authBusy}>
              <LinearGradient colors={[PRIMARY, PRIMARY_DARK]} start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }} style={styles.emailButtonGrad}>
                {authBusy ? (
                  <ActivityIndicator color="#fff" />
                ) : (
                  <Text style={styles.emailButtonText}>
                    {authMode === 'signin' ? 'Sign In' : 'Create Account'}
                  </Text>
                )}
              </LinearGradient>
            </TouchableOpacity>

            <TouchableOpacity onPress={() => { setAuthMode(m => m === 'signin' ? 'signup' : 'signin'); setAuthErr(null); }}>
              <Text style={styles.switchModeText}>
                {authMode === 'signin' ? "Don't have an account? Sign Up" : 'Already have an account? Sign In'}
              </Text>
            </TouchableOpacity>

            <View style={styles.dividerContainer}>
              <View style={styles.dividerLine} />
              <Text style={styles.dividerText}>OR</Text>
              <View style={styles.dividerLine} />
            </View>

            <TouchableOpacity
              style={[styles.socialButton, notConfigured && { opacity: 0.5 }]}
              onPress={signInWithGoogle}
              disabled={notConfigured}
            >
              <FontAwesome name="google" size={18} color="#1A1C1E" />
              <Text style={styles.socialButtonText}>Continue with Google</Text>
            </TouchableOpacity>

            <TouchableOpacity style={[styles.socialButton, { backgroundColor: '#1A1C1E' }]} onPress={handleGuestContinue}>
              <Feather name="user" size={18} color="#fff" />
              <Text style={[styles.socialButtonText, { color: '#fff' }]}>Continue as Guest</Text>
            </TouchableOpacity>

            <Text style={styles.termsText}>Terms of Use (EULA) & Privacy Policy</Text>
          </ScrollView>
        </SafeAreaView>
      </View>
    );
  }

  // ── Onboarding steps 1–8 ────────────────────────────────────────────────────
  return (
    <View style={styles.container}>
      <LinearGradient colors={['#FFFFFF', '#F5F5F7']} style={StyleSheet.absoluteFill} />
      <SafeAreaView style={styles.safeArea}>
        <View style={styles.header}>
          {canGoBack ? (
            <TouchableOpacity onPress={prevStep} style={styles.backButton}>
              <Feather name="arrow-left" size={24} color="#1D1D1F" />
            </TouchableOpacity>
          ) : (
            <View style={{ width: 44 }} />
          )}
          <TouchableOpacity onPress={() => router.replace('/(tabs)')}>
            <Text style={styles.skipText}>Skip</Text>
          </TouchableOpacity>
        </View>

        <Animated.View style={[styles.content, { opacity, transform: [{ translateX }] }]}>
          <View style={styles.assetContainer}>
            {step === 1 ? (
              <Image source={require('../assets/images/onboarding/auth_welcome_v2.png.png')} style={styles.transparentAssetImage} contentFit="contain" transition={200} cachePolicy="memory-disk" />
            ) : step === 3 ? (
              <Image source={require('../assets/images/onboarding/onboarding_q1_v2.png.png')} style={styles.transparentAssetImage} contentFit="contain" transition={200} cachePolicy="memory-disk" />
            ) : step === 4 ? (
              <Image source={require('../assets/images/onboarding/onboarding_q2_v2.png')} style={styles.transparentAssetImage} contentFit="contain" transition={200} cachePolicy="memory-disk" />
            ) : step === 5 ? (
              <Image source={require('../assets/images/onboarding/onboarding_q4_v2.png')} style={styles.transparentAssetImage} contentFit="contain" transition={200} cachePolicy="memory-disk" />
            ) : step === 6 ? (
              <Image source={require('../assets/images/onboarding/onboarding_pace.png')} style={styles.transparentAssetImage} contentFit="contain" transition={200} cachePolicy="memory-disk" />
            ) : step === 7 ? (
              <Image source={require('../assets/images/onboarding/onboarding_diet.png')} style={styles.transparentAssetImage} contentFit="contain" transition={200} cachePolicy="memory-disk" />
            ) : step === 2 ? null : (
              <View style={styles.assetCircle}>
                <Feather name={currentStepData.icon as any} size={48} color={PRIMARY} />
              </View>
            )}
          </View>

          <View style={styles.titleContainer}>
            {currentStepData.subtitle && <Text style={styles.subtitle}>{currentStepData.subtitle}</Text>}
            <Text style={styles.title}>{currentStepData.title}</Text>
          </View>

          <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
            {step === 1 && (
              <View style={styles.step1Container}>
                <Text style={styles.bodyText}>
                  Welcome to Touri. Experience the next generation of seamless,
                  AI-driven travel planning tailored exactly to your lifestyle.
                </Text>
              </View>
            )}
            {step === 2 && renderDestinationCards()}
            {step === 3 && renderOptions('purpose', ['Leisure & Exploration', 'Medical & Wellness Tourism'], true)}
            {step === 4 && renderOptions('companions', ['Single (فردية)', 'Couples (ثنائية)', 'Family/Group (أسرة)'])}
            {step === 5 && renderOptions('budget', ['Economy', 'Mid-Range', 'Luxury'], true)}
            {step === 6 && renderOptions('pace', ['Relaxed', 'Moderate', 'High Energy'], true)}
            {step === 7 && renderOptions('dietary', ['Halal Food (أكل حلال)', 'Vegan (نباتي)', 'No Restrictions (بدون قيود)'], true)}
            {step === 8 && (
              <View>
                {renderOptions('language', ['en', 'ar'], true)}
                <Text style={styles.langHelpText}>
                  {persona.language === 'ar' ? 'سيتم تطبيق اللغة العربية من اليمين إلى اليسار' : 'English LTR will be applied'}
                </Text>
              </View>
            )}
          </ScrollView>
        </Animated.View>

        <View style={styles.footer}>
          <View style={styles.pagination}>
            {visibleSteps.map((s, i) => (
              <Animated.View
                key={s.id}
                style={[styles.dot, { width: dotAnims[i], backgroundColor: step === s.id ? PRIMARY : '#E2E8F0' }]}
              />
            ))}
          </View>
          <TouchableOpacity
            style={[styles.continueButton, !canContinue && styles.continueButtonDisabled]}
            onPress={nextStep}
            disabled={!canContinue}
          >
            <LinearGradient
              colors={canContinue ? [PRIMARY, PRIMARY_DARK] : [PLACEHOLDER, PLACEHOLDER]}
              start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }}
              style={styles.continueGradient}
            >
              <Text style={styles.continueText}>
                {step === 1 ? 'Get Started' : step === 8 ? 'Complete Setup' : 'Continue'}
              </Text>
              <Feather name="arrow-right" size={20} color="#fff" />
            </LinearGradient>
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F5F5F7' },
  safeArea: { flex: 1 },
  header: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    paddingHorizontal: 24, paddingTop: 16, height: 60,
  },
  backButton: {
    width: 44, height: 44, borderRadius: 22, backgroundColor: 'rgba(0,0,0,0.03)',
    alignItems: 'center', justifyContent: 'center',
  },
  skipText: { fontSize: 16, color: MUTED, fontWeight: '500' },
  content: { flex: 1 },
  assetContainer: { alignItems: 'center', justifyContent: 'center', height: height * 0.22 },
  transparentAssetImage: { width: '90%', height: '100%', backgroundColor: 'transparent' },
  assetCircle: {
    width: 120, height: 120, borderRadius: 60, backgroundColor: 'rgba(0,168,150,0.1)',
    alignItems: 'center', justifyContent: 'center',
  },
  titleContainer: { paddingHorizontal: 24, marginBottom: 24 },
  subtitle: {
    fontSize: 13, fontWeight: '700', color: PRIMARY, textTransform: 'uppercase',
    letterSpacing: 1.2, marginBottom: 8,
  },
  title: { fontSize: 32, fontWeight: '800', color: '#1D1D1F', letterSpacing: -0.5 },
  scrollContent: { paddingHorizontal: 24, paddingBottom: 40 },
  bodyText: { fontSize: 16, color: MUTED, lineHeight: 24, marginBottom: 32 },
  step1Container: { flex: 1 },
  optionsContainer: { gap: 12 },
  optionsGrid: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'space-between', gap: 0 },
  optionCard: {
    backgroundColor: SURFACE, padding: 16, borderRadius: 20, borderWidth: 2,
    borderColor: BORDER_COLOR, position: 'relative',
  },
  optionCardSelected: { borderColor: PRIMARY, backgroundColor: '#F0FDFA' },
  optionCheck: {
    position: 'absolute', top: 12, right: 12, width: 20, height: 20,
    borderRadius: RADIUS_SM, backgroundColor: PRIMARY, alignItems: 'center', justifyContent: 'center',
  },
  optionText: { fontSize: 16, fontWeight: '600', color: MUTED },
  optionTextSelected: { color: PRIMARY, fontWeight: '700' },
  langHelpText: { marginTop: 16, textAlign: 'center', color: MUTED, fontSize: 14 },
  footer: { paddingHorizontal: 24, paddingBottom: 24, paddingTop: 16, backgroundColor: 'transparent' },
  pagination: { flexDirection: 'row', justifyContent: 'center', alignItems: 'center', gap: 6, marginBottom: 24 },
  dot: { height: 8, borderRadius: 4 },
  continueButton: {
    overflow: 'hidden', borderRadius: 20,
  },
  continueButtonDisabled: { opacity: 0.6 },
  continueGradient: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    paddingVertical: 18, gap: 12,
  },
  continueText: { color: '#FFFFFF', fontSize: 18, fontWeight: '700' },

  // ── Destination cards with Wikipedia images ──
  destGrid: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'space-between', gap: 12 },
  destCard: {
    ...flatCard,
    width: '48%', overflow: 'hidden', borderWidth: 2,
  },
  destCardSelected: { borderColor: PRIMARY },
  destImgWrap: { width: '100%', height: 120, position: 'relative' },
  destImg: { width: '100%', height: '100%' },
  destGrad: {
    position: 'absolute', bottom: 0, left: 0, right: 0, height: 60,
    justifyContent: 'flex-end', padding: 10,
  },
  destLabel: { color: '#fff', fontSize: 13, fontWeight: '700' },
  destCheck: {
    position: 'absolute', top: 8, right: 8, width: 24, height: 24,
    borderRadius: 12, backgroundColor: PRIMARY, alignItems: 'center', justifyContent: 'center',
  },

  // ── Auth step styles ──
  authScrollContent: { paddingHorizontal: 24, paddingBottom: 40 },
  authAssetContainer: { alignItems: 'center', justifyContent: 'center', height: height * 0.2, marginBottom: 8 },
  authTitleContainer: { marginBottom: 24 },
  authTitle: { fontSize: 28, fontWeight: '800', color: '#1D1D1F', letterSpacing: -0.5, marginBottom: 8 },
  authSubtitle: { fontSize: 15, color: MUTED, lineHeight: 22 },
  errorText: { color: ERROR, fontSize: 14, marginBottom: 12, textAlign: 'center' },
  authInputContainer: { gap: 12, marginBottom: 20 },
  inputWrapper: {
    ...flatInput,
    flexDirection: 'row', alignItems: 'center', backgroundColor: '#F5F5F7',
    paddingHorizontal: 16,
  },
  authInput: { flex: 1, paddingVertical: 14, fontSize: 15, color: '#1D1D1F' },
  emailButton: { borderRadius: 20, overflow: 'hidden', marginBottom: 16 },
  emailButtonGrad: { paddingVertical: 16, alignItems: 'center', justifyContent: 'center' },
  emailButtonText: { color: '#fff', fontSize: 16, fontWeight: '700' },
  switchModeText: { color: PRIMARY, fontSize: 14, fontWeight: '600', textAlign: 'center', marginBottom: 20 },
  dividerContainer: { flexDirection: 'row', alignItems: 'center', marginBottom: 20 },
  dividerLine: { flex: 1, height: 1, backgroundColor: BORDER_COLOR },
  dividerText: { color: MUTED, marginHorizontal: 12, fontSize: 12, fontWeight: '600' },
  socialButton: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    backgroundColor: SURFACE, paddingVertical: 16, borderRadius: 20, marginBottom: 12,
    gap: 10, borderWidth: 1, borderColor: BORDER_COLOR,
  },
  socialButtonText: { fontSize: 15, fontWeight: '600', color: '#1D1D1F' },
  termsText: { textAlign: 'center', fontSize: 12, color: MUTED, marginTop: 12 },
});
