/**
 * Touri auth hook wraps Firebase + expo-auth-session Google Sign-In.
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
import { useRouter } from 'expo-router';
import { onAuthStateChanged, signOut as fbSignOut, type User } from 'firebase/auth';
import {
  auth,
  signInWithGoogleIdToken,
  signInWithEmail as fbSignInWithEmail,
  signUpWithEmail as fbSignUpWithEmail,
  signInAnonymously as fbSignInAnonymously,
} from '@/config/firebaseConfig';
import { api, clearSessionTokens, clearAllLocalData } from '@/services/api';

WebBrowser.maybeCompleteAuthSession();

// Module-level session deduplication
// useAuth() is called in every tab/screen, creating multiple onAuthStateChanged
// listeners. Without dedup, each listener fires startSession concurrently,
// instantly exceeding the backend's 5 req/min AUTH_LIMIT and returning 429.
// This cache ensures startSession is called at most once per Firebase uid.
let _sessionCache: { uid: string; promise: Promise<void> } | null = null;

function _startSessionOnce(
  uid: string,
  getIdToken: () => Promise<string>,
): Promise<void> {
  if (_sessionCache?.uid === uid) return _sessionCache.promise;
  const promise = (async () => {
    const idToken = await getIdToken();
    await api.startSession({ id_token: idToken });
  })().catch((e) => {
    console.warn('[useAuth] startSession failed:', e);
    if (_sessionCache?.uid === uid) _sessionCache = null;
  });
  _sessionCache = { uid, promise };
  return promise;
}

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

const ONBOARDING_KEY = 'touri_onboarded';

export function useAuth() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [isGuest, setIsGuest] = useState(false);
  const [authError, setAuthError] = useState<string | null>(null);

  const [, response, promptAsync] = Google.useIdTokenAuthRequest({
    clientId: webId || PLACEHOLDER,
    iosClientId: iosId || PLACEHOLDER,
    androidClientId: androidId || PLACEHOLDER,
  });

  useEffect(() => {
    try {
      const unsub = onAuthStateChanged(auth, async (u) => {
        setUser(u);
        if (u) {
          setIsGuest(u.isAnonymous);
          // Phase 5: hand the Firebase ID token to the backend so it can mint
          // HTTP-only access + refresh cookies and store the access JWT in
          // expo-secure-store. Failure is non-fatal in dev.
          await _startSessionOnce(u.uid, () => u.getIdToken(/* forceRefresh */ false));
        } else {
          setIsGuest(false);
          await clearSessionTokens().catch(() => {});
        }
        setLoading(false);
      });
      return unsub;
    } catch (e) {
      // Firebase auth not initialised; stay in loading=false, user=null
      const errMsg = e instanceof Error ? e.message : String(e);
      setAuthError(errMsg);
      // eslint-disable-next-line no-console
      console.warn('[useAuth] auth state subscription failed:', e);
      setLoading(false);
      return undefined;
    }
  }, []);

  const continueAsGuest = useCallback(async () => {
    try {
      await fbSignInAnonymously();
    } catch (e) {
      const errMsg = e instanceof Error ? e.message : String(e);
      setAuthError(errMsg);
      console.warn('[useAuth] Anonymous sign-in failed:', e);
    }
  }, []);

  useEffect(() => {
    if (response?.type === 'success' && response.params.id_token) {
      signInWithGoogleIdToken(response.params.id_token).catch((e) => {
        const errMsg = e instanceof Error ? e.message : String(e);
        setAuthError(errMsg);
        // eslint-disable-next-line no-console
        console.warn('[useAuth] Firebase sign-in failed:', e);
      });
    }
  }, [response]);

  const signInWithGoogle = useCallback(() => {
    if (!platformConfigured) {
      const msg =
        '[useAuth] Google OAuth client ID not configured for ' +
        Platform.OS +
        '. Set EXPO_PUBLIC_GOOGLE_' +
        (Platform.OS === 'ios'
          ? 'IOS'
          : Platform.OS === 'android'
          ? 'ANDROID'
          : 'WEB') +
        '_CLIENT_ID in mobile/.env';
      setAuthError(msg);
      // eslint-disable-next-line no-console
      console.warn(msg);
      return Promise.resolve({ type: 'dismiss' as const });
    }
    return promptAsync();
  }, [promptAsync]);

  const signOut = useCallback(async () => {
    setIsGuest(false);
    // 1. Clear backend cookies + secure-store tokens
    try {
      await api.logoutSession();
    } catch {
      /* non-fatal */
    }
    // 2. Clear all local AsyncStorage data (session, intake, last trip, user id, onboarding flag)
    try {
      await clearAllLocalData();
      await AsyncStorage.removeItem(ONBOARDING_KEY);
    } catch {
      /* non-fatal */
    }
    // 3. Clear Firebase auth state
    setUser(null);
    try {
      await fbSignOut(auth);
    } catch {
      /* ignore */
    }
    // 4. Redirect to entry gate so auth routing re-evaluates cleanly
    try {
      router.replace('/');
    } catch {
      /* ignore if router not mounted */
    }
  }, [router]);

  const signInWithEmail = useCallback(
    async (email: string, password: string) => {
      try {
        const result = await fbSignInWithEmail(email, password);
        setAuthError(null);
        return result;
      } catch (error) {
        const err = error as Record<string, unknown>;
        const errMsg = `${err.code}: ${err.message}`;
        setAuthError(errMsg);
        throw error;
      }
    },
    [],
  );

  const signUpWithEmail = useCallback(
    async (email: string, password: string) => {
      try {
        const result = await fbSignUpWithEmail(email, password);
        setAuthError(null);
        return result;
      } catch (error) {
        const err = error as Record<string, unknown>;
        const errMsg = `${err.code}: ${err.message}`;
        setAuthError(errMsg);
        throw error;
      }
    },
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
    authError,
  };
}
