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
  Modal,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
  TextInput,
  Alert,
} from 'react-native';
import { Image } from 'expo-image';
import * as ImagePicker from 'expo-image-picker';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Feather, Ionicons, MaterialIcons } from '@expo/vector-icons';
import { useTranslation } from 'react-i18next';
import { useRouter } from 'expo-router';

import { applyLanguage, type AppLanguage } from '@/i18n';
import { GUEST_LIMITS, useAuth } from '@/hooks/useAuth';
import { api, getOrCreateUserId, type PersonaWrite, type UserPersona } from '@/services/api';
import { EGYPT_GOVERNORATES } from '@/constants/Governorates';
import NotionAvatar from '@/components/NotionAvatar';
import {
  PRIMARY,
  BG,
  SURFACE,
  BORDER_COLOR,
  TEXT,
  MUTED,
  PLACEHOLDER,
  ERROR,
  RADIUS,
  RADIUS_SM,
  RADIUS_PILL,
  SPACING,
} from '@/theme/tokens';

const GENDER_OPTS: { value: 'male' | 'female'; en: string; ar: string }[] = [
  { value: 'male', en: 'Male', ar: 'ذكر' },
  { value: 'female', en: 'Female', ar: 'أنثى' },
];

const TOURISM_OPTS: { value: 'leisure' | 'medical'; en: string; ar: string; icon: keyof typeof Ionicons.glyphMap }[] = [
  { value: 'leisure', en: 'Leisure',  ar: 'ترفيهية', icon: 'sunny-outline' },
  { value: 'medical', en: 'Medical',  ar: 'علاجية',  icon: 'medkit-outline' },
];

const ALLERGY_OPTS: { value: string; en: string; ar: string }[] = [
  { value: 'nuts',    en: 'Nuts',    ar: 'مكسرات' },
  { value: 'dairy',   en: 'Dairy',   ar: 'ألبان' },
  { value: 'gluten',  en: 'Gluten',  ar: 'جلوتين' },
  { value: 'seafood', en: 'Seafood', ar: 'مأكولات بحرية' },
  { value: 'none',    en: 'None',    ar: 'لا يوجد' },
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
  divider: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: BORDER_COLOR },
  left: { flexDirection: 'row', alignItems: 'center', gap: 10, flex: 1 },
  label: { fontSize: 14, fontWeight: '500', color: TEXT },
  right: { flex: 1.2, alignItems: 'flex-end' },
});

// ── Inline Input ──────────────────────────────────────────────────────────────
function InlineInput({
  value,
  placeholder,
  onChangeText,
}: {
  value?: string;
  placeholder?: string;
  onChangeText: (text: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [localVal, setLocalVal] = useState(value || '');

  useEffect(() => {
    setLocalVal(value || '');
  }, [value]);

  if (editing) {
    return (
      <TextInput
        style={[styles.valuePillTxt, { borderBottomWidth: 1, borderColor: PRIMARY, minWidth: 100 }]}
        value={localVal}
        onChangeText={setLocalVal}
        onBlur={() => {
          setEditing(false);
          if (localVal !== (value || '')) {
            onChangeText(localVal);
          }
        }}
        autoFocus
        placeholder={placeholder}
      />
    );
  }

  return (
    <TouchableOpacity onPress={() => setEditing(true)} style={styles.valuePill}>
      <Text style={styles.valuePillTxt} numberOfLines={1}>
        {value || placeholder}
      </Text>
      <Feather name="edit-2" size={11} color={MUTED} />
    </TouchableOpacity>
  );
}

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
    borderRadius: 20, borderWidth: 1.5, borderColor: BORDER_COLOR,
  },
  txt: { fontSize: 12, fontWeight: '600', color: MUTED },
});

// ── Multi-select chip group (for allergies) ───────────────────────────────────
function MultiChipGroup({
  selected,
  options,
  onChange,
}: {
  selected: string[];
  options: { value: string; label: string; color?: string }[];
  onChange: (values: string[]) => void;
}) {
  const toggle = (val: string) => {
    if (val === 'none') {
      // Selecting "none" clears all others
      onChange(selected.includes('none') ? [] : ['none']);
      return;
    }
    // Remove "none" if selecting an actual allergy
    let next = selected.filter((v) => v !== 'none');
    if (next.includes(val)) {
      next = next.filter((v) => v !== val);
    } else {
      next = [...next, val];
    }
    onChange(next);
  };

  return (
    <View style={{ flexDirection: 'row', gap: 6, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
      {options.map((opt) => {
        const active = selected.includes(opt.value);
        const col = opt.color ?? '#DC2626';
        return (
          <TouchableOpacity
            key={opt.value}
            style={[
              toggleStyles.chip,
              active && { backgroundColor: `${col}15`, borderColor: col },
            ]}
            onPress={() => toggle(opt.value)}
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
  card: { backgroundColor: SURFACE, borderRadius: RADIUS, borderWidth: 1, borderColor: BORDER_COLOR, overflow: 'hidden' },
});

// ── Main screen ───────────────────────────────────────────────────────────────
export default function ProfileScreen() {
  const { t, i18n } = useTranslation();
  const { user, isGuest, signOut, loading } = useAuth();
  const router = useRouter();
  const isAr = i18n.language === 'ar';

  const [persona, setPersona] = useState<UserPersona | null>(null);
  const [loadErr, setLoadErr] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [destModalOpen, setDestModalOpen] = useState(false);
  const [passwordModalOpen, setPasswordModalOpen] = useState(false);
  const savingAnim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    Animated.timing(savingAnim, { toValue: saving ? 1 : 0, duration: 200, useNativeDriver: true }).start();
  }, [saving]);

  const refresh = useCallback(async () => {
    if (loading) return;
    if (isGuest) return;
    if (!user?.uid) return;
    try {
      const p = await api.getPersona(user.uid);
      setPersona(p);
      const langPref = (p.extras as Record<string, unknown> | undefined)?.language_preference;
      if (langPref === 'en' || langPref === 'ar') applyLanguage(langPref as AppLanguage);
    } catch (e: any) {
      setLoadErr(e?.message ?? 'Failed to load persona');
    }
  }, [user?.uid, isGuest, loading]);

  useEffect(() => { refresh(); }, [refresh]);

  const update = async (changes: PersonaWrite) => {
    if (!persona || loading || !user?.uid) return;
    setSaving(true);
    setPersona((p) => p ? { ...p, ...(changes as Partial<UserPersona>) } : p);
    try {
      const next = await api.updatePersona(user.uid, changes);
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

  const handleSignOut = () => {
    Alert.alert(
      isAr ? 'تسجيل الخروج' : 'Sign Out',
      isAr ? 'هل أنت متأكد أنك تريد تسجيل الخروج؟' : 'Are you sure you want to sign out?',
      [
        { text: isAr ? 'إلغاء' : 'Cancel', style: 'cancel' },
        { text: isAr ? 'خروج' : 'Sign Out', style: 'destructive', onPress: async () => { await signOut(); router.replace('/'); } },
      ]
    );
  };

  const pickImage = async () => {
    if (isGuest) return;
    Alert.alert(
      isAr ? 'تغيير الصورة' : 'Change Photo',
      isAr ? 'اختر مصدر الصورة' : 'Select photo source',
      [
        { text: isAr ? 'الكاميرا' : 'Camera', onPress: launchCamera },
        { text: isAr ? 'المعرض' : 'Gallery', onPress: launchGallery },
        { text: isAr ? 'إلغاء' : 'Cancel', style: 'cancel' },
      ]
    );
  };

  const launchCamera = async () => {
    const perm = await ImagePicker.requestCameraPermissionsAsync();
    if (perm.granted) {
      const res = await ImagePicker.launchCameraAsync({ 
        base64: true, 
        quality: 0.3,
        allowsEditing: true,
        aspect: [1, 1],
      });
      if (!res.canceled && res.assets[0].base64) {
        update({ photo_url: `data:image/jpeg;base64,${res.assets[0].base64}` });
      }
    }
  };

  const launchGallery = async () => {
    const perm = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (perm.granted) {
      const res = await ImagePicker.launchImageLibraryAsync({ 
        base64: true, 
        quality: 0.3,
        allowsEditing: true,
        aspect: [1, 1],
      });
      if (!res.canceled && res.assets[0].base64) {
        update({ photo_url: `data:image/jpeg;base64,${res.assets[0].base64}` });
      }
    }
  };

  const displayName = [persona?.first_name, persona?.last_name].filter(Boolean).join(' ') 
    || user?.email?.split('@')[0] 
    || (isAr ? 'مستخدم' : 'Touri User');

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

        {/* ── Avatar + identity block (Notion-style centered B&W line art) ── */}
        <View style={styles.identityBlock}>
          <TouchableOpacity style={styles.avatarShell} onPress={pickImage} activeOpacity={0.8}>
            {persona?.photo_url ? (
              <Image source={{ uri: persona.photo_url }} style={styles.avatarImg} />
            ) : (
              <NotionAvatar
                id={user?.uid ?? user?.email ?? 'guest'}
                gender={persona?.gender === 'unspecified' ? undefined : persona?.gender}
                size={88}
              />
            )}
            {!isGuest && (
              <View style={styles.camBadge}>
                <Feather name="camera" size={13} color="#fff" />
              </View>
            )}
          </TouchableOpacity>
          <Text style={styles.displayName}>{displayName}</Text>
          <View style={styles.emailRow}>
            <Text style={styles.emailLine}>{user?.email || (isAr ? 'وضع الضيف' : 'Guest Mode')}</Text>
            {!isGuest && (
              <View style={styles.verifiedBadge}>
                <Feather name="check" size={10} color="#fff" />
              </View>
            )}
            {isGuest && (
              <Text style={styles.guestBadgeText}>{isAr ? 'حساب زائر' : 'Guest Mode'}</Text>
            )}
          </View>
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

        {/* ── Personal Information ── */}
        {!isGuest && persona && (
          <Section label={isAr ? 'البيانات الشخصية' : 'Personal Information'}>
            <PropRow icon="person-outline" label={isAr ? 'الاسم الأول' : 'First Name'}>
              <InlineInput
                value={persona.first_name || ''}
                placeholder={isAr ? 'أضف الاسم الأول' : 'Add first name'}
                onChangeText={(v) => update({ first_name: v })}
              />
            </PropRow>
            
            <PropRow icon="person-outline" label={isAr ? 'الاسم الأخير' : 'Last Name'}>
              <InlineInput
                value={persona.last_name || ''}
                placeholder={isAr ? 'أضف الاسم الأخير' : 'Add last name'}
                onChangeText={(v) => update({ last_name: v })}
              />
            </PropRow>

            <PropRow icon="mail-outline" label={isAr ? 'البريد الإلكتروني' : 'Email Address'}>
              <View style={styles.valuePill}>
                <Text style={[styles.valuePillTxt, { color: MUTED }]} numberOfLines={1}>
                  {user?.email}
                </Text>
              </View>
            </PropRow>

            <PropRow icon="transgender-outline" label={isAr ? 'الجنس' : 'Gender'}>
              <ToggleGroup
                value={persona.gender === 'unspecified' ? undefined : persona.gender}
                options={GENDER_OPTS.map((o) => ({ value: o.value, label: isAr ? o.ar : o.en }))}
                onChange={(v) => update({ gender: v })}
              />
            </PropRow>

            <PropRow icon="lock-closed-outline" label={isAr ? 'تغيير كلمة المرور' : 'Change Password'} last>
              <TouchableOpacity onPress={() => setPasswordModalOpen(true)} style={styles.valuePill}>
                <Text style={styles.valuePillTxt}>{isAr ? 'تعديل' : 'Edit'}</Text>
                <Feather name="chevron-right" size={11} color={MUTED} />
              </TouchableOpacity>
            </PropRow>
          </Section>
        )}

        {/* ── Preferences ── */}
        {!isGuest && persona && (
          <>
            <Section label={isAr ? 'التفضيلات' : 'Preferences'}>
              {/* Destination */}
              <PropRow icon="location-outline" label={isAr ? 'الوجهة' : 'Destination'}>
                <TouchableOpacity onPress={() => setDestModalOpen(true)} style={styles.valuePill}>
                  <Text style={styles.valuePillTxt} numberOfLines={1}>
                    {persona.preferred_destination || (isAr ? 'اضغط للتعديل' : 'Tap to set')}
                  </Text>
                  <Feather name="chevron-down" size={11} color={MUTED} />
                </TouchableOpacity>
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
              <PropRow icon="people-outline" label={isAr ? 'عدد المسافرين' : 'Travelers'}>
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

              {/* Food Allergies */}
              <PropRow icon="nutrition-outline" label={isAr ? 'الحساسية الغذائية' : 'Food Allergies'} last>
                <MultiChipGroup
                  selected={((persona.extras as Record<string, unknown>)?.allergies as string[]) ?? []}
                  options={ALLERGY_OPTS.map((o) => ({ value: o.value, label: isAr ? o.ar : o.en }))}
                  onChange={(values) =>
                    update({ extras: { ...(persona.extras || {}), allergies: values } })
                  }
                />
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
              <Ionicons name="log-out-outline" size={16} color={ERROR} style={{ width: 20 }} />
              <Text style={[styles.actionTxt, { color: ERROR }]}>
                {isAr ? 'تسجيل الخروج' : 'Sign Out'}
              </Text>
            </View>
            <Feather name="chevron-right" size={16} color={ERROR} />
          </TouchableOpacity>
        </Section>

        <Text style={styles.version}>Touri v2.0 · Egypt Travel AI · Offline RAG Mode</Text>
      </ScrollView>

      {/* ── Password Change Modal ── */}
      <Modal visible={passwordModalOpen} animationType="slide" transparent presentationStyle="overFullScreen">
        <View style={styles.modalOverlay}>
          <View style={styles.modalCard}>
            <View style={[styles.modalHeader, { flexDirection: isAr ? 'row-reverse' : 'row' }]}>
              <Text style={styles.modalTitle}>{isAr ? 'تغيير كلمة المرور' : 'Change Password'}</Text>
              <TouchableOpacity onPress={() => setPasswordModalOpen(false)}>
                <Feather name="x" size={22} color={MUTED} />
              </TouchableOpacity>
            </View>
            <View style={{ padding: 20, gap: 16 }}>
              <View style={{ gap: 8 }}>
                <Text style={styles.modalLabel}>{isAr ? 'كلمة المرور الحالية' : 'Current Password'}</Text>
                <TextInput style={[styles.modalInput, isAr && { textAlign: 'right' }]} secureTextEntry placeholder="••••••••" />
              </View>
              <View style={{ gap: 8 }}>
                <Text style={styles.modalLabel}>{isAr ? 'كلمة المرور الجديدة' : 'New Password'}</Text>
                <TextInput style={[styles.modalInput, isAr && { textAlign: 'right' }]} secureTextEntry placeholder="••••••••" />
              </View>
              <View style={{ gap: 8 }}>
                <Text style={styles.modalLabel}>{isAr ? 'تأكيد كلمة المرور' : 'Confirm Password'}</Text>
                <TextInput style={[styles.modalInput, isAr && { textAlign: 'right' }]} secureTextEntry placeholder="••••••••" />
              </View>
              <TouchableOpacity style={styles.saveBtn} onPress={() => setPasswordModalOpen(false)}>
                <Text style={styles.saveBtnTxt}>{isAr ? 'حفظ التغييرات' : 'Save Changes'}</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

      {/* ── Governorate picker modal ── */}
      <Modal visible={destModalOpen} animationType="slide" transparent presentationStyle="overFullScreen">
        <View style={styles.modalOverlay}>
          <View style={styles.modalCard}>
            <View style={[styles.modalHeader, { flexDirection: isAr ? 'row-reverse' : 'row' }]}>
              <Text style={styles.modalTitle}>{isAr ? 'اختر المحافظة' : 'Select Governorate'}</Text>
              <TouchableOpacity onPress={() => setDestModalOpen(false)}>
                <Feather name="x" size={22} color={MUTED} />
              </TouchableOpacity>
            </View>
            <ScrollView showsVerticalScrollIndicator={false}>
              {EGYPT_GOVERNORATES.map((gov) => {
                const active = persona?.preferred_destination === gov;
                return (
                  <TouchableOpacity
                    key={gov}
                    style={[styles.modalRow, active && { backgroundColor: `${PRIMARY}10` }]}
                    onPress={() => {
                      update({ preferred_destination: gov });
                      setDestModalOpen(false);
                    }}
                  >
                    <Text style={[styles.modalRowTxt, active && { color: PRIMARY, fontWeight: '700' }]}>
                      {gov}
                    </Text>
                    {active && <Feather name="check" size={16} color={PRIMARY} />}
                  </TouchableOpacity>
                );
              })}
            </ScrollView>
          </View>
        </View>
      </Modal>
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
    alignItems: 'center', gap: 10,
    backgroundColor: SURFACE, borderRadius: RADIUS,
    paddingVertical: 24, paddingHorizontal: SPACING,
    borderWidth: 1, borderColor: BORDER_COLOR,
  },
  avatarShell: { position: 'relative' },
  avatarImg: { width: 88, height: 88, borderRadius: 44 },
  avatarFallback: {
    width: 88, height: 88, borderRadius: 44,
    backgroundColor: `${PRIMARY}20`,
    alignItems: 'center', justifyContent: 'center',
  },
  camBadge: {
    position: 'absolute', bottom: 0, right: 0,
    backgroundColor: '#000', width: 28, height: 28, borderRadius: 14,
    alignItems: 'center', justifyContent: 'center',
    borderWidth: 2.5, borderColor: SURFACE,
  },
  avatarLetters: { fontSize: 22, fontWeight: '800', color: PRIMARY },
  displayName: { fontSize: 22, fontWeight: '800', color: TEXT, textAlign: 'center', letterSpacing: -0.3 },
  emailRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  emailLine: { fontSize: 13, color: MUTED },
  verifiedBadge: {
    width: 18, height: 18, borderRadius: 9,
    backgroundColor: '#34C759', alignItems: 'center', justifyContent: 'center',
  },
  guestBadgeText: {
    fontSize: 11, fontWeight: '600', color: '#FF9500',
    backgroundColor: '#FFF3E0', paddingHorizontal: 8, paddingVertical: 2,
    borderRadius: 8, overflow: 'hidden',
  },

  errTxt: { color: ERROR, fontSize: 13, textAlign: 'center', marginTop: -8 },

  // ── Guest block ──
  guestBlock: {
    alignItems: 'center', gap: 10, padding: 24,
  },
  guestIconWrap: {
    width: 52, height: 52, borderRadius: RADIUS,
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
    backgroundColor: BG, borderRadius: RADIUS_SM,
    paddingHorizontal: 10, paddingVertical: 6,
    maxWidth: 180,
  },
  valuePillTxt: { fontSize: 13, fontWeight: '600', color: TEXT, flex: 1, textAlign: 'right' },

  // ── Stepper ──
  stepper: { flexDirection: 'row', alignItems: 'center', gap: 14 },
  stepBtn: {
    width: 30, height: 30, borderRadius: RADIUS_SM,
    backgroundColor: BG, alignItems: 'center', justifyContent: 'center',
    borderWidth: 1, borderColor: BORDER_COLOR,
  },
  stepVal: { fontSize: 17, fontWeight: '800', color: TEXT, minWidth: 24, textAlign: 'center' },

  // ── Language buttons ──
  langBtn: {
    paddingHorizontal: 14, paddingVertical: 6,
    borderRadius: 20, borderWidth: 1.5, borderColor: BORDER_COLOR,
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

  version: { textAlign: 'center', fontSize: 11, color: PLACEHOLDER, paddingBottom: 8 },

  // ── Modal ──
  modalOverlay: {
    flex: 1, backgroundColor: 'rgba(0,0,0,0.35)',
    justifyContent: 'flex-end',
  },
  modalCard: {
    backgroundColor: SURFACE,
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    paddingTop: 16,
    paddingBottom: 40,
    maxHeight: '80%',
  },
  modalHeader: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: 20, paddingBottom: 12,
    borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: BORDER_COLOR,
  },
  modalTitle: { fontSize: 16, fontWeight: '700', color: TEXT },
  modalRow: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: 20, paddingVertical: 14,
    borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: BORDER_COLOR,
  },
  modalRowTxt: { fontSize: 14, color: TEXT, fontWeight: '500' },
  modalLabel: { fontSize: 13, fontWeight: '600', color: TEXT },
  modalInput: {
    backgroundColor: BG,
    borderWidth: 1, borderColor: BORDER_COLOR,
    borderRadius: RADIUS_SM,
    paddingHorizontal: 14, paddingVertical: 12,
    fontSize: 15, color: TEXT,
  },
  saveBtn: {
    backgroundColor: PRIMARY,
    borderRadius: RADIUS,
    paddingVertical: 14,
    alignItems: 'center', marginTop: 10,
  },
  saveBtnTxt: { color: '#fff', fontSize: 15, fontWeight: '700' },
});
