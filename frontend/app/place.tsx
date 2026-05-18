/**
 * Place Detail — native modal route (Phase 4).
 *
 * Replaces the hand-rolled PlaceSheet Animated.View + PanResponder.
 * The OS handles the sheet animation, gesture-to-dismiss, and accessibility.
 *
 * Navigation:
 *   router.push({ pathname: '/place', params: { type: 'hotel', id: '...' } })
 *
 * In the root _layout.tsx this screen must be declared with:
 *   <Stack.Screen name="place" options={{ presentation: 'modal' }} />
 */

import { useEffect, useState } from 'react';
import {
  Dimensions,
  Linking,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { Image } from 'expo-image';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Feather, Ionicons, MaterialIcons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { useLocalSearchParams, useRouter } from 'expo-router';

import { api, type CatalogItem, type CatalogItemType } from '@/services/api';
import { BORDER_COLOR, BG, MUTED, SURFACE, TEXT } from '@/theme/tokens';

const { width: SCREEN_W } = Dimensions.get('window');

// ── Type helpers ──────────────────────────────────────────────────────────────
function typeLabel(t: CatalogItemType): string {
  const map: Record<CatalogItemType, string> = {
    attraction: 'Attraction', hotel: 'Hotel', restaurant: 'Restaurant',
    transport: 'Transport', flight: 'Flight', event: 'Event', medical: 'Medical',
  };
  return map[t] ?? t;
}

function typeColor(t: CatalogItemType): string {
  const map: Record<CatalogItemType, string> = {
    attraction: '#00A896', hotel: '#7C3AED', restaurant: '#EA580C',
    transport: '#0284C7', flight: '#0369A1', event: '#DB2777', medical: '#059669',
  };
  return map[t] ?? '#00A896';
}

// ── Info row ──────────────────────────────────────────────────────────────────
function InfoRow({ icon, label, value, color = MUTED }: {
  icon: keyof typeof Ionicons.glyphMap;
  label: string;
  value?: string | null;
  color?: string;
}) {
  if (!value) return null;
  return (
    <View style={rowStyles.container}>
      <View style={[rowStyles.iconWrap, { backgroundColor: `${color}18` }]}>
        <Ionicons name={icon} size={16} color={color} />
      </View>
      <View style={{ flex: 1 }}>
        <Text style={rowStyles.label}>{label}</Text>
        <Text style={rowStyles.value}>{value}</Text>
      </View>
    </View>
  );
}

const rowStyles = StyleSheet.create({
  container: { flexDirection: 'row', alignItems: 'flex-start', gap: 12, marginBottom: 14 },
  iconWrap: { width: 32, height: 32, borderRadius: 8, alignItems: 'center', justifyContent: 'center', marginTop: 2 },
  label: { fontSize: 11, color: MUTED, fontWeight: '600', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 2 },
  value: { fontSize: 14, color: TEXT, lineHeight: 20 },
});

function PillList({ items, color }: { items: string[]; color: string }) {
  if (!items?.length) return null;
  return (
    <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 4 }}>
      {items.map((it, i) => (
        <View key={i} style={[pillStyles.pill, { backgroundColor: `${color}12`, borderColor: `${color}30` }]}>
          <Text style={[pillStyles.text, { color }]}>{it}</Text>
        </View>
      ))}
    </View>
  );
}

const pillStyles = StyleSheet.create({
  pill: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 20, borderWidth: 1 },
  text: { fontSize: 12, fontWeight: '600' },
});

// ── Main screen ───────────────────────────────────────────────────────────────
export default function PlaceScreen() {
  const router = useRouter();
  const { type, id, preloaded } = useLocalSearchParams<{
    type: CatalogItemType;
    id: string;
    preloaded?: string;
  }>();

  const [item, setItem] = useState<CatalogItem | null>(
    preloaded ? (JSON.parse(preloaded) as CatalogItem) : null,
  );
  const [loading, setLoading] = useState(!preloaded);
  const [galleryIdx, setGalleryIdx] = useState(0);

  useEffect(() => {
    if (item || !id || !type) return;
    setLoading(true);
    api.getCatalogPlace(type, id)
      .then(setItem)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [id, type]);

  const color = item ? typeColor(item.type) : '#00A896';
  const images = item?.image_urls?.length
    ? item.image_urls
    : item?.image ? [item.image] : [];

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* ── Drag handle (visual only — OS handles dismissal) ── */}
      <View style={styles.handleRow}>
        <View style={styles.handle} />
      </View>

      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.scroll}
        bounces={Platform.OS === 'ios'}
      >
        {/* ── Gallery ── */}
        {images.length > 0 ? (
          <View style={styles.galleryContainer}>
            <ScrollView
              horizontal pagingEnabled showsHorizontalScrollIndicator={false}
              onScroll={e => setGalleryIdx(Math.round(e.nativeEvent.contentOffset.x / SCREEN_W))}
              scrollEventThrottle={16}
            >
              {images.map((uri, i) => (
                <Image key={i} source={{ uri }} style={styles.galleryImage} contentFit="cover" transition={200} cachePolicy="memory-disk" />
              ))}
            </ScrollView>
            <TouchableOpacity style={styles.closeBtn} onPress={() => router.back()}>
              <Feather name="x" size={18} color="#fff" />
            </TouchableOpacity>
            {images.length > 1 && (
              <View style={styles.dotsRow}>
                {images.map((_, i) => (
                  <View key={i} style={[styles.dot, i === galleryIdx && styles.dotActive]} />
                ))}
              </View>
            )}
            {item && (
              <LinearGradient colors={['transparent', 'rgba(0,0,0,0.5)']} style={styles.imageFade}>
                <View style={[styles.typeBadge, { backgroundColor: color }]}>
                  <Text style={styles.typeBadgeText}>{typeLabel(item.type)}</Text>
                </View>
              </LinearGradient>
            )}
          </View>
        ) : item ? (
          <LinearGradient colors={[`${color}30`, `${color}10`]} style={[styles.galleryContainer, styles.noImg]}>
            <TouchableOpacity style={styles.closeBtn} onPress={() => router.back()}>
              <Feather name="x" size={18} color={color} />
            </TouchableOpacity>
            <MaterialIcons name={item.type === 'hotel' ? 'hotel' : item.type === 'restaurant' ? 'restaurant' : 'place'} size={56} color={color} />
            <View style={[styles.typeBadge, { backgroundColor: color, marginTop: 12 }]}>
              <Text style={styles.typeBadgeText}>{typeLabel(item.type)}</Text>
            </View>
          </LinearGradient>
        ) : null}

        {loading && !item && (
          <View style={{ padding: 40, alignItems: 'center' }}>
            <Text style={{ color: MUTED }}>Loading…</Text>
          </View>
        )}

        {item && (
          <View style={styles.content}>
            {/* Title + rating */}
            <View style={styles.titleRow}>
              <Text style={styles.title} numberOfLines={3}>{item.name}</Text>
              {item.rating != null && (
                <View style={[styles.ratingBadge, { backgroundColor: `${color}15` }]}>
                  <Ionicons name="star" size={14} color="#FFB800" />
                  <Text style={[styles.ratingText, { color }]}>{item.rating.toFixed(1)}</Text>
                </View>
              )}
            </View>

            {item.city ? (
              <View style={styles.cityRow}>
                <Ionicons name="location-outline" size={14} color={MUTED} />
                <Text style={styles.cityText}>{item.city}</Text>
              </View>
            ) : null}

            {item.subtype ? (
              <View style={[styles.subtypePill, { borderColor: `${color}40` }]}>
                <Text style={[styles.subtypeText, { color }]}>{item.subtype}</Text>
              </View>
            ) : null}

            <View style={styles.divider} />

            {item.description ? (
              <>
                <Text style={styles.sectionTitle}>Overview</Text>
                <Text style={styles.description}>{item.description}</Text>
                <View style={styles.divider} />
              </>
            ) : null}

            {/* Domain-specific details */}
            {item.type === 'attraction' && (
              <>
                <Text style={styles.sectionTitle}>Details</Text>
                <InfoRow icon="time-outline" label="Best Hours" value={item.best_hours} color={color} />
                <InfoRow icon="sunny-outline" label="Best Season" value={item.best_season} color={color} />
                <InfoRow icon="ticket-outline" label="Entry Fee" value={item.entry_fee} color={color} />
                <InfoRow icon="car-outline" label="Distance from Cairo" value={item.distance_from_cairo_km != null ? `${item.distance_from_cairo_km} km` : null} color={color} />
              </>
            )}
            {item.type === 'hotel' && (
              <>
                <Text style={styles.sectionTitle}>Details</Text>
                <InfoRow icon="pricetag-outline" label="Price per Night" value={item.price_egp != null ? `${item.price_egp.toLocaleString()} EGP` : null} color={color} />
                {item.amenities?.length > 0 && (
                  <View style={{ marginBottom: 14 }}>
                    <Text style={rowStyles.label}>Amenities</Text>
                    <PillList items={item.amenities} color={color} />
                  </View>
                )}
              </>
            )}
            {item.type === 'restaurant' && (
              <>
                <Text style={styles.sectionTitle}>Details</Text>
                <InfoRow icon="restaurant-outline" label="Cuisine" value={item.cuisine} color={color} />
                <InfoRow icon="pricetag-outline" label="Price Range" value={item.entry_fee} color={color} />
                {item.dishes?.length > 0 && <View style={{ marginBottom: 14 }}><Text style={rowStyles.label}>Signature Dishes</Text><PillList items={item.dishes} color={color} /></View>}
                {item.dietary?.length > 0 && <View style={{ marginBottom: 14 }}><Text style={rowStyles.label}>Dietary Options</Text><PillList items={item.dietary} color={color} /></View>}
                {item.reviews_summary ? <><Text style={styles.sectionTitle}>Reviews</Text><Text style={styles.description}>{item.reviews_summary}</Text></> : null}
              </>
            )}
            {item.type === 'event' && (
              <>
                <Text style={styles.sectionTitle}>Details</Text>
                <InfoRow icon="calendar-outline" label="Date" value={item.event_date} color={color} />
                <InfoRow icon="time-outline" label="Duration" value={item.event_duration} color={color} />
                <InfoRow icon="people-outline" label="Audience" value={item.audience} color={color} />
                <InfoRow icon="ticket-outline" label="Entry Fee" value={item.entry_fee || 'Free'} color={color} />
                <InfoRow icon="business-outline" label="Organizer" value={item.organizer} color={color} />
              </>
            )}
            {item.type === 'transport' && (
              <>
                <Text style={styles.sectionTitle}>Route Details</Text>
                <InfoRow icon="arrow-forward-outline" label="From" value={item.transport_from} color={color} />
                <InfoRow icon="arrow-back-outline" label="To" value={item.transport_to} color={color} />
                <InfoRow icon="car-outline" label="Mode" value={item.transport_mode} color={color} />
                <InfoRow icon="pricetag-outline" label="Avg Price" value={item.price_egp != null ? `${item.price_egp} EGP` : null} color={color} />
                <InfoRow icon="time-outline" label="Duration" value={item.transport_duration_h != null ? `${item.transport_duration_h}h` : null} color={color} />
                <InfoRow icon="refresh-outline" label="Frequency" value={item.transport_frequency} color={color} />
              </>
            )}
            {item.type === 'flight' && (
              <>
                <Text style={styles.sectionTitle}>Flight Details</Text>
                <InfoRow icon="airplane-outline" label="Airline" value={item.airline} color={color} />
                <InfoRow icon="arrow-forward-outline" label="From" value={item.transport_from} color={color} />
                <InfoRow icon="arrow-back-outline" label="To" value={item.transport_to} color={color} />
                <InfoRow icon="pricetag-outline" label="Price" value={item.price_usd != null ? `$${item.price_usd}` : null} color={color} />
                <InfoRow icon="time-outline" label="Duration" value={item.flight_duration_min != null ? `${Math.floor(item.flight_duration_min / 60)}h ${item.flight_duration_min % 60}m` : null} color={color} />
                <InfoRow icon="git-branch-outline" label="Stops" value={item.stops} color={color} />
                <InfoRow icon="calendar-outline" label="Departure" value={item.departure_date} color={color} />
              </>
            )}
            {item.type === 'medical' && (
              <>
                <Text style={styles.sectionTitle}>Facility Details</Text>
                <InfoRow icon="pricetag-outline" label="Price Category" value={item.price_category} color={color} />
                <InfoRow icon="cash-outline" label="Approx. Prices" value={item.entry_fee} color={color} />
                {item.services?.length > 0 && <View style={{ marginBottom: 14 }}><Text style={rowStyles.label}>Services Offered</Text><PillList items={item.services.slice(0, 8)} color={color} /></View>}
              </>
            )}

            {/* Map link */}
            {item.location_url ? (
              <TouchableOpacity style={[styles.mapBtn, { borderColor: `${color}40` }]} onPress={() => Linking.openURL(item.location_url).catch(() => {})}>
                <Ionicons name="map-outline" size={18} color={color} />
                <Text style={[styles.mapBtnText, { color }]}>Open in Maps</Text>
                <Feather name="external-link" size={14} color={color} />
              </TouchableOpacity>
            ) : null}
            {item.type === 'flight' && item.booking_link ? (
              <TouchableOpacity style={[styles.mapBtn, { borderColor: `${color}40`, marginTop: 8 }]} onPress={() => Linking.openURL(item.booking_link).catch(() => {})}>
                <Ionicons name="airplane-outline" size={18} color={color} />
                <Text style={[styles.mapBtnText, { color }]}>View Flight Details</Text>
                <Feather name="external-link" size={14} color={color} />
              </TouchableOpacity>
            ) : null}
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: SURFACE },
  handleRow: { alignItems: 'center', paddingVertical: 10 },
  handle: { width: 36, height: 4, borderRadius: 2, backgroundColor: BORDER_COLOR },
  scroll: { paddingBottom: 60 },

  galleryContainer: { width: '100%', height: 260, backgroundColor: BG },
  galleryImage: { width: SCREEN_W, height: 260 },
  noImg: { alignItems: 'center', justifyContent: 'center' },
  closeBtn: { position: 'absolute', top: 12, right: 16, zIndex: 5, width: 34, height: 34, borderRadius: 17, backgroundColor: 'rgba(0,0,0,0.35)', alignItems: 'center', justifyContent: 'center' },
  dotsRow: { position: 'absolute', bottom: 12, left: 0, right: 0, flexDirection: 'row', justifyContent: 'center', gap: 5 },
  dot: { width: 6, height: 6, borderRadius: 3, backgroundColor: 'rgba(255,255,255,0.5)' },
  dotActive: { backgroundColor: '#fff', width: 16 },
  imageFade: { position: 'absolute', bottom: 0, left: 0, right: 0, height: 80, justifyContent: 'flex-end', paddingBottom: 12, paddingHorizontal: 16 },
  typeBadge: { alignSelf: 'flex-start', paddingHorizontal: 10, paddingVertical: 4, borderRadius: 8 },
  typeBadgeText: { color: '#fff', fontSize: 11, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.5 },

  content: { padding: 20, paddingTop: 16 },
  titleRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 12, marginBottom: 8 },
  title: { flex: 1, fontSize: 22, fontWeight: '800', color: TEXT, letterSpacing: -0.3 },
  ratingBadge: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 8, paddingVertical: 4, borderRadius: 10, marginTop: 4 },
  ratingText: { fontSize: 14, fontWeight: '700' },
  cityRow: { flexDirection: 'row', alignItems: 'center', gap: 4, marginBottom: 8 },
  cityText: { fontSize: 14, color: MUTED },
  subtypePill: { alignSelf: 'flex-start', paddingHorizontal: 10, paddingVertical: 4, borderRadius: 8, borderWidth: 1, marginBottom: 12 },
  subtypeText: { fontSize: 12, fontWeight: '600' },
  divider: { height: 1, backgroundColor: BG, marginVertical: 16 },
  sectionTitle: { fontSize: 16, fontWeight: '700', color: TEXT, marginBottom: 12 },
  description: { fontSize: 14, color: '#3C3C43', lineHeight: 22 },
  mapBtn: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 16, paddingVertical: 12, paddingHorizontal: 16, borderRadius: 12, borderWidth: 1, backgroundColor: BG },
  mapBtnText: { flex: 1, fontSize: 14, fontWeight: '600' },
});
