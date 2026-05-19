/**
 * Secure storage wrapper — Phase 5.
 *
 * On iOS / Android we use `expo-secure-store` (Keychain / Keystore) for
 * sensitive tokens. On web we transparently fall back to `AsyncStorage`
 * because SecureStore is unavailable there.
 *
 * Use this for:
 *   - touri_access_token   (JWT issued by /api/auth/session)
 *   - touri_refresh_token  (JWT issued by /api/auth/session)
 *   - any future credential that should never live in plain AsyncStorage
 */

import * as SecureStore from 'expo-secure-store';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { Platform } from 'react-native';

const useNative = Platform.OS === 'ios' || Platform.OS === 'android';

export const SECURE_KEYS = {
  ACCESS_TOKEN: 'touri_access_token',
  REFRESH_TOKEN: 'touri_refresh_token',
} as const;

export async function setSecure(key: string, value: string): Promise<void> {
  if (useNative) {
    try {
      await SecureStore.setItemAsync(key, value);
      return;
    } catch (e) {
      console.warn('[secureStore] setItemAsync failed — falling back', e);
    }
  }
  await AsyncStorage.setItem(key, value);
}

export async function getSecure(key: string): Promise<string | null> {
  if (useNative) {
    try {
      const v = await SecureStore.getItemAsync(key);
      if (v !== null) return v;
    } catch (e) {
      console.warn('[secureStore] getItemAsync failed — falling back', e);
    }
  }
  return AsyncStorage.getItem(key);
}

export async function deleteSecure(key: string): Promise<void> {
  if (useNative) {
    try {
      await SecureStore.deleteItemAsync(key);
    } catch {
      /* non-fatal */
    }
  }
  await AsyncStorage.removeItem(key);
}

export async function clearAllSecure(): Promise<void> {
  await Promise.all(
    Object.values(SECURE_KEYS).map((k) => deleteSecure(k)),
  );
}
