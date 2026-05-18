import { useEffect, useState } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import { Feather, Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { getLastTrip, type LastTrip } from '@/services/api';

export default function ItineraryScreen() {
  const router = useRouter();
  const [trip, setTrip] = useState<LastTrip | null>(null);

  useEffect(() => {
    getLastTrip().then(setTrip).catch(() => setTrip(null));
  }, []);

  const total = trip?.budget_breakdown?.total_usd;
  const breakdown = trip?.budget_breakdown?.breakdown;
  const days = trip?.itinerary?.days ?? [];

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <LinearGradient colors={['#f8fafc', '#e0f2fe']} style={StyleSheet.absoluteFill} />

      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.iconBtn}>
          <Feather name="chevron-left" size={24} color="#1e293b" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Trip Itinerary</Text>
        <TouchableOpacity style={styles.iconBtn}>
          <Feather name="download" size={20} color="#1e293b" />
        </TouchableOpacity>
      </View>

      <ScrollView contentContainerStyle={styles.scrollContent}>
        {/* Budget Overview Card */}
        <LinearGradient colors={['#1e293b', '#0f172a']} style={styles.budgetCard}>
          <View style={styles.budgetHeader}>
            <Text style={styles.budgetTitle}>Total Estimated Budget</Text>
            <Ionicons name="wallet-outline" size={24} color="#14b8a6" />
          </View>
          <Text style={styles.budgetAmount}>
            {total != null ? `$${total.toLocaleString()}` : '—'}
          </Text>
          <View style={styles.budgetBreakdown}>
            {breakdown ? (
              Object.entries(breakdown).map(([k, v]) => (
                <View key={k} style={styles.budgetItem}>
                  <Text style={styles.budgetLabel}>
                    {k.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
                  </Text>
                  <Text style={styles.budgetValue}>
                    {typeof v === 'number' ? `$${v.toLocaleString()}` : String(v)}
                  </Text>
                </View>
              ))
            ) : (
              <Text style={styles.budgetLabel}>
                Plan a trip in chat to see your live budget breakdown.
              </Text>
            )}
          </View>
        </LinearGradient>

        <Text style={styles.sectionTitle}>Day-by-Day Plan</Text>

        {/* Timeline Items */}
        <View style={styles.timelineContainer}>
          {days.length === 0 ? (
            <TimelineItem
              day="Day 1"
              title="No itinerary yet"
              desc="Ask Tripmind in chat to plan a trip — your day-by-day plan will appear here."
              type={trip?.tourism_type === 'medical' ? 'medical' : 'leisure'}
              isLast
            />
          ) : (
            days.map((d, idx) => {
              const first = d.activities?.[0];
              const title = first?.title || `Day ${d.day}`;
              const descParts = (d.activities ?? [])
                .slice(0, 3)
                .map((a) =>
                  [a.time, a.title].filter(Boolean).join(' — '),
                )
                .filter(Boolean);
              return (
                <TimelineItem
                  key={d.day}
                  day={d.date_label || `Day ${d.day}`}
                  title={title}
                  desc={descParts.join('  •  ') || 'Activities being curated…'}
                  type={
                    first?.type === 'hotel' || trip?.tourism_type === 'medical'
                      ? 'medical'
                      : 'leisure'
                  }
                  isLast={idx === days.length - 1}
                />
              );
            })
          )}
        </View>

      </ScrollView>
    </SafeAreaView>
  );
}

function TimelineItem({ day, title, desc, type, isLast }: any) {
  const isMed = type === 'medical';
  return (
    <View style={styles.timelineItem}>
      {!isLast && <View style={styles.timelineLine} />}
      <View style={[styles.timelineDot, { backgroundColor: isMed ? '#ef4444' : '#14b8a6' }]} />
      <View style={styles.timelineContent}>
        <Text style={styles.dayText}>{day}</Text>
        <View style={styles.timelineCard}>
          <Text style={styles.cardTitle}>{title}</Text>
          <Text style={styles.cardDesc}>{desc}</Text>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', padding: 20 },
  headerTitle: { fontSize: 18, fontWeight: '700', color: '#1e293b' },
  iconBtn: { width: 40, height: 40, borderRadius: 20, backgroundColor: 'rgba(255,255,255,0.7)', alignItems: 'center', justifyContent: 'center' },
  scrollContent: { padding: 24, paddingBottom: 60 },
  budgetCard: { padding: 24, borderRadius: 24, marginBottom: 32 },
  budgetHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 },
  budgetTitle: { color: '#94a3b8', fontSize: 14, fontWeight: '600' },
  budgetAmount: { color: '#fff', fontSize: 40, fontWeight: '800', marginBottom: 20 },
  budgetBreakdown: { borderTopWidth: 1, borderTopColor: 'rgba(255,255,255,0.1)', paddingTop: 16, gap: 8 },
  budgetItem: { flexDirection: 'row', justifyContent: 'space-between' },
  budgetLabel: { color: '#cbd5e1', fontSize: 14 },
  budgetValue: { color: '#fff', fontSize: 14, fontWeight: '600' },
  sectionTitle: { fontSize: 20, fontWeight: '700', color: '#1e293b', marginBottom: 24 },
  timelineContainer: { paddingLeft: 8 },
  timelineItem: { flexDirection: 'row', marginBottom: 24, position: 'relative' },
  timelineLine: { position: 'absolute', left: 7, top: 24, bottom: -24, width: 2, backgroundColor: '#cbd5e1' },
  timelineDot: { width: 16, height: 16, borderRadius: 8, marginTop: 4, marginRight: 16 },
  timelineContent: { flex: 1 },
  dayText: { fontSize: 14, fontWeight: '700', color: '#64748b', marginBottom: 8 },
  timelineCard: { backgroundColor: '#fff', padding: 16, borderRadius: 16, borderWidth: 1, borderColor: '#E5E5EA' },
  cardTitle: { fontSize: 16, fontWeight: '700', color: '#1e293b', marginBottom: 6 },
  cardDesc: { fontSize: 14, color: '#475569', lineHeight: 20 },
});
