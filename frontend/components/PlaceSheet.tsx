/**
 * PlaceSheet — bottom-sheet detail panel for any CatalogItem.
 *
 * Slides up from the bottom (iOS-style). Swipe down or tap the backdrop
 * to dismiss. Shows: image gallery, title, rating, location, overview,
 * best hours & season, price, and domain-specific extras.
 *
 * NO booking button — this is a discovery-only sheet.
 */

import React, { useEffect, useRef, useState } from 'react';
import {
  Animated,
  Dimensions,
  Image,
  Linking,
  PanResponder,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { Feather, Ionicons, MaterialIcons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';

import { api, type CatalogItem, type CatalogItemType } from '@/services/api';

const { height: SCREEN_H, width: SCREEN_W } = Dimensions.get('window');
const SHEET_HEIGHT = SCREEN_H * 0.88;
const SNAP_CLOSE_THRESHOLD = SHEET_HEIGHT * 0.25;

// ── Type helpers ──────────────────────────────────────────────────────────────
function typeLabel(t: CatalogItemType): string {
  const map: Record<CatalogItemType, string> = {
    attraction: 'Attraction',
    hotel: 'Hotel',
    restaurant: 'Restaurant',
    transport: 'Transport',
    flight: 'Flight',
    event: 'Event',
    medical: 'Medical',
  };
  return map[t] ?? t;
}

function typeColor(t: CatalogItemType): string {
  const map: Record<CatalogItemType, string> = {
    attraction: '#00A896',
    hotel: '#7C3AED',
    restaurant: '#EA580C',
    transport: '#0284C7',
    flight: '#0369A1',
    event: '#DB2777',
    medical: '#059669',
  };
  return map[t] ?? '#00A896';
}

// ── Info row helper ───────────────────────────────────────────────────────────
function InfoRow({
  icon,
  label,
  value,
  color = '#8E8E93',
}: {
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
  container: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 12,
    marginBottom: 14,
  },
  iconWrap: {
    width: 32,
    height: 32,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 2,
  },
  label: { fontSize: 11, color: '#8E8E93', fontWeight: '600', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 2 },
  value: { fontSize: 14, color: '#1C1C1E', lineHeight: 20 },
});

// ── Pill list ─────────────────────────────────────────────────────────────────
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

// ── Main component ─────────────────────────────────────────────────────────────
export type PlaceSheetProps = {
  /** Pass the card's (type, id) to load full detail, or pass pre-loaded item */
  itemId?: string;
  itemType?: CatalogItemType;
  preloaded?: CatalogItem;
  isVisible: boolean;
  onClose: () => void;
};

export default function PlaceSheet({ itemId, itemType, preloaded, isVisible, onClose }: PlaceSheetProps) {
  const translateY = useRef(new Animated.Value(SHEET_HEIGHT)).current;
  const backdropOpacity = useRef(new Animated.Value(0)).current;
  const [rendered, setRendered] = useState(false);

  const [item, setItem] = useState<CatalogItem | null>(preloaded ?? null);
  const [loading, setLoading] = useState(false);
  const [galleryIdx, setGalleryIdx] = useState(0);

  // ── Slide in / out ──────────────────────────────────────────────────────
  useEffect(() => {
    if (isVisible) {
      setRendered(true);
      setGalleryIdx(0);
      Animated.parallel([
        Animated.spring(translateY, {
          toValue: 0,
          useNativeDriver: true,
          tension: 65,
          friction: 11,
        }),
        Animated.timing(backdropOpacity, {
          toValue: 1,
          duration: 250,
          useNativeDriver: true,
        }),
      ]).start();
    } else {
      Animated.parallel([
        Animated.timing(translateY, {
          toValue: SHEET_HEIGHT,
          duration: 300,
          useNativeDriver: true,
        }),
        Animated.timing(backdropOpacity, {
          toValue: 0,
          duration: 250,
          useNativeDriver: true,
        }),
      ]).start(() => setRendered(false));
    }
  }, [isVisible]);

  // ── Fetch full detail when sheet opens ──────────────────────────────────
  useEffect(() => {
    if (!isVisible) return;
    if (preloaded) { setItem(preloaded); return; }
    if (!itemId || !itemType) return;
    setLoading(true);
    api.getCatalogPlace(itemType, itemId)
      .then(setItem)
      .catch(() => {/* show card with minimal data */})
      .finally(() => setLoading(false));
  }, [isVisible, itemId, itemType, preloaded]);

  // ── Swipe-down gesture ──────────────────────────────────────────────────
  const panRef = useRef(new Animated.Value(0)).current;
  const panResponder = useRef(
    PanResponder.create({
      onMoveShouldSetPanResponder: (_, g) => g.dy > 10 && Math.abs(g.dy) > Math.abs(g.dx),
      onPanResponderMove: (_, g) => {
        if (g.dy > 0) panRef.setValue(g.dy);
      },
      onPanResponderRelease: (_, g) => {
        if (g.dy > SNAP_CLOSE_THRESHOLD || g.vy > 0.5) {
          onClose();
        } else {
          Animated.spring(panRef, { toValue: 0, useNativeDriver: true }).start();
        }
        panRef.setValue(0);
      },
    }),
  ).current;

  if (!rendered) return null;

  const color = item ? typeColor(item.type) : '#00A896';
  const images = item?.image_urls?.length ? item.image_urls : (item?.image ? [item.image] : []);

  return (
    <View style={styles.overlay} pointerEvents="box-none">
      {/* Backdrop */}
      <Animated.View
        style={[styles.backdrop, { opacity: backdropOpacity }]}
        pointerEvents={isVisible ? 'auto' : 'none'}
      >
        <TouchableOpacity style={StyleSheet.absoluteFill} onPress={onClose} />
      </Animated.View>

      {/* Sheet */}
      <Animated.View
        style={[
          styles.sheet,
          { transform: [{ translateY: Animated.add(translateY, panRef) }] },
        ]}
      >
        {/* Drag handle */}
        <View {...panResponder.panHandlers} style={styles.handleArea}>
          <View style={styles.handle} />
        </View>

        <ScrollView
          style={{ flex: 1 }}
          showsVerticalScrollIndicator={false}
          contentContainerStyle={{ paddingBottom: 60 }}
          bounces={Platform.OS === 'ios'}
        >
          {/* ── Image Gallery ── */}
          {images.length > 0 && (
            <View style={styles.galleryContainer}>
              <ScrollView
                horizontal
                pagingEnabled
                showsHorizontalScrollIndicator={false}
                onScroll={(e) => {
                  const idx = Math.round(e.nativeEvent.contentOffset.x / SCREEN_W);
                  setGalleryIdx(idx);
                }}
                scrollEventThrottle={16}
              >
                {images.map((uri, i) => (
                  <Image key={i} source={{ uri }} style={styles.galleryImage} />
                ))}
              </ScrollView>
              {/* Close button */}
              <TouchableOpacity style={styles.closeBtn} onPress={onClose}>
                <Feather name="x" size={18} color="#fff" />
              </TouchableOpacity>
              {/* Dots */}
              {images.length > 1 && (
                <View style={styles.dotsRow}>
                  {images.map((_, i) => (
                    <View
                      key={i}
                      style={[styles.dot, i === galleryIdx && { backgroundColor: '#fff', width: 16 }]}
                    />
                  ))}
                </View>
              )}
              {/* Type badge over image */}
              {item && (
                <LinearGradient
                  colors={['transparent', 'rgba(0,0,0,0.55)']}
                  style={styles.imageFade}
                >
                  <View style={[styles.typeBadge, { backgroundColor: color }]}>
                    <Text style={styles.typeBadgeText}>{typeLabel(item.type)}</Text>
                  </View>
                </LinearGradient>
              )}
            </View>
          )}

          {/* ── No image placeholder ── */}
          {images.length === 0 && item && (
            <LinearGradient
              colors={[`${color}30`, `${color}10`]}
              style={[styles.galleryContainer, styles.noImagePlaceholder]}
            >
              <TouchableOpacity style={styles.closeBtn} onPress={onClose}>
                <Feather name="x" size={18} color={color} />
              </TouchableOpacity>
              <MaterialIcons
                name={item.type === 'hotel' ? 'hotel' : item.type === 'restaurant' ? 'restaurant' : item.type === 'event' ? 'event' : 'place'}
                size={56}
                color={color}
              />
              <View style={[styles.typeBadge, { backgroundColor: color, marginTop: 12 }]}>
                <Text style={styles.typeBadgeText}>{typeLabel(item.type)}</Text>
              </View>
            </LinearGradient>
          )}

          {loading && (
            <View style={{ padding: 24, alignItems: 'center' }}>
              <Text style={{ color: '#8E8E93' }}>Loading details…</Text>
            </View>
          )}

          {item && (
            <View style={styles.content}>
              {/* Title + Rating */}
              <View style={styles.titleRow}>
                <Text style={styles.title} numberOfLines={3}>{item.name}</Text>
                {item.rating != null && (
                  <View style={[styles.ratingBadge, { backgroundColor: `${color}15` }]}>
                    <Ionicons name="star" size={14} color="#FFB800" />
                    <Text style={[styles.ratingText, { color }]}>{item.rating.toFixed(1)}</Text>
                  </View>
                )}
              </View>

              {/* City */}
              {item.city ? (
                <View style={styles.cityRow}>
                  <Ionicons name="location-outline" size={14} color="#8E8E93" />
                  <Text style={styles.cityText}>{item.city}</Text>
                </View>
              ) : null}

              {/* Subtype pill */}
              {item.subtype ? (
                <View style={[styles.subtypePill, { borderColor: `${color}40` }]}>
                  <Text style={[styles.subtypeText, { color }]}>{item.subtype}</Text>
                </View>
              ) : null}

              <View style={styles.divider} />

              {/* ── Overview ── */}
              {item.description ? (
                <>
                  <Text style={styles.sectionTitle}>Overview</Text>
                  <Text style={styles.description}>{item.description}</Text>
                  <View style={styles.divider} />
                </>
              ) : null}

              {/* ── Domain-specific info ── */}
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
                  {item.dishes?.length > 0 && (
                    <View style={{ marginBottom: 14 }}>
                      <Text style={rowStyles.label}>Signature Dishes</Text>
                      <PillList items={item.dishes} color={color} />
                    </View>
                  )}
                  {item.dietary?.length > 0 && (
                    <View style={{ marginBottom: 14 }}>
                      <Text style={rowStyles.label}>Dietary Options</Text>
                      <PillList items={item.dietary} color={color} />
                    </View>
                  )}
                  {item.reviews_summary ? (
                    <>
                      <Text style={styles.sectionTitle}>Reviews</Text>
                      <Text style={styles.description}>{item.reviews_summary}</Text>
                    </>
                  ) : null}
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
                  <InfoRow icon="business-outline" label="Operator" value={item.organizer} color={color} />
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
                  {item.services?.length > 0 && (
                    <View style={{ marginBottom: 14 }}>
                      <Text style={rowStyles.label}>Services Offered</Text>
                      <PillList items={item.services.slice(0, 8)} color={color} />
                    </View>
                  )}
                </>
              )}

              {/* ── Map link ── */}
              {item.location_url ? (
                <TouchableOpacity
                  style={[styles.mapBtn, { borderColor: `${color}40` }]}
                  onPress={() => Linking.openURL(item.location_url).catch(() => {})}
                >
                  <Ionicons name="map-outline" size={18} color={color} />
                  <Text style={[styles.mapBtnText, { color }]}>Open in Maps</Text>
                  <Feather name="external-link" size={14} color={color} />
                </TouchableOpacity>
              ) : null}

              {/* ── Booking link (flights only) ── */}
              {item.type === 'flight' && item.booking_link ? (
                <TouchableOpacity
                  style={[styles.mapBtn, { borderColor: `${color}40`, marginTop: 8 }]}
                  onPress={() => Linking.openURL(item.booking_link).catch(() => {})}
                >
                  <Ionicons name="airplane-outline" size={18} color={color} />
                  <Text style={[styles.mapBtnText, { color }]}>View Flight Details</Text>
                  <Feather name="external-link" size={14} color={color} />
                </TouchableOpacity>
              ) : null}
            </View>
          )}
        </ScrollView>
      </Animated.View>
    </View>
  );
}

const styles = StyleSheet.create({
  overlay: {
    ...StyleSheet.absoluteFillObject,
    zIndex: 999,
    justifyContent: 'flex-end',
  },
  backdrop: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: 'rgba(0,0,0,0.5)',
  },
  sheet: {
    height: SHEET_HEIGHT,
    backgroundColor: '#fff',
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    overflow: 'hidden',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: -4 },
    shadowOpacity: 0.12,
    shadowRadius: 20,
    elevation: 20,
  },
  handleArea: {
    alignItems: 'center',
    paddingVertical: 12,
    backgroundColor: '#fff',
    zIndex: 10,
  },
  handle: {
    width: 36,
    height: 4,
    backgroundColor: '#E5E5EA',
    borderRadius: 2,
  },
  galleryContainer: {
    width: '100%',
    height: 260,
    backgroundColor: '#F2F2F7',
  },
  galleryImage: {
    width: SCREEN_W,
    height: 260,
    resizeMode: 'cover',
  },
  noImagePlaceholder: {
    alignItems: 'center',
    justifyContent: 'center',
  },
  closeBtn: {
    position: 'absolute',
    top: 12,
    right: 16,
    zIndex: 5,
    width: 34,
    height: 34,
    borderRadius: 17,
    backgroundColor: 'rgba(0,0,0,0.35)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  dotsRow: {
    position: 'absolute',
    bottom: 12,
    left: 0,
    right: 0,
    flexDirection: 'row',
    justifyContent: 'center',
    gap: 5,
  },
  dot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: 'rgba(255,255,255,0.5)',
  },
  imageFade: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    height: 80,
    justifyContent: 'flex-end',
    paddingBottom: 12,
    paddingHorizontal: 16,
  },
  typeBadge: {
    alignSelf: 'flex-start',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 8,
  },
  typeBadgeText: { color: '#fff', fontSize: 11, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.5 },

  content: { padding: 20, paddingTop: 16 },
  titleRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 12,
    marginBottom: 8,
  },
  title: { flex: 1, fontSize: 22, fontWeight: '800', color: '#1C1C1E', letterSpacing: -0.3 },
  ratingBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 10,
    marginTop: 4,
  },
  ratingText: { fontSize: 14, fontWeight: '700' },
  cityRow: { flexDirection: 'row', alignItems: 'center', gap: 4, marginBottom: 8 },
  cityText: { fontSize: 14, color: '#8E8E93' },
  subtypePill: {
    alignSelf: 'flex-start',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 8,
    borderWidth: 1,
    marginBottom: 12,
  },
  subtypeText: { fontSize: 12, fontWeight: '600' },
  divider: { height: 1, backgroundColor: '#F2F2F7', marginVertical: 16 },
  sectionTitle: { fontSize: 16, fontWeight: '700', color: '#1C1C1E', marginBottom: 12 },
  description: { fontSize: 14, color: '#3C3C43', lineHeight: 22 },
  mapBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginTop: 16,
    paddingVertical: 12,
    paddingHorizontal: 16,
    borderRadius: 12,
    borderWidth: 1,
    backgroundColor: '#F9FAFB',
  },
  mapBtnText: { flex: 1, fontSize: 14, fontWeight: '600' },
});
