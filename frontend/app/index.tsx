import { useState, useEffect } from 'react';
import { View, ActivityIndicator, StyleSheet } from 'react-native';
import { useAuth } from '@/hooks/useAuth';
import { Redirect } from 'expo-router';
import { api, getOrCreateUserId } from '@/services/api';

/**
 * Entry point — decides where to send the user:
 *   • Not authenticated → /onboarding (starts with sign-in/up)
 *   • Authenticated + has persona → /(tabs)
 *   • Authenticated + no persona → /onboarding (skips auth step)
 */
export default function EntryScreen() {
  const { user, loading, isAuthed, isGuest } = useAuth();

  const [checkingPersona, setCheckingPersona] = useState(false);
  const [hasPersona, setHasPersona] = useState<boolean | null>(null);

  useEffect(() => {
    if (isAuthed) {
      let isMounted = true;
      const checkPersona = async () => {
        setCheckingPersona(true);
        try {
          const uid = user?.uid ?? (await getOrCreateUserId());
          const p = await api.getPersona(uid);
          if (isMounted) setHasPersona(!!p?.preferred_destination);
        } catch {
          if (isMounted) setHasPersona(false);
        } finally {
          if (isMounted) setCheckingPersona(false);
        }
      };
      checkPersona();
      return () => { isMounted = false; };
    }
  }, [isAuthed, user]);

  // Still loading auth state
  if (loading || checkingPersona) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#00A896" />
      </View>
    );
  }

  // Not authenticated at all → send to onboarding (which starts with sign-in/up)
  if (!isAuthed) {
    return <Redirect href="/onboarding" />;
  }

  // Authenticated but no persona → onboarding (will skip auth step automatically)
  if (hasPersona === false) {
    return <Redirect href="/onboarding" />;
  }

  // Authenticated + has persona → main app
  if (hasPersona === true) {
    return <Redirect href="/(tabs)" />;
  }

  // Still resolving
  return (
    <View style={styles.center}>
      <ActivityIndicator size="large" color="#00A896" />
    </View>
  );
}

const styles = StyleSheet.create({
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#FAFAFA',
  },
});
