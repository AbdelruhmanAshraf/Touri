/**
 * Touri i18n bootstrap.
 *
 * Initialises ``react-i18next`` with English + Arabic resource bundles and
 * exposes a small ``applyLanguage`` helper that also flips ``I18nManager``
 * for proper RTL on Arabic. The active language is sourced from the backend
 * ``UserPersona.language_preference`` whenever the chat tab mounts.
 */

import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import { I18nManager } from 'react-native';
import * as Localization from 'expo-localization';

import en from './locales/en.json';
import ar from './locales/ar.json';

export type AppLanguage = 'en' | 'ar';

const deviceLang: AppLanguage =
  (Localization.getLocales()?.[0]?.languageCode as AppLanguage) === 'ar'
    ? 'ar'
    : 'en';

i18n
  .use(initReactI18next)
  .init({
    compatibilityJSON: 'v4',
    resources: { en: { translation: en }, ar: { translation: ar } },
    lng: deviceLang,
    fallbackLng: 'en',
    interpolation: { escapeValue: false },
    returnNull: false,
  });

/**
 * Switches the active language and flips RTL when needed.
 *
 * NOTE: Hard RTL flipping requires a native reload. We toggle the soft
 * preference for layout direction so React Native's flex behaviour follows
 * along; on Arabic we still rotate ``writingDirection`` via styles in the
 * components.
 */
export async function applyLanguage(lang: AppLanguage): Promise<void> {
  if (i18n.language !== lang) {
    await i18n.changeLanguage(lang);
  }
  const wantsRTL = lang === 'ar';
  if (I18nManager.isRTL !== wantsRTL) {
    try {
      I18nManager.allowRTL(wantsRTL);
      I18nManager.forceRTL(wantsRTL);
    } catch {
      /* non-fatal on web */
    }
  }
}

export default i18n;
