import React, { useEffect, useRef, useState } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  Dimensions,
  ScrollView,
  Animated,
  Image,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import { Feather } from '@expo/vector-icons';
import { api, getOrCreateUserId, setIntake, type IntakeData } from '@/services/api';
import { applyLanguage } from '@/i18n';

const { width, height } = Dimensions.get('window');

// Map onboarding selections to the backend's intake / persona shape
// (matches frontend/src/components/Onboarding/OnboardingForm and the
// `IntakeData` / `UserPersona` schemas in BackEnd/schemas).
const COUNTRY_CODE: Record<string, string> = {
  Egypt: 'egypt',
  'Saudi Arabia': 'saudi_arabia',
  Qatar: 'qatar',
  Turkey: 'turkey',
  Morocco: 'morocco',
  'Cairo (القاهرة)': 'egypt',
  'Alexandria (الإسكندرية)': 'egypt',
  'Luxor (الأقصر)': 'egypt',
  'Aswan (أسوان)': 'egypt',
  'Sharm El-Sheikh (شرم الشيخ)': 'egypt',
  'Hurghada (الغردقة)': 'egypt',
};
const TOURISM_TYPE: Record<string, IntakeData['tourism_type']> = {
  'Leisure & Exploration': 'standard',
  'Medical & Wellness Tourism': 'medical',
};
const COMPANIONS_TO_NUM: Record<string, number> = {
  'Single (فردية)': 1,
  'Couples (ثنائية)': 2,
  'Family/Group (أسرة)': 4,
};
const BUDGET_TO_USD: Record<string, number> = {
  Economy: 800,
  'Mid-Range': 2000,
  Luxury: 5000,
};

const STEPS = [
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
  const [step, setStep] = useState(1);
  const [direction, setDirection] = useState<'right' | 'left'>('right');

  const [persona, setPersona] = useState({
    destination: '',
    purpose: '',
    companions: '',
    budget: '',
    pace: '',
    dietary: '',
    language: 'en',
  });

  // ── Animated step transition (replaces MotiView) ────────────────────────
  const opacity = useRef(new Animated.Value(1)).current;
  const translateX = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    // Reset to start position then animate in
    opacity.setValue(0);
    translateX.setValue(direction === 'right' ? 40 : -40);
    Animated.parallel([
      Animated.timing(opacity, {
        toValue: 1,
        duration: 280,
        useNativeDriver: true,
      }),
      Animated.timing(translateX, {
        toValue: 0,
        duration: 280,
        useNativeDriver: true,
      }),
    ]).start();
  }, [step, direction]);

  // ── Animated pagination dots (replaces MotiView dots) ────────────────────
  const dotAnims = useRef(
    STEPS.map(() => new Animated.Value(8)),
  ).current;

  useEffect(() => {
    dotAnims.forEach((val, idx) => {
      Animated.spring(val, {
        toValue: step === idx + 1 ? 24 : 8,
        friction: 6,
        tension: 80,
        useNativeDriver: false,
      }).start();
    });
  }, [step, dotAnims]);

  const nextStep = async () => {
    if (step < 8) {
      setDirection('right');
      setStep(step + 1);
    } else {
      // Complete onboarding: persist intake locally and push persona to the
      // same backend the website writes to (POST /api/user/{user_id}/persona).
      try {
        const country = COUNTRY_CODE[persona.destination] ?? 'egypt';
        const tourism_type = TOURISM_TYPE[persona.purpose] ?? 'standard';
        const num_travelers = COMPANIONS_TO_NUM[persona.companions] ?? 2;
        const total_budget_usd = BUDGET_TO_USD[persona.budget] ?? 2000;

        await setIntake({ country, num_travelers, total_budget_usd, tourism_type });

        const uid = await getOrCreateUserId();
        await api
          .updatePersona(uid, {
            preferred_destination: persona.destination || country,
            party_size: num_travelers,
            tourism_type: tourism_type === 'medical' ? 'medical' : 'leisure',
            budget_bracket:
              persona.budget === 'Luxury'
                ? 'luxury'
                : persona.budget === 'Economy'
                ? 'economy'
                : 'mid_range',
            extras: {
              activity_level: persona.pace || undefined,
              dietary_preference: persona.dietary || undefined,
              language_preference: persona.language === 'ar' ? 'ar' : 'en',
            },
          })
          .catch((e) => {
            // Non-fatal: persona sync can fail offline; intake is still cached.
            // eslint-disable-next-line no-console
            console.warn('[onboarding] persona sync failed:', e?.message ?? e);
          });
      } catch (e) {
        // eslint-disable-next-line no-console
        console.warn('[onboarding] failed to persist intake:', e);
      }

      await applyLanguage(persona.language as 'ar' | 'en');
      router.replace('/(tabs)');
    }
  };

  const prevStep = () => {
    if (step > 1) {
      setDirection('left');
      setStep(step - 1);
    }
  };

  const renderOptions = (field: keyof typeof persona, options: string[], isVertical = false) => {
    return (
      <View style={[styles.optionsContainer, !isVertical && styles.optionsGrid]}>
        {options.map((opt) => {
          const isSelected = persona[field] === opt;
          return (
            <TouchableOpacity
              key={opt}
              style={[
                styles.optionCard,
                isSelected && styles.optionCardSelected,
                !isVertical && { width: '48%', marginBottom: 16 },
              ]}
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
  };

  const currentStepData = STEPS[step - 1];

  return (
    <View style={styles.container}>
      {/* Dynamic Background Gradient */}
      <LinearGradient
        colors={['#FFFFFF', '#F5F5F7']}
        style={StyleSheet.absoluteFill}
      />

      <SafeAreaView style={styles.safeArea}>
        {/* Header / Back Button */}
        <View style={styles.header}>
          {step > 1 ? (
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

        {/* Animated Step Content */}
        <Animated.View
          style={[
            styles.content,
            { opacity, transform: [{ translateX }] },
          ]}
        >
          {/* Icon Asset or 3D Image */}
          <View style={styles.assetContainer}>
            {step === 1 ? (
              <Image source={require('../assets/images/onboarding/auth_welcome_v2.png.png')} style={styles.transparentAssetImage} />
            ) : step === 3 ? (
              <Image source={require('../assets/images/onboarding/onboarding_q1_v2.png.png')} style={styles.transparentAssetImage} />
            ) : step === 4 ? (
              <Image source={require('../assets/images/onboarding/onboarding_q2_v2.png')} style={styles.transparentAssetImage} />
            ) : step === 5 ? (
              <Image source={require('../assets/images/onboarding/onboarding_q4_v2.png')} style={styles.transparentAssetImage} />
            ) : step === 6 ? (
              <Image source={require('../assets/images/onboarding/onboarding_pace.png')} style={styles.transparentAssetImage} />
            ) : step === 7 ? (
              <Image source={require('../assets/images/onboarding/onboarding_diet.png')} style={styles.transparentAssetImage} />
            ) : (
              <View style={styles.assetCircle}>
                <Feather
                  name={currentStepData.icon as any}
                  size={48}
                  color="#00A896"
                />
              </View>
            )}
          </View>

          <View style={styles.titleContainer}>
            {currentStepData.subtitle && (
              <Text style={styles.subtitle}>{currentStepData.subtitle}</Text>
            )}
            <Text style={styles.title}>{currentStepData.title}</Text>
          </View>

          <ScrollView
            contentContainerStyle={styles.scrollContent}
            showsVerticalScrollIndicator={false}
          >
            {step === 1 && (
              <View style={styles.step1Container}>
                <Text style={styles.bodyText}>
                  Welcome to TripMind. Experience the next generation of seamless,
                  AI-driven travel planning tailored exactly to your lifestyle.
                </Text>
              </View>
            )}

            {step === 2 &&
              renderOptions('destination', [
                'Cairo (القاهرة)',
                'Alexandria (الإسكندرية)',
                'Luxor (الأقصر)',
                'Aswan (أسوان)',
                'Sharm El-Sheikh (شرم الشيخ)',
                'Hurghada (الغردقة)',
              ])}

            {step === 3 &&
              renderOptions(
                'purpose',
                ['Leisure & Exploration', 'Medical & Wellness Tourism'],
                true,
              )}

            {step === 4 &&
              renderOptions('companions', ['Single (فردية)', 'Couples (ثنائية)', 'Family/Group (أسرة)'])}

            {step === 5 &&
              renderOptions('budget', ['Economy', 'Mid-Range', 'Luxury'], true)}

            {step === 6 &&
              renderOptions('pace', ['Relaxed', 'Moderate', 'High Energy'], true)}

            {step === 7 &&
              renderOptions('dietary', ['Halal Food (أكل حلال)', 'Vegan (نباتي)', 'No Restrictions (بدون قيود)'], true)}

            {step === 8 && (
              <View>
                {renderOptions('language', ['en', 'ar'], true)}
                <Text style={styles.langHelpText}>
                  {persona.language === 'ar'
                    ? 'سيتم تطبيق اللغة العربية من اليمين إلى اليسار'
                    : 'English LTR will be applied'}
                </Text>
              </View>
            )}
          </ScrollView>
        </Animated.View>

        {/* Footer: Pagination & CTA */}
        <View style={styles.footer}>
          {/* Animated Pagination Dots */}
          <View style={styles.pagination}>
            {STEPS.map((s, i) => (
              <Animated.View
                key={s.id}
                style={[
                  styles.dot,
                  {
                    width: dotAnims[i],
                    backgroundColor:
                      step === s.id ? '#00A896' : '#E2E8F0',
                  },
                ]}
              />
            ))}
          </View>

          <TouchableOpacity style={styles.continueButton} onPress={nextStep}>
            <LinearGradient
              colors={['#00A896', '#028090']}
              start={{ x: 0, y: 0 }}
              end={{ x: 1, y: 0 }}
              style={styles.continueGradient}
            >
              <Text style={styles.continueText}>
                {step === 1
                  ? 'Get Started'
                  : step === 8
                  ? 'Complete Setup'
                  : 'Continue'}
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
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 24,
    paddingTop: 16,
    height: 60,
  },
  backButton: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: 'rgba(0,0,0,0.03)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  skipText: { fontSize: 16, color: '#8E8E93', fontWeight: '500' },
  content: { flex: 1 },
  assetContainer: {
    alignItems: 'center',
    justifyContent: 'center',
    height: height * 0.22,
  },
  transparentAssetImage: {
    width: '90%',
    height: '100%',
    resizeMode: 'contain',
    backgroundColor: 'transparent',
  },
  assetCircle: {
    width: 120,
    height: 120,
    borderRadius: 60,
    backgroundColor: 'rgba(0, 168, 150, 0.1)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  titleContainer: { paddingHorizontal: 24, marginBottom: 24 },
  subtitle: {
    fontSize: 13,
    fontWeight: '700',
    color: '#00A896',
    textTransform: 'uppercase',
    letterSpacing: 1.2,
    marginBottom: 8,
  },
  title: {
    fontSize: 32,
    fontWeight: '800',
    color: '#1D1D1F',
    letterSpacing: -0.5,
  },
  scrollContent: { paddingHorizontal: 24, paddingBottom: 40 },
  bodyText: {
    fontSize: 16,
    color: '#8E8E93',
    lineHeight: 24,
    marginBottom: 32,
  },
  step1Container: { flex: 1 },
  oauthContainer: { gap: 16 },
  oauthButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#FFFFFF',
    padding: 18,
    borderRadius: 16,
    gap: 12,
    borderWidth: 1,
    borderColor: '#E5E5EA',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 8,
  },
  oauthText: { fontSize: 16, fontWeight: '600', color: '#1D1D1F' },
  optionsContainer: { gap: 12 },
  optionsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-between',
    gap: 0,
  },
  optionCard: {
    backgroundColor: '#FFFFFF',
    padding: 16,
    borderRadius: 20,
    borderWidth: 2,
    borderColor: 'transparent',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.05,
    shadowRadius: 10,
    position: 'relative',
  },
  optionCardSelected: {
    borderColor: '#00A896',
    backgroundColor: '#F0FDFA',
  },
  optionCheck: {
    position: 'absolute',
    top: 12,
    right: 12,
    width: 20,
    height: 20,
    borderRadius: 10,
    backgroundColor: '#00A896',
    alignItems: 'center',
    justifyContent: 'center',
  },
  optionText: { fontSize: 16, fontWeight: '600', color: '#8E8E93' },
  optionTextSelected: { color: '#00A896', fontWeight: '700' },
  langHelpText: {
    marginTop: 16,
    textAlign: 'center',
    color: '#8E8E93',
    fontSize: 14,
  },
  footer: {
    paddingHorizontal: 24,
    paddingBottom: 24,
    paddingTop: 16,
    backgroundColor: 'transparent',
  },
  pagination: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    gap: 6,
    marginBottom: 24,
  },
  dot: { height: 8, borderRadius: 4 },
  continueButton: {
    overflow: 'hidden',
    borderRadius: 20,
    shadowColor: '#00A896',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.3,
    shadowRadius: 16,
  },
  continueGradient: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 18,
    gap: 12,
  },
  continueText: { color: '#FFFFFF', fontSize: 18, fontWeight: '700' },
});
