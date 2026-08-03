/**
 * Live "Plan / الخطة" tab.
 *
 * Reads the last trip the chat tab saved (``saveLastTrip``) and renders the
 * Travel Planner's day-by-day plan + the Budget Specialist's breakdown.
 * Also accepts live updates from the chat's ui_trigger confirmation flow.
 * Zero mocks.
 */

import { useEffect, useState, useRef } from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  TouchableOpacity,
  ActivityIndicator,
  Animated,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import { MaterialIcons, Feather, Ionicons } from '@expo/vector-icons';
import { useTranslation } from 'react-i18next';
import { useFocusEffect } from 'expo-router';
import { useCallback } from 'react';
import { doc, onSnapshot } from 'firebase/firestore';

import { Colors } from '@/constants/Colors';
import { RADIUS_PILL, RADIUS_XL, flatCard, PRIMARY, SURFACE, BORDER_COLOR, BG, MUTED, TEXT, SUCCESS } from '@/theme/tokens';
import { db } from '@/config/firebaseConfig';
import { useAuth } from '@/hooks/useAuth';
import {
  getLastTrip,
  saveLastTrip,
  getOrCreateUserId,
  api,
  type LastTrip,
} from '@/services/api';

const ACTIVITY_ICON: Record<string, keyof typeof MaterialIcons.glyphMap> = {
  attraction: 'place',
  restaurant: 'restaurant',
  hotel: 'hotel',
  transport: 'directions-bus',
  medical: 'local-hospital',
};

const MUTED_ICON = '#cbd5e1';

export default function PlanScreen() {
  const { t, i18n } = useTranslation();
  const { user } = useAuth();
  const isAr = i18n.language === 'ar';
  const writingDirection = isAr ? 'rtl' : 'ltr';

  const [trip, setTrip] = useState<LastTrip | null>(null);
  const [loading, setLoading] = useState(true);
  const progressAnim = useRef(new Animated.Value(0)).current;

  // Firestore real-time listener for trip updates
  useEffect(() => {
    if (!user?.uid) return;
    const tripRef = doc(db, 'users', user.uid, 'trips', 'initial');
    const unsub = onSnapshot(tripRef, (snap) => {
      if (!snap.exists()) return;
      const data = snap.data();
      if (data?.itinerary) {
        const mapped: LastTrip = {
          itinerary: data.itinerary,
          budget_breakdown: data.budget_breakdown ?? null,
          country: data.destination ?? null,
          tourism_type: data.tourism_type ?? null,
          updated_at: data.updated_at ?? new Date().toISOString(),
        };
        setTrip(mapped);
        saveLastTrip(mapped);
        setLoading(false);
      }
    });
    return () => unsub();
  }, [user?.uid]);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      // 1) Prefer the most recent locally-saved trip (from chat interaction)
      let local = await getLastTrip();
      if (local) {
        setTrip(local);
        setLoading(false);
        return;
      }

      // 2) Fallback to the auto-generated onboarding trip on the backend
      const uid = await getOrCreateUserId();
      const initial = await api.getInitialTrip(uid);
      if (initial.found && initial.itinerary) {
        const mapped: LastTrip = {
          itinerary: initial.itinerary,
          budget_breakdown: initial.budget_breakdown ?? null,
          country: initial.destination ?? null,
          tourism_type: initial.tourism_type ?? null,
          updated_at: initial.generated_at ?? new Date().toISOString(),
        };
        await saveLastTrip(mapped);
        setTrip(mapped);
      } else {
        setTrip(null);
      }
    } catch {
      setTrip(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  // Re-pull whenever the tab regains focus so a freshly-saved chat reply
  // shows up immediately.
  useFocusEffect(
    useCallback(() => {
      refresh();
    }, [refresh]),
  );

  const days = trip?.itinerary?.days ?? [];
  const budget = trip?.budget_breakdown ?? null;
  const total = budget?.total_usd;
  const perPerson = budget?.per_person_usd;
  const breakdown = budget?.breakdown ?? {};
  const remainingBudget = budget?.remaining_budget ?? total;
  const city = trip?.itinerary?.city;
  const duration = trip?.itinerary?.duration;

  // Toggle activity checkbox — sync to Firestore instantly
  const toggleActivity = useCallback(async (dayIdx: number, activityIdx: number) => {
    if (!trip?.itinerary) return;

    const newDays = [...(trip.itinerary.days || [])];
    const day = { ...newDays[dayIdx] };
    const acts = [...(day.activities || [])];
    const act = { ...acts[activityIdx] };

    const cost = act.cost || 0;
    const isDone = !act.done;
    act.done = isDone;

    acts[activityIdx] = act;
    day.activities = acts;
    newDays[dayIdx] = day;

    const newItinerary = { ...trip.itinerary, days: newDays };

    let newBudget = trip.budget_breakdown;
    if (newBudget && total != null) {
      const currentRemaining = budget?.remaining_budget ?? total;
      newBudget = {
        ...newBudget,
        remaining_budget: isDone ? Math.max(0, currentRemaining - cost) : currentRemaining + cost,
      };
    }

    const updatedTrip = { ...trip, itinerary: newItinerary, budget_breakdown: newBudget };
    setTrip(updatedTrip);
    await saveLastTrip(updatedTrip);

    try {
      const uid = user?.uid ?? (await getOrCreateUserId());
      const res = await api.toggleActivity(uid, dayIdx, activityIdx, isDone);
      if (res.remaining_budget != null && newBudget) {
        const synced = { ...updatedTrip, budget_breakdown: { ...newBudget, remaining_budget: res.remaining_budget } };
        setTrip(synced);
        await saveLastTrip(synced);
      }
    } catch (e) {
      console.error('Failed to sync checklist', e);
    }
  }, [trip, budget, total, user?.uid]);

  // Calculate completion percentages (overall + per-day)
  let totalActs = 0;
  let doneActs = 0;
  const dayProgress: { total: number; done: number; pct: number }[] = [];
  days.forEach((d) => {
    let dayTotal = 0;
    let dayDone = 0;
    (d.activities || []).forEach((a) => {
      totalActs++;
      dayTotal++;
      if (a.done) { doneActs++; dayDone++; }
    });
    dayProgress.push({ total: dayTotal, done: dayDone, pct: dayTotal > 0 ? Math.round((dayDone / dayTotal) * 100) : 0 });
  });
  const completionPct = totalActs > 0 ? Math.round((doneActs / totalActs) * 100) : 0;

  // Animate the progress bar
  useEffect(() => {
    Animated.timing(progressAnim, {
      toValue: completionPct,
      duration: 400,
      useNativeDriver: false,
    }).start();
  }, [completionPct]);

  const budgetSpent = total != null && remainingBudget != null ? total - remainingBudget : 0;
  const budgetPct = total && total > 0 ? Math.min(100, Math.round((budgetSpent / total) * 100)) : 0;

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <LinearGradient
        colors={['#f8fafc', '#e0f2fe']}
        style={StyleSheet.absoluteFill}
      />

      <View
        style={[styles.header, { flexDirection: isAr ? 'row-reverse' : 'row' }]}
      >
        <Text style={[styles.headerTitle, { writingDirection }]}>
          {t('itinerary.title')}
        </Text>
        <TouchableOpacity style={styles.iconBtn} onPress={refresh}>
          <Feather name="refresh-cw" size={18} color={Colors.onSurface} />
        </TouchableOpacity>
      </View>

      <ScrollView contentContainerStyle={styles.scrollContent}>
        {/* Budget card */}
        <LinearGradient
          colors={['#1e293b', '#0f172a']}
          style={styles.budgetCard}
        >
          <View style={[styles.budgetHeader, { flexDirection: isAr ? 'row-reverse' : 'row' }]}>
            <Text style={[styles.budgetTitle, { writingDirection }]}>
              {t('itinerary.totalBudget')}
            </Text>
            <Ionicons name="wallet-outline" size={24} color={Colors.primaryFixedDim} />
          </View>

          {/* Core Budget Amounts */}
          <View style={[styles.budgetAmountRow, { flexDirection: isAr ? 'row-reverse' : 'row' }]}>
            <View>
              <Text style={styles.budgetAmount}>
                {remainingBudget != null ? `$${remainingBudget.toLocaleString()}` : '—'}
              </Text>
              <Text style={styles.budgetSubAmount}>
                {isAr ? 'المتبقي' : 'Remaining'} / {total != null ? `$${total.toLocaleString()}` : '—'}
              </Text>
            </View>
            <View>
              <Text style={[styles.completionText, { textAlign: isAr ? 'left' : 'right' }]}>
                {completionPct}% {isAr ? 'مكتمل' : 'Done'}
              </Text>
              {perPerson != null && (
                <Text style={[styles.perPerson, { textAlign: isAr ? 'left' : 'right' }]}>
                  {t('itinerary.perPerson', { amount: `$${perPerson.toLocaleString()}` })}
                </Text>
              )}
            </View>
          </View>

          {/* Trip completion progress bar */}
          <View style={{ gap: 4, marginBottom: 12 }}>
            <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
              <Text style={{ color: '#94a3b8', fontSize: 11, fontWeight: '600' }}>
                {isAr ? 'إنجاز الرحلة' : 'Trip Progress'}
              </Text>
              <Text style={{ color: Colors.primaryFixedDim, fontSize: 11, fontWeight: '700' }}>
                {doneActs}/{totalActs} {isAr ? 'نشاط' : 'activities'}
              </Text>
            </View>
            <View style={styles.progressBarBg}>
              <Animated.View style={[styles.progressBarFill, { width: progressAnim.interpolate({ inputRange: [0, 100], outputRange: ['0%', '100%'] }) }]} />
            </View>
          </View>

          {/* Budget spent indicator */}
          {total != null && total > 0 && (
            <View style={{ gap: 4, marginBottom: 16 }}>
              <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
                <Text style={{ color: '#94a3b8', fontSize: 11, fontWeight: '600' }}>
                  {isAr ? 'الميزانية المستخدمة' : 'Budget Used'}
                </Text>
                <Text style={{ color: budgetPct > 80 ? '#f87171' : Colors.primaryFixedDim, fontSize: 11, fontWeight: '700' }}>
                  {budgetPct}%
                </Text>
              </View>
              <View style={styles.progressBarBg}>
                <View style={[styles.progressBarFill, { width: `${budgetPct}%`, backgroundColor: budgetPct > 80 ? '#f87171' : Colors.primaryFixedDim }]} />
              </View>
            </View>
          )}

          <View style={styles.budgetBreakdown}>
            {Object.keys(breakdown).length === 0 ? (
              <Text style={[styles.budgetLabel, { writingDirection }]}>
                {t('itinerary.noBudget')}
              </Text>
            ) : (
              Object.entries(breakdown).map(([k, v]) => (
                <View
                  key={k}
                  style={[
                    styles.budgetItem,
                    { flexDirection: isAr ? 'row-reverse' : 'row' },
                  ]}
                >
                  <Text style={styles.budgetLabel}>
                    {(t(`itinerary.breakdown.${k}`, { defaultValue: k }) as string)}
                  </Text>
                  <Text style={styles.budgetValue}>
                    {typeof v === 'number' ? `$${v.toLocaleString()}` : String(v)}
                  </Text>
                </View>
              ))
            )}
          </View>
        </LinearGradient>

        {/* City + duration meta */}
        {(city || duration) && (
          <View style={styles.metaRow}>
            {city && (
              <View style={styles.metaPill}>
                <MaterialIcons name="place" size={14} color={Colors.primary} />
                <Text style={styles.metaPillText}>{city}</Text>
              </View>
            )}
            {duration && (
              <View style={styles.metaPill}>
                <MaterialIcons name="event" size={14} color={Colors.primary} />
                <Text style={styles.metaPillText}>
                  {t('itinerary.days', { count: duration })}
                </Text>
              </View>
            )}
          </View>
        )}

        <Text style={[styles.sectionTitle, { writingDirection }]}>
          {t('itinerary.dayByDay')}
        </Text>

        {loading ? (
          <View style={styles.loadingBox}>
            <ActivityIndicator size="large" color={Colors.primary} />
          </View>
        ) : days.length === 0 ? (
          <View style={styles.emptyCard}>
            <Text style={[styles.emptyTitle, { writingDirection }]}>
              {t('itinerary.noItinerary')}
            </Text>
            <Text style={[styles.emptyText, { writingDirection }]}>
              {t('itinerary.noItinerarySub')}
            </Text>
          </View>
        ) : (
          <View style={styles.timeline}>
            {days.map((d, idx) => {
              const dp = dayProgress[idx];
              return (
              <View key={d.day} style={styles.dayBlock}>
                {idx < days.length - 1 && <View style={styles.timelineLine} />}
                <View style={[styles.timelineDot, dp && dp.pct === 100 && { backgroundColor: SUCCESS }]} />
                <View style={styles.dayCard}>
                  <View style={[styles.dayHeaderRow, { flexDirection: isAr ? 'row-reverse' : 'row' }]}>
                    <Text style={[styles.dayLabel, { writingDirection }]}>
                      {d.date_label || `Day ${d.day}`}
                    </Text>
                    {dp && (
                      <Text style={[styles.dayPct, dp.pct === 100 && { color: SUCCESS }]}>
                        {dp.done}/{dp.total}
                      </Text>
                    )}
                  </View>
                  {dp && dp.total > 0 && (
                    <View style={styles.dayProgressBg}>
                      <View style={[styles.dayProgressFill, { width: `${dp.pct}%` }, dp.pct === 100 && { backgroundColor: SUCCESS }]} />
                    </View>
                  )}
                  {(d.activities || []).map((a, i) => {
                    const icon =
                      ACTIVITY_ICON[a.type || ''] ?? 'check-circle-outline';
                    const isDone = a.done;
                    const priceLabel = a.cost && a.cost > 0 ? `$${a.cost}` : null;
                    return (
                      <TouchableOpacity
                        key={i}
                        activeOpacity={0.7}
                        onPress={() => toggleActivity(idx, i)}
                        style={[
                          styles.activityRow,
                          { flexDirection: isAr ? 'row-reverse' : 'row' },
                          isDone && { opacity: 0.6 }
                        ]}
                      >
                        <MaterialIcons 
                          name={isDone ? "check-circle" : "radio-button-unchecked"} 
                          size={22} 
                          color={isDone ? Colors.primary : MUTED_ICON} 
                        />
                        <View style={{ flex: 1 }}>
                          <Text style={[
                            styles.activityTitle, 
                            { writingDirection },
                            isDone && { textDecorationLine: 'line-through', color: '#94a3b8' }
                          ]}>
                            {a.emoji ? `${a.emoji} ` : ''}
                            {a.title}
                          </Text>
                          <View style={[styles.activitySubRow, { flexDirection: isAr ? 'row-reverse' : 'row' }]}>
                            {a.time && (
                              <Text style={[styles.activityTime, { writingDirection }]}>
                                {a.time}
                              </Text>
                            )}
                            {priceLabel && (
                              <Text style={styles.activityPrice}>
                                •  {priceLabel}
                              </Text>
                            )}
                          </View>
                        </View>
                      </TouchableOpacity>
                    );
                  })}
                </View>
              </View>
              );
            })}
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  header: {
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 20,
  },
  headerTitle: { fontSize: 18, fontWeight: '700', color: Colors.onSurface },
  iconBtn: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: 'rgba(255,255,255,0.7)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  scrollContent: { padding: 20, paddingBottom: 40 },
  budgetCard: {
    padding: 22,
    borderRadius: RADIUS_XL,
    marginBottom: 24,
  },
  budgetHeader: { justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 },
  budgetTitle: { color: '#94a3b8', fontSize: 14, fontWeight: '600' },
  budgetAmountRow: { justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: 16 },
  budgetAmount: { color: '#fff', fontSize: 34, fontWeight: '800', letterSpacing: -0.5 },
  budgetSubAmount: { color: '#cbd5e1', fontSize: 13, marginTop: 2, fontWeight: '500' },
  completionText: { color: Colors.primaryFixedDim, fontSize: 14, fontWeight: '700', marginBottom: 2 },
  perPerson: { color: '#94a3b8', fontSize: 12 },
  progressBarBg: { height: 6, backgroundColor: 'rgba(255,255,255,0.1)', borderRadius: 3, marginBottom: 16, overflow: 'hidden' },
  progressBarFill: { height: '100%', backgroundColor: Colors.primaryFixedDim, borderRadius: 3 },

  budgetBreakdown: {
    borderTopWidth: 1,
    borderTopColor: 'rgba(255,255,255,0.1)',
    paddingTop: 14,
    gap: 8,
  },
  budgetItem: { justifyContent: 'space-between' },
  budgetLabel: { color: '#cbd5e1', fontSize: 13 },
  budgetValue: { color: '#fff', fontSize: 13, fontWeight: '600' },

  metaRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 16 },
  metaPill: {
    ...flatCard,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    borderRadius: RADIUS_PILL,
    paddingHorizontal: 12,
    paddingVertical: 6,
  },
  metaPillText: { fontSize: 12, color: Colors.onSurface, fontWeight: '500' },

  sectionTitle: { fontSize: 18, fontWeight: '700', color: Colors.onSurface, marginBottom: 16 },

  emptyCard: {
    ...flatCard,
    padding: 24,
  },
  emptyTitle: { fontSize: 16, fontWeight: '700', color: Colors.onSurface, marginBottom: 4 },
  emptyText: { fontSize: 14, color: Colors.onSurfaceVariant, lineHeight: 20 },

  timeline: { paddingLeft: 4 },
  dayBlock: { paddingLeft: 24, position: 'relative', paddingBottom: 22 },
  timelineLine: {
    position: 'absolute',
    left: 7,
    top: 18,
    bottom: 0,
    width: 2,
    backgroundColor: '#cbd5e1',
  },
  timelineDot: {
    position: 'absolute',
    left: 0,
    top: 4,
    width: 16,
    height: 16,
    borderRadius: 8,
    backgroundColor: Colors.primary,
  },
  dayCard: {
    ...flatCard,
    padding: 16,
    gap: 10,
  },
  dayHeaderRow: { justifyContent: 'space-between', alignItems: 'center', marginBottom: 2 },
  dayLabel: {
    fontSize: 13,
    fontWeight: '700',
    color: Colors.primary,
    textTransform: 'uppercase',
    letterSpacing: 0.8,
  },
  dayPct: { fontSize: 11, fontWeight: '600', color: MUTED },
  dayProgressBg: { height: 3, backgroundColor: BORDER_COLOR, borderRadius: 2, overflow: 'hidden', marginBottom: 4 },
  dayProgressFill: { height: '100%', backgroundColor: PRIMARY, borderRadius: 2 },
  activityRow: { alignItems: 'flex-start', gap: 10, paddingVertical: 4 },
  activityTitle: { fontSize: 15, fontWeight: '600', color: Colors.onSurface, marginBottom: 2 },
  activitySubRow: { alignItems: 'center', flexWrap: 'wrap' },
  activityTime: { fontSize: 12, color: Colors.onSurfaceVariant, fontWeight: '500' },
  activityPrice: { fontSize: 12, color: Colors.primary, fontWeight: '600' },
  loadingBox: { alignItems: 'center', justifyContent: 'center', paddingVertical: 40 },
});
