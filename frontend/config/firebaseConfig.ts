/**
 * Firebase client initialisation for the Touri Expo (React Native) app.
 *
 * Bulletproof init: this module is guaranteed not to throw on import,
 * so screens always mount. If auth fails to wire up (unsupported SDK
 * combo, missing env var, etc.) we expose a stub so the rest of the app
 * stays loadable while the issue is surfaced via console warnings.
 */

import { initializeApp, getApp, getApps, type FirebaseApp } from 'firebase/app';
import {
  initializeAuth,
  getAuth,
  getReactNativePersistence, // augmented in types/firebase-auth-rn.d.ts
  GoogleAuthProvider,
  signInWithCredential,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  signInAnonymously as fbSignInAnonymously,
  type Auth,
} from 'firebase/auth';
import {
  getFirestore,
  initializeFirestore,
  type Firestore,
} from 'firebase/firestore';
import { getStorage, type FirebaseStorage } from 'firebase/storage';
import AsyncStorage from '@react-native-async-storage/async-storage';

// ── Env helpers ──────────────────────────────────────────────────────────────
const env = (key: string, fallback = ''): string => {
  const v = (process.env as Record<string, string | undefined>)[key];
  if (!v && !fallback) {
    // eslint-disable-next-line no-console
    console.warn(`[firebaseConfig] Missing env var: ${key}`);
  }
  return v ?? fallback;
};

export const firebaseConfig = {
  apiKey: env('EXPO_PUBLIC_FIREBASE_API_KEY'),
  authDomain: env('EXPO_PUBLIC_FIREBASE_AUTH_DOMAIN'),
  projectId: env('EXPO_PUBLIC_FIREBASE_PROJECT_ID'),
  storageBucket: env('EXPO_PUBLIC_FIREBASE_STORAGE_BUCKET'),
  messagingSenderId: env('EXPO_PUBLIC_FIREBASE_MESSAGING_SENDER_ID'),
  appId: env('EXPO_PUBLIC_FIREBASE_APP_ID'),
} as const;

// ── App singleton ────────────────────────────────────────────────────────────
export const app: FirebaseApp = getApps().length
  ? getApp()
  : initializeApp(firebaseConfig);

// ── Auth (never throws) ──────────────────────────────────────────────────────
// `getReactNativePersistence` is only present when the bundler resolves
// `firebase/auth` via the "react-native" export condition (Metro does this
// automatically; TypeScript does too thanks to `customConditions` in
// expo/tsconfig.base). It's typed as defined, but at runtime in non-RN
// environments (e.g. unit tests under Node) it may be undefined — so we still
// guard with `typeof`.
function tryInitAuth(): Auth {
  const rnPersist: ((s: unknown) => unknown) | undefined =
    getReactNativePersistence as unknown as
      | ((s: unknown) => unknown)
      | undefined;

  // Canonical RN path (firebase 12+ on Expo, async-storage v2).
  if (typeof rnPersist === 'function') {
    try {
      return initializeAuth(app, {
        persistence: rnPersist(AsyncStorage) as never,
      });
    } catch {
      /* fall through — likely Fast Refresh re-init */
    }
  }

  // Already-initialised (Fast Refresh re-runs the module).
  try {
    return getAuth(app);
  } catch {
    /* fall through */
  }

  // Memory-only fallback (will warn, but app still renders).
  try {
    return initializeAuth(app);
  } catch {
    /* fall through */
  }

  // Last-resort stub so the module never throws on import.
  // eslint-disable-next-line no-console
  console.warn(
    '[firebaseConfig] Could not initialise Firebase Auth. ' +
      'Sign-in will not work, but the rest of the app will still render.',
  );
  return new Proxy({} as Auth, {
    get() {
      throw new Error(
        '[firebaseConfig] Firebase Auth failed to initialise. ' +
          'Check that EXPO_PUBLIC_FIREBASE_* env vars are set.',
      );
    },
  });
}

export const auth: Auth = tryInitAuth();

// ── Firestore (RN/Expo-safe long-polling) ────────────────────────────────────
// React Native's WebSocket implementation is unreliable for Firestore's
// streaming protocol, which causes:
//   "Could not reach Cloud Firestore backend. Backend didn't respond within 10 seconds."
// `experimentalAutoDetectLongPolling` falls back to HTTP long-polling, which
// works on every Expo target (iOS, Android, web, Expo Go, dev-client).
function initDb(): Firestore {
  try {
    return initializeFirestore(app, {
      experimentalAutoDetectLongPolling: true,
    });
  } catch {
    // Already initialised (Fast Refresh) — just grab the existing instance.
    return getFirestore(app);
  }
}

export const db: Firestore = initDb();
export const storage: FirebaseStorage = getStorage(app);

// ── Google Sign-In ───────────────────────────────────────────────────────────
export async function signInWithGoogleIdToken(idToken: string) {
  const credential = GoogleAuthProvider.credential(idToken);
  return signInWithCredential(auth, credential);
}

// ── Email / Password ─────────────────────────────────────────────────────────
export async function signInWithEmail(email: string, password: string) {
  return signInWithEmailAndPassword(auth, email.trim(), password);
}

export async function signUpWithEmail(email: string, password: string) {
  return createUserWithEmailAndPassword(auth, email.trim(), password);
}

export async function signInAnonymously() {
  return fbSignInAnonymously(auth);
}

export default app;
