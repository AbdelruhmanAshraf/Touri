/**
 * useProfile — manages the onboarding_completed flag.
 *
 * Strategy:
 *  1. Read AsyncStorage immediately (instant — used for route decision).
 *  2. Validate against Firestore in the background (handles reinstall case).
 *  3. On mismatch (Firestore says completed but local cache empty) update local.
 *  4. `markOnboardingComplete` writes both Firestore and local cache atomically.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import {
  doc,
  getDoc,
  setDoc,
  serverTimestamp,
} from 'firebase/firestore';
import { db } from '@/config/firebaseConfig';
import type { User } from 'firebase/auth';

const LOCAL_KEY = 'touri_onboarded';

function profileRef(uid: string) {
  return doc(db, 'users', uid, 'profile', 'main');
}

export type ProfileState = {
  /** null = still loading, true/false = known */
  onboardingCompleted: boolean | null;
  markOnboardingComplete: () => Promise<void>;
  clearLocalProfile: () => Promise<void>;
};

export function useProfile(user: User | null): ProfileState {
  const [onboardingCompleted, setOnboardingCompleted] = useState<boolean | null>(null);
  const resolvedRef = useRef(false);

  useEffect(() => {
    resolvedRef.current = false;
    setOnboardingCompleted(null);

    if (!user) {
      setOnboardingCompleted(false);
      return;
    }

    let cancelled = false;

    const resolve = async () => {
      // 1. Instant local check
      try {
        const local = await AsyncStorage.getItem(LOCAL_KEY);
        if (!cancelled && local === '1') {
          setOnboardingCompleted(true);
          resolvedRef.current = true;
        }
      } catch { /* ignore */ }

      // 2. Background Firestore validation (handles reinstall)
      try {
        const snap = await getDoc(profileRef(user.uid));
        if (cancelled) return;
        const completed = snap.exists() && snap.data()?.onboarding_completed === true;
        if (completed) {
          await AsyncStorage.setItem(LOCAL_KEY, '1').catch(() => {});
          if (!cancelled) {
            setOnboardingCompleted(true);
            resolvedRef.current = true;
          }
        } else if (!resolvedRef.current) {
          setOnboardingCompleted(false);
        }
      } catch {
        // Firestore unreachable — fall back to local cache or false
        if (!cancelled && !resolvedRef.current) {
          setOnboardingCompleted(false);
        }
      }
    };

    resolve();
    return () => { cancelled = true; };
  }, [user?.uid]);

  const markOnboardingComplete = useCallback(async () => {
    if (!user) return;
    setOnboardingCompleted(true);
    // Write both in parallel; neither blocks the UI
    await Promise.all([
      AsyncStorage.setItem(LOCAL_KEY, '1').catch(() => {}),
      setDoc(
        profileRef(user.uid),
        {
          onboarding_completed: true,
          is_guest: user.isAnonymous,
          updated_at: serverTimestamp(),
        },
        { merge: true },
      ).catch((e) => console.warn('[useProfile] Firestore write failed:', e)),
    ]);
  }, [user]);

  const clearLocalProfile = useCallback(async () => {
    setOnboardingCompleted(null);
    await AsyncStorage.removeItem(LOCAL_KEY).catch(() => {});
  }, []);

  return { onboardingCompleted, markOnboardingComplete, clearLocalProfile };
}
