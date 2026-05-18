/**
 * Profile screen — Notion-style property list design.
 *
 * Each preference is a flat property row (icon · label · value) rather than
 * a card-per-section. Inline editing is triggered by tapping the row value.
 * The overall feel is minimal, content-first, and typography-driven.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Animated,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { Image } from 'expo-image';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Feather, Ionicons, MaterialIcons } from '@expo/vector-icons';
import { useTranslation } from 'react-i18next';
import { useRouter } from 'expo-router';

import { applyLanguage, type AppLanguage } from '@/i18n';
import { GUEST_LIMITS, useAuth } from '@/hooks/useAuth';
import { api, getOrCreateUserId, type PersonaWrite, type UserPersona } from '@/services/api';

const PRIMARY = '#00A896';
const BG = '#F2F2F7';
const SURFACE = '#FFFFFF';
const BORDER = '#E5E5EA';
const TEXT = '#1C1C1E';
const MUTED = '#8E8E93';

const TOURISM_OPTS: { value: 'leisure' | 'medical'; en: string; ar: string; icon: keyof typeof Ionicons.glyphMap }[] = [
  { value: 'leisure', en: 'Leisure',  ar: 'ترفيهية', icon: 'sunny-outline' },
  { value: 'medical', en: 'Medical',  ar: 'علاجية',  icon: 'medkit-outline' },
];

const BUDGET_OPTS: {
  value: 'economy' | 'mid_range' | 'luxury';
  en: string; ar: string;
  icon: keyof typeof Ionicons.glyphMap;
  color: string;
}[] = [
  { value: 'economy',   en: 'Economy',   ar: 'اقتصادي', icon: 'leaf-outline',    color: '#059669' },
  { value: 'mid_range', en: 'Mid-range', ar: 'متوسط',   icon: 'card-outline',    color: '#0284C7' },
  { value: 'luxury',    en: 'Luxury',    ar: 'فاخر',    icon: 'diamond-outline', color: '#7C3AED' },
];

// ── Tiny helpers ──────────────────────────────────────────────────────────────
function initials(email?: string | null) {
  if (!email) return 'TM';
  const parts = email.split('@')[0].replace(/[._-]/g, ' ').split(' ');
  return parts.slice(0, 2).map((p) => p[0]?.toUpperCase() ?? '').join('');
}

// ── Property row ──────────────────────────────────────────────────────────────
function PropRow({
  icon,
  label,
  last = false,
  children,
}: {
  icon: keyof typeof Ionicons.glyphMap;
  label: string;
  last?: boolean;
  children: React.ReactNode;
}) {
  return (
    <View style={[propStyles.row, !last && propStyles.divider]}>
      <View style={propStyles.left}>
        <Ionicons name={icon} size={16} color={MUTED} style={{ width: 20 }} />
        <Text style={propStyles.label}>{label}</Text>
      </View>
      <View style={propStyles.right}>{children}</View>
    </View>
  );
}
const propStyles = StyleSheet.create({
  row: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: 18, paddingVertical: 14, minHeight: 52,
  },
  divider: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: BORDER },
  left: { flexDirection: 'row', alignItems: 'center', gap: 10, flex: 1 },
  label: { fontSize: 14, fontWeight: '500', color: TEXT },
  right: { flex: 1.2, alignItems: 'flex-end' },
});

// ── Toggle chip group ─────────────────────────────────────────────────────────
function ToggleGroup<T extends string>({
  value,
  options,
  onChange,
}: {
  value: T | undefined;
  options: { value: T; label: string; color?: string }[];
  onChange: (v: T) => void;
}) {
  return (
    <View style={{ flexDirection: 'row', gap: 6, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
      {options.map((opt) => {
        const active = value === opt.value;
        const col = opt.color ?? PRIMARY;
        return (
          <TouchableOpacity
            key={opt.value}
            style={[
              toggleStyles.chip,
              active && { backgroundColor: `${col}15`, borderColor: col },
            ]}
            onPress={() => onChange(opt.value)}
          >
            <Text style={[toggleStyles.txt, active && { color: col, fontWeight: '700' }]}>
              {opt.label}
            </Text>
          </TouchableOpacity>
        );
      })}
    </View>
  );
}
const toggleStyles = StyleSheet.create({
  chip: {
    paddingHorizontal: 10, paddingVertical: 5,
    borderRadius: 20, borderWidth: 1.5, borderColor: BORDER,
  },
  txt: { fontSize: 12, fontWeight: '600', color: MUTED },
});

// ── Section card ──────────────────────────────────────────────────────────────
function Section({ label, children }: { label?: string; children: React.ReactNode }) {
  return (
    <View style={sectionStyles.wrap}>
      {label && <Text style={sectionStyles.label}>{label}</Text>}
      <View style={sectionStyles.card}>{children}</View>
    </View>
  );
}
const sectionStyles = StyleSheet.create({
  wrap: { gap: 6 },
  label: { fontSize: 11, fontWeight: '700', color: MUTED, textTransform: 'uppercase', letterSpacing: 0.8, paddingHorizontal: 4 },
  card: { backgroundColor: SURFACE, borderRadius: 16, borderWidth: 1, borderColor: BORDER, overflow: 'hidden' },
});

// ── Main screen ───────────────────────────────────────────────────────────────
export default function ProfileScreen() {
  const { t, i18n } = useTranslation();
  const { user, isGuest, signOut } = useAuth();
  const router = useRouter();
  const isAr = i18n.language === 'ar';

  const [persona, setPersona] = useState<UserPersona | null>(null);
  const [loadErr, setLoadErr] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [editDest, setEditDest] = useState(false);
  const savingAnim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    Animated.timing(savingAnim, { toValue: saving ? 1 : 0, duration: 200, useNativeDriver: true }).start();
  }, [saving]);

  const refresh = useCallback(async () => {
    if (isGuest) return;
    try {
      const uid = user?.uid ?? (await getOrCreateUserId());
      const p = await api.getPersona(uid);
      setPersona(p);
      const langPref = (p.extras as Record<string, unknown> | undefined)?.language_preference;
      if (langPref === 'en' || langPref === 'ar') applyLanguage(langPref as AppLanguage);
    } catch (e: any) {
      setLoadErr(e?.message ?? 'Failed to load persona');
    }
  }, [user?.uid, isGuest]);

  useEffect(() => { refresh(); }, [refresh]);

  const update = async (changes: PersonaWrite) => {
    if (!persona) return;
    setSaving(true);
    setPersona((p) => p ? { ...p, ...(changes as Partial<UserPersona>) } : p);
    try {
      const uid = user?.uid ?? (await getOrCreateUserId());
      const next = await api.updatePersona(uid, changes);
      setPersona(next);
    } catch (e) {
      setLoadErr((e as Error)?.message ?? 'Update failed');
    } finally {
      setSaving(false);
    }
  };

  const handleLanguage = async (lang: AppLanguage) => {
    await applyLanguage(lang);
    if (persona) await update({ extras: { ...(persona.extras || {}), language_preference: lang } });
  };

  const handleSignOut = async () => { await signOut(); router.replace('/'); };

  const displayName = user?.email?.split('@')[0] || (isAr ? 'مستخدم' : 'Tripmind User');
  const avatarLetters = initials(user?.email);

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* ── Page title ── */}
      <View style={[styles.pageHeader, { flexDirection: isAr ? 'row-reverse' : 'row' }]}>
        <Text style={styles.pageTitle}>{isAr ? 'الملف الشخصي' : 'Profile'}</Text>
        <Animated.View style={{ opacity: savingAnim }}>
          <ActivityIndicator size="small" color={PRIMARY} />
        </Animated.View>
      </View>

      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>

        {/* ── Avatar + identity block ── */}
        <View style={styles.identityBlock}>
          <View style={styles.avatarShell}>
            {user?.photoURL ? (
              <Image source={{ uri: user.photoURL }} style={styles.avatarImg} contentFit="cover" transition={200} />
            ) : (
              <View style={styles.avatarFallback}>
                <Text style={styles.avatarLetters}>{avatarLetters}</Text>
              </View>
            )}
          </View>
          <View style={styles.identityText}>
            <Text style={styles.displayName}>{displayName}</Text>
            <Text style={styles.emailLine}>{user?.email || (isAr ? 'وضع الضيف' : 'Guest Mode')}</Text>
          </View>
          {!isGuest && <View style={styles.verifiedBadge}>
            <Feather name="check" size={11} color="#fff" />
          </View>}
        </View>

        {loadErr && (
          <Text style={styles.errTxt}>{loadErr}</Text>
        )}

        {/* ── Guest call-to-action ── */}
        {isGuest && (
          <Section>
            <View style={styles.guestBlock}>
              <View style={styles.guestIconWrap}>
                <MaterialIcons name="lock-outline" size={28} color={PRIMARY} />
              </View>
              <Text style={styles.guestTitle}>{isAr ? 'ميزات كاملة بعد تسجيل الدخول' : 'Unlock full features'}</Text>
              <Text style={styles.guestSub}>{isAr ? 'سجّل دخولك لحفظ تفضيلاتك وخططك' : 'Sign in to save your preferences and trip plans'}</Text>
              <TouchableOpacity style={styles.guestCTA} onPress={handleSignOut}>
                <Text style={styles.guestCTATxt}>{isAr ? 'تسجيل الدخول' : 'Sign In'}</Text>
              </TouchableOpacity>
            </View>
          </Section>
        )}

        {/* ── Preferences ── */}
        {!isGuest && persona && (
          <>
            <Section label={isAr ? 'التفضيلات' : 'Preferences'}>
              {/* Destination */}
              <PropRow icon="location-outline" label={isAr ? 'الوجهة' : 'Destination'}>
                {editDest ? (
                  <TextInput
                    style={styles.inlineInput}
                    value={persona.preferred_destination ?? ''}
                    autoFocus
                    onChangeText={(v) => setPersona((p) => p ? { ...p, preferred_destination: v } : p)}
                    onBlur={() => {
                      setEditDest(false);
                      update({ preferred_destination: persona.preferred_destination || undefined });
                    }}
                    placeholder={isAr ? 'اكتب الوجهة' : 'e.g. Cairo'}
                    placeholderTextColor="#C7C7CC"
                    textAlign={isAr ? 'right' : 'left'}
                  />
                ) : (
                  <TouchableOpacity onPress={() => setEditDest(true)} style={styles.valuePill}>
                    <Text style={styles.valuePillTxt} numberOfLines={1}>
                      {persona.preferred_destination || (isAr ? 'اضغط للتعديل' : 'Tap to set')}
                    </Text>
                    <Feather name="edit-2" size={11} color={MUTED} />
                  </TouchableOpacity>
                )}
              </PropRow>

              {/* Tourism type */}
              <PropRow icon="compass-outline" label={isAr ? 'نوع السياحة' : 'Tourism'}>
                <ToggleGroup
                  value={persona.tourism_type}
                  options={TOURISM_OPTS.map((o) => ({ value: o.value, label: isAr ? o.ar : o.en }))}
                  onChange={(v) => update({ tourism_type: v })}
                />
              </PropRow>

              {/* Budget */}
              <PropRow icon="wallet-outline" label={isAr ? 'الميزانية' : 'Budget'}>
                <ToggleGroup
                  value={persona.budget_bracket}
                  options={BUDGET_OPTS.map((o) => ({ value: o.value, label: isAr ? o.ar : o.en, color: o.color }))}
                  onChange={(v) => update({ budget_bracket: v })}
                />
              </PropRow>

              {/* Party size */}
              <PropRow icon="people-outline" label={isAr ? 'عدد المسافرين' : 'Travelers'} last>
                <View style={styles.stepper}>
                  <TouchableOpacity
                    style={styles.stepBtn}
                    onPress={() => update({ party_size: Math.max(1, (persona.party_size ?? 1) - 1) })}
                  >
                    <MaterialIcons name="remove" size={16} color={TEXT} />
                  </TouchableOpacity>
                  <Text style={styles.stepVal}>{persona.party_size ?? 1}</Text>
                  <TouchableOpacity
                    style={styles.stepBtn}
                    onPress={() => update({ party_size: Math.min(20, (persona.party_size ?? 1) + 1) })}
                  >
                    <MaterialIcons name="add" size={16} color={TEXT} />
                  </TouchableOpacity>
                </View>
              </PropRow>
            </Section>

            {/* Language */}
            <Section label={isAr ? 'اللغة' : 'Language'}>
              <PropRow icon="globe-outline" label={isAr ? 'لغة التطبيق' : 'App language'} last>
                <View style={{ flexDirection: 'row', gap: 6 }}>
                  {(['en', 'ar'] as AppLanguage[]).map((lang) => {
                    const active = i18n.language === lang;
                    return (
                      <TouchableOpacity
                        key={lang}
                        style={[styles.langBtn, active && styles.langBtnActive]}
                        onPress={() => handleLanguage(lang)}
                      >
                        <Text style={[styles.langTxt, active && styles.langTxtActive]}>
                          {lang === 'en' ? 'EN' : 'AR'}
                        </Text>
                      </TouchableOpacity>
                    );
                  })}
                </View>
              </PropRow>
            </Section>
          </>
        )}

        {/* ── Account actions ── */}
        <Section label={isAr ? 'الحساب' : 'Account'}>
          <TouchableOpacity style={styles.actionRow} onPress={handleSignOut}>
            <View style={styles.actionLeft}>
              <Ionicons name="log-out-outline" size={16} color="#FF3B30" style={{ width: 20 }} />
              <Text style={[styles.actionTxt, { color: '#FF3B30' }]}>
                {isAr ? 'تسجيل الخروج' : 'Sign Out'}
              </Text>
            </View>
            <Feather name="chevron-right" size={16} color="#FF3B30" />
          </TouchableOpacity>
        </Section>

        <Text style={styles.version}>Tripmind v1.0 · Egypt Travel AI</Text>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: BG },

  pageHeader: {
    paddingHorizontal: 20, paddingVertical: 14,
    alignItems: 'center', justifyContent: 'space-between',
  },
  pageTitle: { fontSize: 28, fontWeight: '800', color: TEXT, letterSpacing: -0.5 },

  scroll: { paddingHorizontal: 16, paddingBottom: 120, gap: 20 },

  // ── Identity block ──
  identityBlock: {
    flexDirection: 'row', alignItems: 'center', gap: 14,
    backgroundColor: SURFACE, borderRadius: 16,
    padding: 16, borderWidth: 1, borderColor: BORDER,
  },
  avatarShell: { position: 'relative' },
  avatarImg: { width: 52, height: 52, borderRadius: 26 },
  avatarFallback: {
    width: 52, height: 52, borderRadius: 26,
    backgroundColor: `${PRIMARY}20`,
    alignItems: 'center', justifyContent: 'center',
  },
  avatarLetters: { fontSize: 18, fontWeight: '800', color: PRIMARY },
  identityText: { flex: 1, gap: 2 },
  displayName: { fontSize: 17, fontWeight: '700', color: TEXT },
  emailLine: { fontSize: 13, color: MUTED },
  verifiedBadge: {
    width: 20, height: 20, borderRadius: 10,
    backgroundColor: PRIMARY, alignItems: 'center', justifyContent: 'center',
  },

  errTxt: { color: '#FF3B30', fontSize: 13, textAlign: 'center', marginTop: -8 },

  // ── Guest block ──
  guestBlock: {
    alignItems: 'center', gap: 10, padding: 24,
  },
  guestIconWrap: {
    width: 52, height: 52, borderRadius: 16,
    backgroundColor: `${PRIMARY}15`, alignItems: 'center', justifyContent: 'center',
  },
  guestTitle: { fontSize: 16, fontWeight: '700', color: TEXT, textAlign: 'center' },
  guestSub: { fontSize: 13, color: MUTED, textAlign: 'center', lineHeight: 20 },
  guestCTA: {
    marginTop: 4, backgroundColor: PRIMARY,
    paddingHorizontal: 28, paddingVertical: 11, borderRadius: 12,
  },
  guestCTATxt: { color: '#fff', fontWeight: '700', fontSize: 14 },

  // ── Value pill (inline edit trigger) ──
  valuePill: {
    flexDirection: 'row', alignItems: 'center', gap: 5,
    backgroundColor: BG, borderRadius: 10,
    paddingHorizontal: 10, paddingVertical: 6,
    maxWidth: 180,
  },
  valuePillTxt: { fontSize: 13, fontWeight: '600', color: TEXT, flex: 1, textAlign: 'right' },
  inlineInput: {
    fontSize: 13, color: TEXT, fontWeight: '600',
    borderBottomWidth: 1.5, borderBottomColor: PRIMARY,
    minWidth: 120, textAlign: 'right', paddingVertical: 2,
  },

  // ── Stepper ──
  stepper: { flexDirection: 'row', alignItems: 'center', gap: 14 },
  stepBtn: {
    width: 30, height: 30, borderRadius: 10,
    backgroundColor: BG, alignItems: 'center', justifyContent: 'center',
    borderWidth: 1, borderColor: BORDER,
  },
  stepVal: { fontSize: 17, fontWeight: '800', color: TEXT, minWidth: 24, textAlign: 'center' },

  // ── Language buttons ──
  langBtn: {
    paddingHorizontal: 14, paddingVertical: 6,
    borderRadius: 20, borderWidth: 1.5, borderColor: BORDER,
  },
  langBtnActive: { backgroundColor: PRIMARY, borderColor: PRIMARY },
  langTxt: { fontSize: 13, fontWeight: '700', color: MUTED },
  langTxtActive: { color: '#fff' },

  // ── Account action row ──
  actionRow: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: 18, paddingVertical: 14,
  },
  actionLeft: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  actionTxt: { fontSize: 15, fontWeight: '600' },

  version: { textAlign: 'center', fontSize: 11, color: '#C7C7CC', paddingBottom: 8 },
});
