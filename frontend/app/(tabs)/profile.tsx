import { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Image,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Feather, Ionicons, MaterialIcons } from '@expo/vector-icons';
import { useTranslation } from 'react-i18next';
import { useRouter } from 'expo-router';
import { LinearGradient } from 'expo-linear-gradient';

import { Colors } from '@/constants/Colors';
import { applyLanguage, type AppLanguage } from '@/i18n';
import { GUEST_LIMITS, useAuth } from '@/hooks/useAuth';
import { api, getOrCreateUserId, type PersonaWrite, type UserPersona } from '@/services/api';

const TOURISM: { value: 'leisure' | 'medical'; labelEn: string; labelAr: string; icon: keyof typeof Ionicons.glyphMap }[] = [
  { value: 'leisure', labelEn: 'Leisure', labelAr: 'ترفيهية', icon: 'sunny-outline' },
  { value: 'medical', labelEn: 'Medical', labelAr: 'علاجية', icon: 'medkit-outline' },
];

const BUDGETS: { value: 'economy' | 'mid_range' | 'luxury'; labelEn: string; labelAr: string; icon: keyof typeof Ionicons.glyphMap; color: string }[] = [
  { value: 'economy',   labelEn: 'Economy',   labelAr: 'اقتصادي', icon: 'leaf-outline',     color: '#059669' },
  { value: 'mid_range', labelEn: 'Mid-range',  labelAr: 'متوسط',   icon: 'card-outline',     color: '#0284C7' },
  { value: 'luxury',    labelEn: 'Luxury',     labelAr: 'فاخر',    icon: 'diamond-outline',  color: '#7C3AED' },
];

// ── Persona stat badge ─────────────────────────────────────────────────────────
function StatBadge({ icon, label, value, color = '#00A896' }: {
  icon: keyof typeof Ionicons.glyphMap;
  label: string;
  value: string | number;
  color?: string;
}) {
  return (
    <View style={[badgeStyles.badge, { borderColor: `${color}30` }]}>
      <View style={[badgeStyles.iconWrap, { backgroundColor: `${color}15` }]}>
        <Ionicons name={icon} size={16} color={color} />
      </View>
      <Text style={badgeStyles.value}>{value}</Text>
      <Text style={badgeStyles.label}>{label}</Text>
    </View>
  );
}
const badgeStyles = StyleSheet.create({
  badge: { flex: 1, alignItems: 'center', gap: 4, padding: 12, borderRadius: 16, borderWidth: 1, backgroundColor: '#fff' },
  iconWrap: { width: 32, height: 32, borderRadius: 10, alignItems: 'center', justifyContent: 'center' },
  value: { fontSize: 15, fontWeight: '800', color: '#1C1C1E' },
  label: { fontSize: 10, color: '#8E8E93', fontWeight: '600', textTransform: 'uppercase', letterSpacing: 0.4 },
});

// ── Section card ──────────────────────────────────────────────────────────────
function SettingCard({ title, icon, color = '#8E8E93', children }: {
  title: string;
  icon: keyof typeof Ionicons.glyphMap;
  color?: string;
  children: React.ReactNode;
}) {
  return (
    <View style={cardStyles.card}>
      <View style={cardStyles.header}>
        <View style={[cardStyles.iconWrap, { backgroundColor: `${color}18` }]}>
          <Ionicons name={icon} size={16} color={color} />
        </View>
        <Text style={cardStyles.title}>{title}</Text>
      </View>
      {children}
    </View>
  );
}
const cardStyles = StyleSheet.create({
  card: { backgroundColor: '#fff', borderRadius: 20, padding: 18, gap: 14, shadowColor: '#000', shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.05, shadowRadius: 8, elevation: 2 },
  header: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  iconWrap: { width: 30, height: 30, borderRadius: 9, alignItems: 'center', justifyContent: 'center' },
  title: { fontSize: 14, fontWeight: '700', color: '#8E8E93', textTransform: 'uppercase', letterSpacing: 0.5 },
});

export default function ProfileScreen() {
  const { t, i18n } = useTranslation();
  const { user, isGuest, signOut } = useAuth();
  const router = useRouter();
  const isAr = i18n.language === 'ar';

  const [persona, setPersona] = useState<UserPersona | null>(null);
  const [loadErr, setLoadErr] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

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
    setPersona({ ...persona, ...(changes as Partial<UserPersona>) });
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
    if (persona) {
      const nextExtras = { ...(persona.extras || {}), language_preference: lang };
      await update({ extras: nextExtras });
    }
  };

  const handleSignOut = async () => {
    await signOut();
    router.replace('/');
  };

  const budgetColor = BUDGETS.find((b) => b.value === persona?.budget_bracket)?.color ?? '#8E8E93';

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* ── Header ── */}
      <View style={[styles.header, { flexDirection: isAr ? 'row-reverse' : 'row' }]}>
        <Text style={styles.headerTitle}>{isAr ? 'الملف الشخصي' : 'Profile'}</Text>
        {saving && <ActivityIndicator size="small" color="#00A896" />}
      </View>

      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
        {/* ── Hero card ── */}
        <LinearGradient
          colors={['#00A896', '#028090']}
          start={{ x: 0, y: 0 }}
          end={{ x: 1, y: 1 }}
          style={styles.heroCard}
        >
          <View style={styles.avatarWrap}>
            <Image
              source={{ uri: 'https://lh3.googleusercontent.com/aida-public/AB6AXuCpO7gZzXXTZDL5yRCrLEHL_isGfSt1h4-PzCHdvKFBUtAWj5Q-xFURHfyGE2PilbyHE4WsoE0dJp0sVSim98DBd-a0F-7V7VxG8h2dDd3zmzOBDQaZJFhPS8eBv56aze9cEmNoov3ZlTuVCDSQkIVHpVEhjbGWe_nXw_YCGnQlcyD0tg4_yQZj8fsm6I6oWGhjSxOGwA--xAvXevncLwGIjbTvq2-rSgzmqhp1ddWi1tgUM2knzKpQxWCrsX1lWDYckr3gcSkIiAM' }}
              style={styles.avatar}
            />
            {saving && (
              <View style={styles.savingDot}>
                <ActivityIndicator size="small" color="#00A896" />
              </View>
            )}
          </View>
          <Text style={styles.heroName}>{user?.email?.split('@')[0] || 'Tripmind User'}</Text>
          <Text style={styles.heroEmail}>{user?.email || (isAr ? 'وضع الضيف' : 'Guest Mode')}</Text>

          {/* Persona summary chips */}
          {persona && (
            <View style={styles.heroPills}>
              {persona.tourism_type && (
                <View style={styles.heroPill}>
                  <Ionicons name={persona.tourism_type === 'medical' ? 'medkit-outline' : 'sunny-outline'} size={12} color="rgba(255,255,255,0.9)" />
                  <Text style={styles.heroPillTxt}>{isAr ? (persona.tourism_type === 'medical' ? 'علاجية' : 'ترفيهية') : persona.tourism_type}</Text>
                </View>
              )}
              {persona.budget_bracket && (
                <View style={styles.heroPill}>
                  <Ionicons name="wallet-outline" size={12} color="rgba(255,255,255,0.9)" />
                  <Text style={styles.heroPillTxt}>{isAr ? BUDGETS.find(b => b.value === persona.budget_bracket)?.labelAr : BUDGETS.find(b => b.value === persona.budget_bracket)?.labelEn}</Text>
                </View>
              )}
              {persona.preferred_destination && (
                <View style={styles.heroPill}>
                  <Ionicons name="location-outline" size={12} color="rgba(255,255,255,0.9)" />
                  <Text style={styles.heroPillTxt}>{persona.preferred_destination}</Text>
                </View>
              )}
            </View>
          )}
        </LinearGradient>

        {/* ── Stat row ── */}
        {persona && (
          <View style={styles.statRow}>
            <StatBadge
              icon="people-outline"
              label={isAr ? 'مسافرون' : 'Travelers'}
              value={persona.party_size ?? 1}
              color="#0284C7"
            />
            <StatBadge
              icon="location-outline"
              label={isAr ? 'الوجهة' : 'Destination'}
              value={persona.preferred_destination || '—'}
              color="#00A896"
            />
            <StatBadge
              icon="diamond-outline"
              label={isAr ? 'ميزانية' : 'Budget'}
              value={isAr ? BUDGETS.find(b => b.value === persona.budget_bracket)?.labelAr ?? '—' : BUDGETS.find(b => b.value === persona.budget_bracket)?.labelEn ?? '—'}
              color={budgetColor}
            />
          </View>
        )}

        {loadErr && (
          <Text style={styles.error}>{isAr ? `خطأ: ${loadErr}` : `Error: ${loadErr}`}</Text>
        )}

        {/* ── Guest panel ── */}
        {isGuest && (
          <View style={styles.guestCard}>
            <MaterialIcons name="lock-outline" size={32} color="#00A896" />
            <Text style={styles.guestTitle}>{isAr ? 'ميزات كاملة بعد تسجيل الدخول' : 'Full features after sign in'}</Text>
            <Text style={styles.guestSub}>{isAr ? 'سجّل دخولك لحفظ تفضيلاتك وخططك' : 'Sign in to save your preferences and trip plans'}</Text>
            <TouchableOpacity style={styles.signInBtn} onPress={handleSignOut}>
              <Text style={styles.signInBtnTxt}>{isAr ? 'تسجيل الدخول' : 'Sign In'}</Text>
            </TouchableOpacity>
          </View>
        )}

        {/* ── Settings ── */}
        {!isGuest && persona && (
          <>
            {/* Language */}
            <SettingCard title={isAr ? 'اللغة' : 'Language'} icon="globe-outline" color="#0284C7">
              <View style={styles.segRow}>
                {(['en', 'ar'] as AppLanguage[]).map((lang) => (
                  <TouchableOpacity
                    key={lang}
                    style={[styles.segBtn, i18n.language === lang && styles.segBtnActive]}
                    onPress={() => handleLanguage(lang)}
                  >
                    <Text style={[styles.segTxt, i18n.language === lang && styles.segTxtActive]}>
                      {lang === 'en' ? 'English' : 'العربية'}
                    </Text>
                  </TouchableOpacity>
                ))}
              </View>
            </SettingCard>

            {/* Tourism type */}
            <SettingCard title={isAr ? 'نوع السياحة' : 'Tourism Type'} icon="compass-outline" color="#DB2777">
              <View style={styles.optRow}>
                {TOURISM.map((opt) => {
                  const active = persona.tourism_type === opt.value;
                  return (
                    <TouchableOpacity
                      key={opt.value}
                      style={[styles.optBtn, active && { borderColor: '#DB2777', backgroundColor: '#FDF2F8' }]}
                      onPress={() => update({ tourism_type: opt.value })}
                    >
                      <Ionicons name={opt.icon} size={18} color={active ? '#DB2777' : '#8E8E93'} />
                      <Text style={[styles.optTxt, active && { color: '#DB2777', fontWeight: '700' }]}>
                        {isAr ? opt.labelAr : opt.labelEn}
                      </Text>
                    </TouchableOpacity>
                  );
                })}
              </View>
            </SettingCard>

            {/* Budget bracket */}
            <SettingCard title={isAr ? 'الميزانية' : 'Budget Bracket'} icon="wallet-outline" color="#7C3AED">
              <View style={styles.optRow}>
                {BUDGETS.map((opt) => {
                  const active = persona.budget_bracket === opt.value;
                  return (
                    <TouchableOpacity
                      key={opt.value}
                      style={[styles.optBtn, active && { borderColor: opt.color, backgroundColor: `${opt.color}10` }]}
                      onPress={() => update({ budget_bracket: opt.value })}
                    >
                      <Ionicons name={opt.icon} size={18} color={active ? opt.color : '#8E8E93'} />
                      <Text style={[styles.optTxt, active && { color: opt.color, fontWeight: '700' }]}>
                        {isAr ? opt.labelAr : opt.labelEn}
                      </Text>
                    </TouchableOpacity>
                  );
                })}
              </View>
            </SettingCard>

            {/* Party size */}
            <SettingCard title={isAr ? 'عدد المسافرين' : 'Party Size'} icon="people-outline" color="#0284C7">
              <View style={styles.counterRow}>
                <TouchableOpacity
                  style={styles.counterBtn}
                  onPress={() => update({ party_size: Math.max(1, persona.party_size - 1) })}
                >
                  <MaterialIcons name="remove" size={20} color="#1C1C1E" />
                </TouchableOpacity>
                <View style={styles.counterVal}>
                  <Text style={styles.counterNum}>{persona.party_size ?? 1}</Text>
                  <Text style={styles.counterLbl}>{isAr ? 'شخص' : 'people'}</Text>
                </View>
                <TouchableOpacity
                  style={styles.counterBtn}
                  onPress={() => update({ party_size: Math.min(20, persona.party_size + 1) })}
                >
                  <MaterialIcons name="add" size={20} color="#1C1C1E" />
                </TouchableOpacity>
              </View>
            </SettingCard>

            {/* Preferred destination */}
            <SettingCard title={isAr ? 'الوجهة المفضلة' : 'Preferred Destination'} icon="location-outline" color="#00A896">
              <View style={styles.destRow}>
                <Ionicons name="search-outline" size={16} color="#8E8E93" />
                <TextInput
                  style={[styles.destInput, { textAlign: isAr ? 'right' : 'left' }]}
                  placeholder={isAr ? 'مثلاً: الغردقة' : 'e.g. Hurghada'}
                  placeholderTextColor="#C7C7CC"
                  value={persona.preferred_destination ?? ''}
                  onChangeText={(v) => setPersona((p) => p ? { ...p, preferred_destination: v } : p)}
                  onBlur={() => persona && update({ preferred_destination: persona.preferred_destination || undefined })}
                />
              </View>
            </SettingCard>
          </>
        )}

        {/* ── Sign Out ── */}
        <TouchableOpacity style={styles.signOutBtn} onPress={handleSignOut}>
          <Ionicons name="log-out-outline" size={20} color="#FF3B30" />
          <Text style={styles.signOutTxt}>{isAr ? 'تسجيل الخروج' : 'Sign Out'}</Text>
        </TouchableOpacity>

        <Text style={styles.versionTxt}>Tripmind v1.0 · Egypt Travel AI</Text>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F8FAFC' },
  header: {
    paddingHorizontal: 24, paddingVertical: 14,
    justifyContent: 'space-between', alignItems: 'center',
  },
  headerTitle: { fontSize: 28, fontWeight: '800', color: '#1C1C1E', letterSpacing: -0.5 },

  scroll: { paddingHorizontal: 20, paddingBottom: 120, gap: 16 },

  heroCard: {
    borderRadius: 24, padding: 24,
    alignItems: 'center', gap: 6,
    shadowColor: '#00A896', shadowOffset: { width: 0, height: 8 }, shadowOpacity: 0.25, shadowRadius: 16, elevation: 8,
  },
  avatarWrap: { position: 'relative', marginBottom: 4 },
  avatar: { width: 72, height: 72, borderRadius: 36, borderWidth: 3, borderColor: 'rgba(255,255,255,0.5)' },
  savingDot: {
    position: 'absolute', bottom: -4, right: -4,
    width: 22, height: 22, borderRadius: 11,
    backgroundColor: '#fff', alignItems: 'center', justifyContent: 'center',
  },
  heroName: { fontSize: 22, fontWeight: '800', color: '#fff', marginTop: 4 },
  heroEmail: { fontSize: 13, color: 'rgba(255,255,255,0.75)' },
  heroPills: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, justifyContent: 'center', marginTop: 8 },
  heroPill: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    backgroundColor: 'rgba(255,255,255,0.2)',
    paddingHorizontal: 10, paddingVertical: 4, borderRadius: 20,
  },
  heroPillTxt: { fontSize: 12, color: '#fff', fontWeight: '600', textTransform: 'capitalize' },

  statRow: { flexDirection: 'row', gap: 10 },

  error: { color: '#FF3B30', fontSize: 13, textAlign: 'center' },

  guestCard: {
    backgroundColor: '#fff', borderRadius: 20, padding: 24,
    alignItems: 'center', gap: 10,
    shadowColor: '#000', shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.05, shadowRadius: 8, elevation: 2,
  },
  guestTitle: { fontSize: 18, fontWeight: '700', color: '#1C1C1E', textAlign: 'center' },
  guestSub: { fontSize: 13, color: '#8E8E93', textAlign: 'center', lineHeight: 20 },
  signInBtn: {
    marginTop: 4, backgroundColor: '#00A896',
    paddingHorizontal: 32, paddingVertical: 12, borderRadius: 14,
  },
  signInBtnTxt: { color: '#fff', fontWeight: '700', fontSize: 15 },

  segRow: { flexDirection: 'row', gap: 8 },
  segBtn: {
    flex: 1, paddingVertical: 10, borderRadius: 12,
    backgroundColor: '#F2F2F7', alignItems: 'center',
  },
  segBtnActive: { backgroundColor: '#00A896' },
  segTxt: { fontSize: 14, fontWeight: '600', color: '#8E8E93' },
  segTxtActive: { color: '#fff' },

  optRow: { flexDirection: 'row', gap: 10, flexWrap: 'wrap' },
  optBtn: {
    flex: 1, minWidth: 90,
    flexDirection: 'row', alignItems: 'center', gap: 6,
    paddingVertical: 10, paddingHorizontal: 12,
    borderRadius: 12, borderWidth: 1.5, borderColor: '#E5E5EA',
  },
  optTxt: { fontSize: 13, fontWeight: '600', color: '#8E8E93' },

  counterRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  counterBtn: {
    width: 44, height: 44, borderRadius: 14,
    backgroundColor: '#F2F2F7', alignItems: 'center', justifyContent: 'center',
  },
  counterVal: { alignItems: 'center', gap: 2 },
  counterNum: { fontSize: 28, fontWeight: '800', color: '#1C1C1E' },
  counterLbl: { fontSize: 11, color: '#8E8E93', fontWeight: '600', textTransform: 'uppercase', letterSpacing: 0.4 },

  destRow: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    backgroundColor: '#F8FAFC', borderRadius: 12, paddingHorizontal: 12, paddingVertical: 10,
    borderWidth: 1, borderColor: '#E5E5EA',
  },
  destInput: { flex: 1, fontSize: 15, color: '#1C1C1E' },

  signOutBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
    backgroundColor: '#fff', borderRadius: 16, paddingVertical: 16,
    shadowColor: '#000', shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.05, shadowRadius: 8, elevation: 2,
  },
  signOutTxt: { color: '#FF3B30', fontSize: 16, fontWeight: '700' },

  versionTxt: { textAlign: 'center', fontSize: 12, color: '#C7C7CC', paddingBottom: 8 },
});
