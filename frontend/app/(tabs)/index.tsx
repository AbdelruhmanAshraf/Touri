import { useCallback, useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Animated,
  Dimensions,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { Image } from 'expo-image';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Feather, Ionicons, MaterialIcons } from '@expo/vector-icons';
import { useTranslation } from 'react-i18next';
import { useRouter } from 'expo-router';
import { LinearGradient } from 'expo-linear-gradient';

import { useAuth } from '@/hooks/useAuth';
import { api, getOrCreateUserId, type CatalogCard, type CatalogHome, type CatalogItemType, type UserPersona } from '@/services/api';

const { width: SCREEN_W } = Dimensions.get('window');
const CARD_W = SCREEN_W * 0.68;
const CARD_W_SM = SCREEN_W * 0.52;

// ── Type chip colours ─────────────────────────────────────────────────────────
const TYPE_COLOR: Record<CatalogItemType, string> = {
  attraction: '#00A896',
  hotel: '#7C3AED',
  restaurant: '#EA580C',
  transport: '#0284C7',
  flight: '#0369A1',
  event: '#DB2777',
  medical: '#059669',
};

// ── Section config ─────────────────────────────────────────────────────────────
type SectionKey = keyof Pick<CatalogHome, 'events' | 'best_now' | 'offers' | 'popular' | 'featured_hotels' | 'local_food'>;

const SECTIONS: { key: SectionKey; titleEn: string; titleAr: string; icon: keyof typeof Ionicons.glyphMap; small?: boolean }[] = [
  { key: 'events',          titleEn: 'Events & Festivals',     titleAr: 'الفعاليات والمهرجانات', icon: 'calendar-outline',  small: true },
  { key: 'best_now',        titleEn: 'Best to Visit Now',      titleAr: 'الأفضل للزيارة الآن',    icon: 'sunny-outline' },
  { key: 'offers',          titleEn: 'Hot Offers',             titleAr: 'عروض مميزة',             icon: 'pricetag-outline', small: true },
  { key: 'popular',         titleEn: 'Popular Attractions',    titleAr: 'الأماكن الشهيرة',        icon: 'flame-outline' },
  { key: 'featured_hotels', titleEn: 'Top Rated Hotels',       titleAr: 'أفضل الفنادق',           icon: 'bed-outline' },
  { key: 'local_food',      titleEn: 'Local Food & Dining',    titleAr: 'المطاعم والأطعمة',        icon: 'restaurant-outline', small: true },
];

// ── CatalogCard component ──────────────────────────────────────────────────────
function CatalogCardView({
  item,
  small = false,
  onPress,
}: {
  item: CatalogCard;
  small?: boolean;
  onPress: () => void;
}) {
  const color = TYPE_COLOR[item.type] ?? '#00A896';
  const cardWidth = small ? CARD_W_SM : CARD_W;
  const imgHeight = small ? 130 : 170;

  const fallback =
    item.type === 'event'
      ? 'https://images.unsplash.com/photo-1524368535928-5b5e00ddc76b?w=600&auto=format'
      : item.type === 'hotel'
      ? 'https://images.unsplash.com/photo-1542314831-c6a4d14d8373?w=600&auto=format'
      : item.type === 'restaurant'
      ? 'https://images.unsplash.com/photo-1555396273-367ea4eb4db5?w=600&auto=format'
      : 'https://images.unsplash.com/photo-1539650116574-8efeb43e2b50?w=600&auto=format';

  return (
    <TouchableOpacity
      activeOpacity={0.88}
      onPress={onPress}
      style={[cardStyles.card, { width: cardWidth }]}
    >
      <View style={{ overflow: 'hidden', borderRadius: 20 }}>
        <Image
          source={{ uri: item.image || fallback }}
          style={[cardStyles.img, { width: cardWidth, height: imgHeight }]}
          contentFit="cover"
          transition={200}
          cachePolicy="memory-disk"
        />
        <LinearGradient
          colors={['transparent', 'rgba(0,0,0,0.52)']}
          style={cardStyles.imgGrad}
        >
          <View style={[cardStyles.typePill, { backgroundColor: color }]}>
            <Text style={cardStyles.typeText}>{item.type.toUpperCase()}</Text>
          </View>
        </LinearGradient>
      </View>

      <View style={cardStyles.body}>
        <View style={cardStyles.nameRow}>
          <Text style={cardStyles.name} numberOfLines={1}>{item.name}</Text>
          {item.rating != null && (
            <View style={cardStyles.ratingPill}>
              <Ionicons name="star" size={11} color="#FFB800" />
              <Text style={cardStyles.ratingTxt}>{item.rating.toFixed(1)}</Text>
            </View>
          )}
        </View>

        {item.city ? (
          <View style={cardStyles.locRow}>
            <Ionicons name="location-outline" size={12} color="#8E8E93" />
            <Text style={cardStyles.locTxt} numberOfLines={1}>{item.city}</Text>
          </View>
        ) : null}

        {item.type === 'hotel' && item.price_egp != null ? (
          <Text style={[cardStyles.price, { color }]}>
            {item.price_egp.toLocaleString()} <Text style={cardStyles.priceSub}>EGP / night</Text>
          </Text>
        ) : item.entry_fee ? (
          <Text style={[cardStyles.price, { color }]}>{item.entry_fee}</Text>
        ) : null}
      </View>
    </TouchableOpacity>
  );
}

const cardStyles = StyleSheet.create({
  card: {
    backgroundColor: '#fff',
    borderRadius: 20,
    borderWidth: 1,
    borderColor: '#E5E5EA',
    overflow: 'hidden',
  },
  img: { backgroundColor: '#E8E8ED' },
  imgGrad: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    height: 60,
    justifyContent: 'flex-end',
    padding: 10,
  },
  typePill: {
    alignSelf: 'flex-start',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
  },
  typeText: { color: '#fff', fontSize: 9, fontWeight: '800', letterSpacing: 0.6 },
  body: { padding: 12 },
  nameRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 6, marginBottom: 4 },
  name: { flex: 1, fontSize: 14, fontWeight: '700', color: '#1C1C1E' },
  ratingPill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 2,
    backgroundColor: '#FFF9E5',
    paddingHorizontal: 5,
    paddingVertical: 2,
    borderRadius: 5,
    marginTop: 2,
  },
  ratingTxt: { fontSize: 11, fontWeight: '700', color: '#FFB800' },
  locRow: { flexDirection: 'row', alignItems: 'center', gap: 3, marginBottom: 4 },
  locTxt: { fontSize: 12, color: '#8E8E93', flex: 1 },
  price: { fontSize: 14, fontWeight: '800' },
  priceSub: { fontSize: 11, fontWeight: '500', color: '#8E8E93' },
});

// ── Section component ──────────────────────────────────────────────────────────
function CatalogSection({
  title,
  icon,
  items,
  small,
  isAr,
  onCardPress,
  onSeeAll,
}: {
  title: string;
  icon: keyof typeof Ionicons.glyphMap;
  items: CatalogCard[];
  small?: boolean;
  isAr: boolean;
  onCardPress: (item: CatalogCard) => void;
  onSeeAll?: () => void;
}) {
  if (!items?.length) return null;
  return (
    <View style={sectionStyles.section}>
      <View style={[sectionStyles.header, { flexDirection: isAr ? 'row-reverse' : 'row' }]}>
        <View style={[sectionStyles.titleGroup, { flexDirection: isAr ? 'row-reverse' : 'row' }]}>
          <Ionicons name={icon} size={18} color="#00A896" />
          <Text style={sectionStyles.title}>{title}</Text>
        </View>
        {onSeeAll && (
          <TouchableOpacity onPress={onSeeAll}>
            <Text style={sectionStyles.seeAll}>{isAr ? 'عرض الكل' : 'See All'}</Text>
          </TouchableOpacity>
        )}
      </View>
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={sectionStyles.scroll}
      >
        {items.map((it) => (
          <CatalogCardView
            key={it.id}
            item={it}
            small={small}
            onPress={() => onCardPress(it)}
          />
        ))}
      </ScrollView>
    </View>
  );
}

const sectionStyles = StyleSheet.create({
  section: { marginBottom: 32 },
  header: {
    paddingHorizontal: 24,
    marginBottom: 14,
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  titleGroup: { alignItems: 'center', gap: 8 },
  title: { fontSize: 18, fontWeight: '700', color: '#1C1C1E', letterSpacing: -0.2 },
  seeAll: { fontSize: 13, fontWeight: '600', color: '#00A896' },
  scroll: { paddingHorizontal: 24, gap: 14 },
});

// ── Main screen ────────────────────────────────────────────────────────────────
export default function ExploreScreen() {
  const { t, i18n } = useTranslation();
  const { user, isGuest } = useAuth();
  const router = useRouter();
  const isAr = i18n.language === 'ar';

  const [persona, setPersona] = useState<UserPersona | null>(null);
  const [catalog, setCatalog] = useState<CatalogHome | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  // No local sheet state — navigation to /place modal instead

  // Pulsing skeleton animation
  const pulseAnim = useRef(new Animated.Value(0.4)).current;
  useEffect(() => {
    if (!loading) return;
    Animated.loop(
      Animated.sequence([
        Animated.timing(pulseAnim, { toValue: 1, duration: 700, useNativeDriver: true }),
        Animated.timing(pulseAnim, { toValue: 0.4, duration: 700, useNativeDriver: true }),
      ]),
    ).start();
    return () => pulseAnim.stopAnimation();
  }, [loading]);

  const loadData = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const [cat, p] = await Promise.allSettled([
        api.getCatalogHome({ limit: 10 }),
        !isGuest
          ? api.getPersona(user?.uid ?? (await getOrCreateUserId()))
          : Promise.reject(new Error('guest')),
      ]);
      if (cat.status === 'fulfilled') setCatalog(cat.value);
      if (p.status === 'fulfilled') setPersona(p.value as UserPersona);
    } catch {
      /* silently handled via allSettled */
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [user?.uid, isGuest]);

  useEffect(() => { loadData(); }, [loadData]);

  const onRefresh = useCallback(() => {
    setRefreshing(true);
    loadData(true);
  }, [loadData]);

  const openSheet = (item: CatalogCard) => {
    router.push({ pathname: '/place', params: { type: item.type, id: item.id } } as any);
  };

  const destination =
    (persona?.preferred_destination &&
      persona.preferred_destination
        .replace(/_/g, ' ')
        .replace(/\b\w/g, (c) => c.toUpperCase())) ||
    t('explore.destinationFallback');

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={onRefresh}
            tintColor="#00A896"
            colors={['#00A896']}
          />
        }
      >
        {/* ── Header ── */}
        <View style={[styles.header, { flexDirection: isAr ? 'row-reverse' : 'row' }]}>
          <View style={[styles.logoRow, { flexDirection: isAr ? 'row-reverse' : 'row' }]}>
            <Image
              source={{ uri: 'https://lh3.googleusercontent.com/aida-public/AB6AXuCpO7gZzXXTZDL5yRCrLEHL_isGfSt1h4-PzCHdvKFBUtAWj5Q-xFURHfyGE2PilbyHE4WsoE0dJp0sVSim98DBd-a0F-7V7VxG8h2dDd3zmzOBDQaZJFhPS8eBv56aze9cEmNoov3ZlTuVCDSQkIVHpVEhjbGWe_nXw_YCGnQlcyD0tg4_yQZj8fsm6I6oWGhjSxOGwA--xAvXevncLwGIjbTvq2-rSgzmqhp1ddWi1tgUM2knzKpQxWCrsX1lWDYckr3gcSkIiAM' }}
              style={styles.logo}
              contentFit="cover"
              transition={200}
              cachePolicy="memory-disk"
            />
            <Text style={styles.logoText}>Tripmind</Text>
          </View>
          <TouchableOpacity style={styles.bellBtn} onPress={() => router.push('/(tabs)/search' as any)}>
            <Feather name="search" size={20} color="#1C1C1E" />
          </TouchableOpacity>
        </View>

        {/* ── Hero ── */}
        <View style={styles.hero}>
          <Text style={[styles.greeting, { textAlign: isAr ? 'right' : 'left' }]}>
            {t('explore.greeting')}
          </Text>
          <Text style={[styles.destination, { textAlign: isAr ? 'right' : 'left' }]}>
            {destination}
          </Text>
          {catalog?.meta && (
            <View style={[styles.metaRow, { flexDirection: isAr ? 'row-reverse' : 'row' }]}>
              <MetaChip icon="location-outline" value={`${catalog.meta.total_attractions} places`} />
              <MetaChip icon="bed-outline" value={`${catalog.meta.total_hotels} hotels`} />
              <MetaChip icon="restaurant-outline" value={`${catalog.meta.total_restaurants} restaurants`} />
            </View>
          )}
        </View>

        {/* ── AI CTA ── */}
        <TouchableOpacity
          style={styles.cta}
          activeOpacity={0.88}
          onPress={() => router.push('/(tabs)/chat' as any)}
        >
          <LinearGradient
            colors={['#00A896', '#028090']}
            start={{ x: 0, y: 0 }}
            end={{ x: 1, y: 0 }}
            style={[styles.ctaInner, { flexDirection: isAr ? 'row-reverse' : 'row' }]}
          >
            <View style={styles.ctaIcon}>
              <MaterialIcons name="auto-awesome" size={20} color="#00A896" />
            </View>
            <View style={{ flex: 1, paddingHorizontal: 12 }}>
              <Text style={[styles.ctaText, { textAlign: isAr ? 'right' : 'left' }]}>
                {t('explore.askChat')}
              </Text>
              <Text style={[styles.ctaSub, { textAlign: isAr ? 'right' : 'left' }]}>
                {isAr ? 'مساعدك الذكي للسفر في مصر' : 'Your AI travel concierge for Egypt'}
              </Text>
            </View>
            <Feather name={isAr ? 'chevron-left' : 'chevron-right'} size={22} color="#fff" />
          </LinearGradient>
        </TouchableOpacity>

        {/* ── Loading skeleton ── */}
        {loading && (
          <View style={{ paddingHorizontal: 24, gap: 20 }}>
            {[1, 2, 3].map((i) => (
              <View key={i}>
                <Animated.View style={[skeletonStyles.titleBar, { opacity: pulseAnim }]} />
                <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 14, paddingRight: 24 }}>
                  {[1, 2, 3].map((j) => (
                    <Animated.View key={j} style={[skeletonStyles.card, { opacity: pulseAnim }]} />
                  ))}
                </ScrollView>
              </View>
            ))}
          </View>
        )}

        {/* ── Data sections ── */}
        {!loading && catalog && SECTIONS.map((sec) => {
          const items: CatalogCard[] = (catalog[sec.key] as CatalogCard[]) ?? [];
          const title = isAr ? sec.titleAr : sec.titleEn;
          return (
            <CatalogSection
              key={sec.key}
              title={title}
              icon={sec.icon}
              items={items}
              small={sec.small}
              isAr={isAr}
              onCardPress={openSheet}
              onSeeAll={() => router.push('/(tabs)/search' as any)}
            />
          );
        })}

        {/* ── Empty state ── */}
        {!loading && !catalog && (
          <View style={styles.emptyState}>
            <MaterialIcons name="cloud-off" size={48} color="#C7C7CC" />
            <Text style={styles.emptyTitle}>
              {isAr ? 'تعذّر تحميل البيانات' : 'Couldn\'t load data'}
            </Text>
            <TouchableOpacity style={styles.retryBtn} onPress={() => loadData()}>
              <Text style={styles.retryTxt}>{isAr ? 'إعادة المحاولة' : 'Retry'}</Text>
            </TouchableOpacity>
          </View>
        )}
      </ScrollView>

    </SafeAreaView>
  );
}

// ── Meta chip ─────────────────────────────────────────────────────────────────
function MetaChip({ icon, value }: { icon: keyof typeof Ionicons.glyphMap; value: string }) {
  return (
    <View style={metaStyles.chip}>
      <Ionicons name={icon} size={12} color="#8E8E93" />
      <Text style={metaStyles.txt}>{value}</Text>
    </View>
  );
}
const metaStyles = StyleSheet.create({
  chip: { flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: '#F2F2F7', paddingHorizontal: 8, paddingVertical: 4, borderRadius: 8 },
  txt: { fontSize: 11, color: '#8E8E93', fontWeight: '600' },
});

// ── Skeleton styles ───────────────────────────────────────────────────────────
const skeletonStyles = StyleSheet.create({
  titleBar: { width: 160, height: 18, borderRadius: 9, backgroundColor: '#E5E5EA', marginBottom: 12 },
  card: { width: CARD_W, height: 220, borderRadius: 20, backgroundColor: '#E5E5EA' },
});

// ── Screen styles ─────────────────────────────────────────────────────────────
const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F2F2F7' },
  scrollContent: { paddingBottom: 20 },

  header: {
    paddingHorizontal: 24,
    paddingTop: 16,
    paddingBottom: 8,
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  logoRow: { alignItems: 'center', gap: 8 },
  logo: { width: 34, height: 34, borderRadius: 8 },
  logoText: { fontSize: 20, fontWeight: '800', color: '#1C1C1E', letterSpacing: -0.5 },
  bellBtn: {
    width: 42, height: 42, borderRadius: 21,
    backgroundColor: '#fff', alignItems: 'center', justifyContent: 'center',
    borderWidth: 1, borderColor: '#E5E5EA',
  },

  hero: { paddingHorizontal: 24, marginBottom: 24, marginTop: 16 },
  greeting: { fontSize: 15, color: '#8E8E93', marginBottom: 4 },
  destination: { fontSize: 32, fontWeight: '800', color: '#1C1C1E', letterSpacing: -0.5, marginBottom: 12 },
  metaRow: { flexDirection: 'row', gap: 8, flexWrap: 'wrap' },

  cta: {
    marginHorizontal: 24,
    marginBottom: 36,
    borderRadius: 20,
    overflow: 'hidden',
  },
  ctaInner: { alignItems: 'center', padding: 16, borderRadius: 20 },
  ctaIcon: { width: 40, height: 40, borderRadius: 12, backgroundColor: '#fff', alignItems: 'center', justifyContent: 'center' },
  ctaText: { color: '#fff', fontSize: 15, fontWeight: '700', marginBottom: 2 },
  ctaSub: { color: 'rgba(255,255,255,0.82)', fontSize: 12 },

  emptyState: { alignItems: 'center', paddingTop: 60, gap: 12 },
  emptyTitle: { fontSize: 16, color: '#8E8E93', fontWeight: '600' },
  retryBtn: { marginTop: 4, paddingHorizontal: 20, paddingVertical: 10, backgroundColor: '#00A896', borderRadius: 12 },
  retryTxt: { color: '#fff', fontWeight: '700', fontSize: 14 },
});
