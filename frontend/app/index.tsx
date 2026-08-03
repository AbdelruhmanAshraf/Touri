import { View, ActivityIndicator, StyleSheet } from 'react-native';
import { useAuth } from '@/hooks/useAuth';
import { useProfile } from '@/hooks/useProfile';
import { Redirect } from 'expo-router';

/**
 * Entry point — decides where to send the user:
 *   • Not authenticated → /onboarding (sign-in/up screen)
 *   • Authenticated + onboarding_completed === true → /(tabs)
 *   • Authenticated + onboarding_completed !== true → /onboarding
 *
 * Route decision is instant when AsyncStorage cache is warm (returning users).
 * For fresh installs Firestore is checked in the background by useProfile.
 */
export default function EntryScreen() {
  const { user, loading } = useAuth();
  const { onboardingCompleted } = useProfile(user ?? null);

  if (loading || onboardingCompleted === null) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#00A896" />
      </View>
    );
  }

  if (!user) {
    return <Redirect href="/onboarding" />;
  }

  if (onboardingCompleted) {
    return <Redirect href="/(tabs)" />;
  }

  return <Redirect href="/onboarding" />;
}

const styles = StyleSheet.create({
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#FAFAFA',
  },
});
