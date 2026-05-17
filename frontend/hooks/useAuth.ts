/**
 * Tripmind auth hook — wraps Firebase + expo-auth-session Google Sign-In.
 *
 * Safe in dev: if Google OAuth client IDs aren't yet configured, the hook
 * still mounts and returns a `notConfigured` flag instead of throwing,
 * so the rest of the UI is still usable.
 *
 * Usage:
 *   const { user, loading, signInWithGoogle, signOut, notConfigured } = useAuth();
 */

import { useEffect, useState, useCallback } from 'react';
import * as Google from 'expo-auth-session/providers/google';
import * as WebBrowser from 'expo-web-browser';
import { Platform } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { onAuthStateChanged, signOut as fbSignOut, type User } from 'firebase/auth';
import {
  auth,
  signInWithGoogleIdToken,
  signInWithEmail as fbSignInWithEmail,
  signUpWithEmail as fbSignUpWithEmail,
} from '@/config/firebaseConfig';

WebBrowser.maybeCompleteAuthSession();

const GUEST_FLAG_KEY = 'tripmind_guest_mode';

/** Feature limits applied to guest accounts. */
export const GUEST_LIMITS = {
  maxChatMessagesPerSession: 3,
  canEditProfile: false,
  canSyncPersonaToBackend: false,
} as const;

// Placeholder used to keep `useIdTokenAuthRequest` from throwing during the
// hook call when a real OAuth client ID hasn't been configured yet.
const PLACEHOLDER = 'placeholder.apps.googleusercontent.com';

const webId = process.env.EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID || '';
const iosId = process.env.EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID || '';
const androidId = process.env.EXPO_PUBLIC_GOOGLE_ANDROID_CLIENT_ID || '';

// Configured if the relevant platform's client ID is set.
const platformConfigured =
  Platform.OS === 'ios'
    ? !!iosId
    : Platform.OS === 'android'
    ? !!androidId
    : !!webId;

export function useAuth() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [isGuest, setIsGuest] = useState(false);

  const [, response, promptAsync] = Google.useIdTokenAuthRequest({
    clientId: webId || PLACEHOLDER,
    iosClientId: iosId || PLACEHOLDER,
    androidClientId: androidId || PLACEHOLDER,
  });

  // Restore previously-stored guest flag so the app remembers the choice
  // across reloads (until the user signs in or signs out).
  useEffect(() => {
    AsyncStorage.getItem(GUEST_FLAG_KEY)
      .then((v) => {
        if (v === '1') setIsGuest(true);
      })
      .catch(() => {
        /* non-fatal */
      });
  }, []);

  useEffect(() => {
    try {
      const unsub = onAuthStateChanged(auth, (u) => {
        setUser(u);
        // A real Firebase user always overrides guest mode.
        if (u) {
          setIsGuest(false);
          AsyncStorage.removeItem(GUEST_FLAG_KEY).catch(() => {});
        }
        setLoading(false);
      });
      return unsub;
    } catch (e) {
      // Firebase auth not initialised — stay in loading=false, user=null
      // eslint-disable-next-line no-console
      console.warn('[useAuth] auth state subscription failed:', e);
      setLoading(false);
      return undefined;
    }
  }, []);

  const continueAsGuest = useCallback(async () => {
    try {
      await AsyncStorage.setItem(GUEST_FLAG_KEY, '1');
    } catch {
      /* non-fatal */
    }
    setIsGuest(true);
  }, []);

  useEffect(() => {
    if (response?.type === 'success' && response.params.id_token) {
      signInWithGoogleIdToken(response.params.id_token).catch((e) =>
        // eslint-disable-next-line no-console
        console.warn('[useAuth] Firebase sign-in failed:', e),
      );
    }
  }, [response]);

  const signInWithGoogle = useCallback(() => {
    if (!platformConfigured) {
      // eslint-disable-next-line no-console
      console.warn(
        '[useAuth] Google OAuth client ID not configured for ' +
          Platform.OS +
          '. Set EXPO_PUBLIC_GOOGLE_' +
          (Platform.OS === 'ios'
            ? 'IOS'
            : Platform.OS === 'android'
            ? 'ANDROID'
            : 'WEB') +
          '_CLIENT_ID in mobile/.env',
      );
      return Promise.resolve({ type: 'dismiss' as const });
    }
    return promptAsync();
  }, [promptAsync]);

  const signOut = useCallback(async () => {
    setIsGuest(false);
    try {
      await AsyncStorage.removeItem(GUEST_FLAG_KEY);
    } catch {
      /* non-fatal */
    }
    try {
      await fbSignOut(auth);
    } catch {
      /* ignore */
    }
  }, []);

  const signInWithEmail = useCallback(
    (email: string, password: string) => fbSignInWithEmail(email, password),
    [],
  );

  const signUpWithEmail = useCallback(
    (email: string, password: string) => fbSignUpWithEmail(email, password),
    [],
  );

  return {
    user,
    loading,
    isGuest,
    /** True if either a real user is signed in OR guest mode is active. */
    isAuthed: !!user || isGuest,
    continueAsGuest,
    signInWithGoogle,
    signInWithEmail,
    signUpWithEmail,
    signOut,
    notConfigured: !platformConfigured,
  };
}
