import { useEffect } from 'react';
import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';

import '@/config/firebaseConfig'; // ensure Firebase initialises at boot
import '@/i18n'; // initialise i18next
import { applyLanguage } from '@/i18n';
import { api, getOrCreateUserId } from '@/services/api';

export default function RootLayout() {
  // On boot, fetch the active persona and apply its language + RTL.
  // Failure is non-fatal — we just stay on the device default language.
  useEffect(() => {
    (async () => {
      try {
        const uid = await getOrCreateUserId();
        const persona = await api.getPersona(uid).catch(() => null);
        const lang =
          persona && (persona.extras as Record<string, unknown> | undefined)?.language_preference;
        if (lang === 'en' || lang === 'ar') {
          await applyLanguage(lang);
        }
      } catch {
        /* silent */
      }
    })();
  }, []);

  return (
    <>
      <StatusBar style="auto" />
      <Stack screenOptions={{ headerTitleStyle: { fontWeight: '600' } }}>
        <Stack.Screen name="index" options={{ headerShown: false }} />
        <Stack.Screen name="onboarding" options={{ headerShown: false, gestureEnabled: false }} />
        <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
        {/* Native OS modal — the OS handles the sheet animation & dismiss gesture */}
        <Stack.Screen
          name="place"
          options={{
            headerShown: false,
            presentation: 'modal',
            gestureEnabled: true,
          }}
        />
        <Stack.Screen
          name="itinerary"
          options={{ headerShown: false }}
        />
      </Stack>
    </>
  );
}
