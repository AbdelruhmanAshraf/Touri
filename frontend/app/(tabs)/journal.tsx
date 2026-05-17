/**
 * Live "Itinerary" tab.
 *
 * Reads the last trip the chat tab saved (``saveLastTrip``) and renders the
 * Travel Planner's day-by-day plan + the Budget Specialist's breakdown.
 * Zero mocks.
 */

import { useEffect, useState } from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  TouchableOpacity,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import { MaterialIcons, Feather, Ionicons } from '@expo/vector-icons';
import { useTranslation } from 'react-i18next';
import { useFocusEffect } from 'expo-router';
import { useCallback } from 'react';

import { Colors } from '@/constants/Colors';
import { getLastTrip, type LastTrip } from '@/services/api';

const ACTIVITY_ICON: Record<string, keyof typeof MaterialIcons.glyphMap> = {
  attraction: 'place',
  restaurant: 'restaurant',
  hotel: 'hotel',
  transport: 'directions-bus',
  medical: 'local-hospital',
};

export default function JournalScreen() {
  const { t, i18n } = useTranslation();
  const isAr = i18n.language === 'ar';
  const writingDirection = isAr ? 'rtl' : 'ltr';

  const [trip, setTrip] = useState<LastTrip | null>(null);

  const refresh = useCallback(() => {
    getLastTrip().then(setTrip).catch(() => setTrip(null));
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
  const city = trip?.itinerary?.city;
  const duration = trip?.itinerary?.duration;

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
          <View
            style={[styles.budgetHeader, { flexDirection: isAr ? 'row-reverse' : 'row' }]}
          >
            <Text style={[styles.budgetTitle, { writingDirection }]}>
              {t('itinerary.totalBudget')}
            </Text>
            <Ionicons name="wallet-outline" size={24} color={Colors.primaryFixedDim} />
          </View>
          <Text style={styles.budgetAmount}>
            {total != null ? `$${total.toLocaleString()}` : '—'}
          </Text>
          {perPerson != null && (
            <Text style={[styles.perPerson, { writingDirection }]}>
              {t('itinerary.perPerson', { amount: `$${perPerson.toLocaleString()}` })}
            </Text>
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

        {days.length === 0 ? (
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
            {days.map((d, idx) => (
              <View key={d.day} style={styles.dayBlock}>
                {idx < days.length - 1 && <View style={styles.timelineLine} />}
                <View style={styles.timelineDot} />
                <View style={styles.dayCard}>
                  <Text style={[styles.dayLabel, { writingDirection }]}>
                    {d.date_label || `Day ${d.day}`}
                  </Text>
                  {(d.activities || []).map((a, i) => {
                    const icon =
                      ACTIVITY_ICON[a.type || ''] ?? 'check-circle-outline';
                    return (
                      <View
                        key={i}
                        style={[
                          styles.activityRow,
                          { flexDirection: isAr ? 'row-reverse' : 'row' },
                        ]}
                      >
                        <MaterialIcons name={icon} size={18} color={Colors.primary} />
                        <View style={{ flex: 1 }}>
                          <Text style={[styles.activityTitle, { writingDirection }]}>
                            {a.emoji ? `${a.emoji} ` : ''}
                            {a.title}
                          </Text>
                          {a.time && (
                            <Text style={[styles.activityTime, { writingDirection }]}>
                              {a.time}
                            </Text>
                          )}
                        </View>
                      </View>
                    );
                  })}
                </View>
              </View>
            ))}
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
  scrollContent: { padding: 20, paddingBottom: 80 },
  budgetCard: {
    padding: 22,
    borderRadius: 24,
    marginBottom: 24,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 10 },
    shadowOpacity: 0.18,
    shadowRadius: 20,
  },
  budgetHeader: { justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 },
  budgetTitle: { color: '#94a3b8', fontSize: 14, fontWeight: '600' },
  budgetAmount: { color: '#fff', fontSize: 36, fontWeight: '800', letterSpacing: -0.5 },
  perPerson: { color: '#cbd5e1', fontSize: 12, marginTop: 4, marginBottom: 16 },
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
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: '#fff',
    borderRadius: 999,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderWidth: 1,
    borderColor: Colors.outlineVariant,
  },
  metaPillText: { fontSize: 12, color: Colors.onSurface, fontWeight: '500' },

  sectionTitle: { fontSize: 18, fontWeight: '700', color: Colors.onSurface, marginBottom: 16 },

  emptyCard: {
    backgroundColor: '#fff',
    borderRadius: 16,
    padding: 24,
    borderWidth: 1,
    borderColor: Colors.outlineVariant,
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
    backgroundColor: '#fff',
    padding: 16,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: Colors.outlineVariant,
    gap: 10,
  },
  dayLabel: {
    fontSize: 13,
    fontWeight: '700',
    color: Colors.primary,
    textTransform: 'uppercase',
    letterSpacing: 0.8,
    marginBottom: 4,
  },
  activityRow: { alignItems: 'center', gap: 10 },
  activityTitle: { fontSize: 14, fontWeight: '600', color: Colors.onSurface },
  activityTime: { fontSize: 12, color: Colors.onSurfaceVariant },
});
