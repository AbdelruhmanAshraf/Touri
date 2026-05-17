import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { Feather, Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';

export default function PlaceScreen() {
  const router = useRouter();

  return (
    <View style={styles.container}>
      <LinearGradient
        colors={['#94a3b8', '#334155']}
        style={StyleSheet.absoluteFill}
      />
      
      <LinearGradient
        colors={['rgba(0,0,0,0.1)', 'rgba(0,0,0,0.8)']}
        style={StyleSheet.absoluteFill}
      />

      <SafeAreaView style={styles.content}>
        <View style={styles.header}>
          <TouchableOpacity style={styles.glassIcon} onPress={() => router.back()}>
            <Feather name="chevron-left" size={24} color="#fff" />
          </TouchableOpacity>
          <Text style={styles.headerTitle}>Place Overview</Text>
          <TouchableOpacity style={styles.glassIcon}>
            <Feather name="more-horizontal" size={24} color="#fff" />
          </TouchableOpacity>
        </View>

        <View style={styles.bottomSection}>
          <Text style={styles.subhead}>Mount</Text>
          <Text style={styles.title}>Daisen(いせ)</Text>
          
          <Text style={styles.description}>
            Absolutely breathtaking views! The hike was challenging but rewarding. Highly recommend visiting during the autumn for the vibrant foliage...
          </Text>

          <View style={styles.footerRow}>
            <View>
              <Text style={styles.reviewsLabel}>Reviews</Text>
              <View style={styles.ratingRow}>
                <Text style={styles.ratingScore}>4.8</Text>
                <View style={styles.stars}>
                  {[1,2,3,4,5].map(i => (
                    <Ionicons key={i} name="star" size={16} color="#14b8a6" />
                  ))}
                </View>
              </View>
              <Text style={styles.reviewsCount}>1.2k reviews</Text>
            </View>

            <TouchableOpacity style={styles.continueBtn} onPress={() => router.push('/(tabs)/chat')}>
              <Text style={styles.continueText}>CONTINUE</Text>
              <Feather name="arrow-up-right" size={18} color="#fff" style={{ marginLeft: 4 }} />
            </TouchableOpacity>
          </View>
        </View>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  content: { flex: 1, justifyContent: 'space-between' },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', padding: 20 },
  headerTitle: { fontSize: 16, fontWeight: '600', color: '#fff' },
  glassIcon: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: 'rgba(255,255,255,0.2)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  bottomSection: { padding: 24, paddingBottom: 40 },
  subhead: { fontSize: 24, color: '#e2e8f0', marginBottom: -4 },
  title: { fontSize: 48, fontWeight: '700', color: '#fff', marginBottom: 16 },
  description: { fontSize: 15, color: 'rgba(255,255,255,0.8)', lineHeight: 24, marginBottom: 32 },
  footerRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-end' },
  reviewsLabel: { color: '#fff', fontSize: 16, marginBottom: 8, fontWeight: '500' },
  ratingRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  ratingScore: { color: '#fff', fontSize: 24, fontWeight: '700' },
  stars: { flexDirection: 'row', gap: 2 },
  reviewsCount: { color: 'rgba(255,255,255,0.6)', fontSize: 13, marginTop: 4 },
  continueBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(255,255,255,0.2)',
    paddingHorizontal: 24,
    paddingVertical: 16,
    borderRadius: 30,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.3)',
  },
  continueText: { color: '#fff', fontSize: 14, fontWeight: '600' },
});
