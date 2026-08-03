/**
 * Firebase client initialisation for the Touri Expo (React Native) app.
 *
 * Bulletproof init: this module is guaranteed not to throw on import,
 * so screens always mount. If auth fails to wire up (unsupported SDK
 * combo, missing env var, etc.) we expose a stub so the rest of the app
 * stays loadable while the issue is surfaced via console warnings.
 */

import { initializeApp, getApp, getApps, type FirebaseApp } from 'firebase/app';
import * as fbAuth from 'firebase/auth';
import {
  getFirestore,
  initializeFirestore,
  type Firestore,
} from 'firebase/firestore';
// import { getFirestore, type Firestore } from 'firebase/firestore';
import { getStorage, type FirebaseStorage } from 'firebase/storage';
import AsyncStorage from '@react-native-async-storage/async-storage';

type Auth = fbAuth.Auth;

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
function tryInitAuth(): Auth {
  const anyFb = fbAuth as any;
  const getRNPersistence: ((s: unknown) => unknown) | undefined =
    anyFb.getReactNativePersistence;

  // Try the canonical RN path first (firebase 12+ on Expo).
  if (typeof getRNPersistence === 'function') {
    try {
      return fbAuth.initializeAuth(app, {
        persistence: getRNPersistence(AsyncStorage) as never,
      });
    } catch {
      /* fall through */
    }
  }

  // Try plain initializeAuth (memory-only persistence).
  try {
    return fbAuth.initializeAuth(app);
  } catch {
    /* fall through */
  }

  // Already-initialised (Fast Refresh).
  try {
    return fbAuth.getAuth(app);
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
// export const db: Firestore = getFirestore(app);
// initializeFirestore must only be called once
// Fast Refresh في Expo ممكن يعيد التهيئة
let db_: Firestore;

try {
  db_ = initializeFirestore(app, {
    experimentalAutoDetectLongPolling: true,
  });
} catch {
  db_ = getFirestore(app);
}

export const db: Firestore = db_;
export const storage: FirebaseStorage = getStorage(app);

// ── Google Sign-In ───────────────────────────────────────────────────────────
export async function signInWithGoogleIdToken(idToken: string) {
  const credential = fbAuth.GoogleAuthProvider.credential(idToken);
  return fbAuth.signInWithCredential(auth, credential);
}

// ── Email / Password ─────────────────────────────────────────────────────────
export async function signInWithEmail(email: string, password: string) {
  return fbAuth.signInWithEmailAndPassword(auth, email.trim(), password);
}

export async function signUpWithEmail(email: string, password: string) {
  return fbAuth.createUserWithEmailAndPassword(auth, email.trim(), password);
}

export async function signInAnonymously() {
  return fbAuth.signInAnonymously(auth);
}

export default app;
