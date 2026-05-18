/**
 * Search screen — horizontal category tabs + unified debounced search.
 * Hitting /api/catalog/search, shows results as a grid of CatalogCards.
 * Tapping a card opens PlaceSheet.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Dimensions,
  FlatList,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { Image } from 'expo-image';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Feather, Ionicons } from '@expo/vector-icons';
import { useTranslation } from 'react-i18next';

import { useRouter } from 'expo-router';
import { api, type CatalogCard, type CatalogItemType } from '@/services/api';

const { width: SCREEN_W } = Dimensions.get('window');
const CARD_W = (SCREEN_W - 48 - 12) / 2; // 2-col grid with 24px padding + 12px gap

// ── Category tab definitions ──────────────────────────────────────────────────
type CategoryDef = {
  key: string;
  typeFilter: string;
  labelEn: string;
  labelAr: string;
  icon: keyof typeof Ionicons.glyphMap;
  color: string;
};

const CATEGORIES: CategoryDef[] = [
  { key: 'all',        typeFilter: 'all',        labelEn: 'All',        labelAr: 'الكل',        icon: 'apps-outline',        color: '#1C1C1E' },
  { key: 'attraction', typeFilter: 'attraction', labelEn: 'Places',     labelAr: 'أماكن',       icon: 'location-outline',    color: '#00A896' },
  { key: 'hotel',      typeFilter: 'hotel',      labelEn: 'Hotels',     labelAr: 'فنادق',       icon: 'bed-outline',         color: '#7C3AED' },
  { key: 'restaurant', typeFilter: 'restaurant', labelEn: 'Food',       labelAr: 'مطاعم',       icon: 'restaurant-outline',  color: '#EA580C' },
  { key: 'event',      typeFilter: 'event',      labelEn: 'Events',     labelAr: 'فعاليات',     icon: 'calendar-outline',    color: '#DB2777' },
  { key: 'transport',  typeFilter: 'transport',  labelEn: 'Transport',  labelAr: 'مواصلات',     icon: 'car-outline',         color: '#0284C7' },
  { key: 'medical',    typeFilter: 'medical',    labelEn: 'Medical',    labelAr: 'طبي',         icon: 'medkit-outline',      color: '#059669' },
];

const TYPE_COLOR: Record<string, string> = {
  attraction: '#00A896',
  hotel: '#7C3AED',
  restaurant: '#EA580C',
  transport: '#0284C7',
  flight: '#0369A1',
  event: '#DB2777',
  medical: '#059669',
};

// ── Search result card ────────────────────────────────────────────────────────
function ResultCard({ item, onPress }: { item: CatalogCard; onPress: () => void }) {
  const color = TYPE_COLOR[item.type] ?? '#00A896';
  const fallback =
    item.type === 'hotel'
      ? 'https://images.unsplash.com/photo-1542314831-c6a4d14d8373?w=400&auto=format'
      : item.type === 'restaurant'
      ? 'https://images.unsplash.com/photo-1555396273-367ea4eb4db5?w=400&auto=format'
      : item.type === 'event'
      ? 'https://images.unsplash.com/photo-1524368535928-5b5e00ddc76b?w=400&auto=format'
      : 'https://images.unsplash.com/photo-1539650116574-8efeb43e2b50?w=400&auto=format';

  return (
    <TouchableOpacity style={[resultStyles.card, { width: CARD_W }]} onPress={onPress} activeOpacity={0.88}>
      <Image
        source={{ uri: item.image || fallback }}
        style={resultStyles.img}
        contentFit="cover"
        transition={200}
        cachePolicy="memory-disk"
      />
      <View style={[resultStyles.typePill, { backgroundColor: color }]}>
        <Text style={resultStyles.typeTxt}>{item.type.toUpperCase()}</Text>
      </View>
      <View style={resultStyles.body}>
        <Text style={resultStyles.name} numberOfLines={2}>{item.name}</Text>
        {item.city ? (
          <View style={resultStyles.locRow}>
            <Ionicons name="location-outline" size={11} color="#8E8E93" />
            <Text style={resultStyles.locTxt} numberOfLines={1}>{item.city}</Text>
          </View>
        ) : null}
        {item.rating != null && (
          <View style={resultStyles.ratingRow}>
            <Ionicons name="star" size={11} color="#FFB800" />
            <Text style={resultStyles.ratingTxt}>{item.rating.toFixed(1)}</Text>
          </View>
        )}
      </View>
    </TouchableOpacity>
  );
}

const resultStyles = StyleSheet.create({
  card: {
    backgroundColor: '#fff',
    borderRadius: 18,
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: '#E5E5EA',
  },
  img: { width: '100%', height: 130, backgroundColor: '#E8E8ED' },
  typePill: {
    position: 'absolute',
    top: 8, left: 8,
    paddingHorizontal: 7, paddingVertical: 3,
    borderRadius: 6,
  },
  typeTxt: { color: '#fff', fontSize: 8, fontWeight: '800', letterSpacing: 0.5 },
  body: { padding: 10, gap: 4 },
  name: { fontSize: 13, fontWeight: '700', color: '#1C1C1E', lineHeight: 18 },
  locRow: { flexDirection: 'row', alignItems: 'center', gap: 3 },
  locTxt: { fontSize: 11, color: '#8E8E93', flex: 1 },
  ratingRow: { flexDirection: 'row', alignItems: 'center', gap: 3 },
  ratingTxt: { fontSize: 11, fontWeight: '700', color: '#FFB800' },
});

// ── Main screen ───────────────────────────────────────────────────────────────
export default function SearchScreen() {
  const { i18n } = useTranslation();
  const router = useRouter();
  const isAr = i18n.language === 'ar';

  const [query, setQuery] = useState('');
  const [selectedCat, setSelectedCat] = useState<string>('all');
  const [results, setResults] = useState<CatalogCard[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const [total, setTotal] = useState(0);

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const inputRef = useRef<TextInput>(null);

  const doSearch = useCallback(async (q: string, type: string) => {
    setLoading(true);
    try {
      if (q.trim().length > 0) {
        // Real search query — use the search endpoint
        setSearched(true);
        const data = await api.searchCatalog(q.trim(), type, 40);
        setResults(data.results);
        setTotal(data.count);
      } else {
        // No query — browse mode: show catalog items from home feed
        setSearched(false);
        try {
          const home = await api.getCatalogHome({ limit: 20 });
          let browseItems: CatalogCard[] = [];
          if (type === 'all') {
            // Combine all sections for a rich browse experience
            const sections = [
              ...(home.popular || []),
              ...(home.best_now || []),
              ...(home.featured_hotels || []),
              ...(home.local_food || []),
              ...(home.events || []),
              ...(home.offers || []),
            ];
            // Deduplicate by id
            const seen = new Set<string>();
            for (const item of sections) {
              if (!seen.has(item.id)) {
                seen.add(item.id);
                browseItems.push(item);
              }
            }
          } else {
            // Filter home feed by selected category type
            const allSections = [
              ...(home.popular || []),
              ...(home.best_now || []),
              ...(home.featured_hotels || []),
              ...(home.local_food || []),
              ...(home.events || []),
              ...(home.offers || []),
            ];
            const seen = new Set<string>();
            for (const item of allSections) {
              if (item.type === type && !seen.has(item.id)) {
                seen.add(item.id);
                browseItems.push(item);
              }
            }
          }
          setResults(browseItems);
          setTotal(browseItems.length);
        } catch {
          setResults([]);
          setTotal(0);
        }
      }
    } catch {
      setResults([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, []);

  // Debounced search when query or category changes
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      doSearch(query, selectedCat);
    }, 300);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [query, selectedCat, doSearch]);

  const openSheet = (item: CatalogCard) => {
    router.push({ pathname: '/place', params: { type: item.type, id: item.id } } as any);
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* ── Header ── */}
      <View style={styles.header}>
        <Text style={styles.headerTitle}>{isAr ? 'اكتشف مصر' : 'Discover Egypt'}</Text>

        {/* Search bar */}
        <View style={[styles.searchBar, { flexDirection: isAr ? 'row-reverse' : 'row' }]}>
          <Feather name="search" size={18} color="#8E8E93" />
          <TextInput
            ref={inputRef}
            style={[styles.searchInput, { textAlign: isAr ? 'right' : 'left' }]}
            placeholder={isAr ? 'ابحث عن أماكن، فنادق، مطاعم…' : 'Search places, hotels, restaurants…'}
            placeholderTextColor="#C7C7CC"
            value={query}
            onChangeText={setQuery}
            returnKeyType="search"
            clearButtonMode="while-editing"
            autoCorrect={false}
          />
          {query.length > 0 && (
            <TouchableOpacity onPress={() => setQuery('')} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
              <Feather name="x-circle" size={16} color="#C7C7CC" />
            </TouchableOpacity>
          )}
        </View>

        {/* Category tabs */}
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.tabsScroll}
        >
          {CATEGORIES.map((cat) => {
            const active = selectedCat === cat.key;
            return (
              <TouchableOpacity
                key={cat.key}
                style={[styles.tab, active && { backgroundColor: cat.color, borderColor: cat.color }]}
                onPress={() => setSelectedCat(cat.key)}
                activeOpacity={0.8}
              >
                <Ionicons name={cat.icon} size={14} color={active ? '#fff' : '#8E8E93'} />
                <Text style={[styles.tabTxt, active && { color: '#fff', fontWeight: '700' }]}>
                  {isAr ? cat.labelAr : cat.labelEn}
                </Text>
              </TouchableOpacity>
            );
          })}
        </ScrollView>
      </View>

      {/* ── Results ── */}
      {loading ? (
        <View style={styles.loadingWrap}>
          <ActivityIndicator size="large" color="#00A896" />
          <Text style={styles.loadingTxt}>{isAr ? 'جاري البحث…' : 'Searching…'}</Text>
        </View>
      ) : (
        <FlatList
          data={results}
          keyExtractor={(it) => it.id}
          numColumns={2}
          contentContainerStyle={styles.grid}
          columnWrapperStyle={{ gap: 12 }}
          showsVerticalScrollIndicator={false}
          ListHeaderComponent={
            loading ? null : (
              <Text style={styles.resultCount}>
                {searched
                  ? (isAr
                    ? `${total} نتيجة`
                    : `${total} result${total !== 1 ? 's' : ''}`)
                  : (isAr ? `${total} مكان شائع` : `${total} popular place${total !== 1 ? 's' : ''}`)}
              </Text>
            )
          }
          ListEmptyComponent={
            searched ? (
              <View style={styles.emptyWrap}>
                <Feather name="search" size={40} color="#C7C7CC" />
                <Text style={styles.emptyTxt}>
                  {isAr ? 'لا توجد نتائج' : 'No results found'}
                </Text>
                <Text style={styles.emptySubTxt}>
                  {isAr ? 'جرّب كلمات بحث أخرى' : 'Try different keywords'}
                </Text>
              </View>
            ) : null
          }
          renderItem={({ item }) => (
            <ResultCard item={item} onPress={() => openSheet(item)} />
          )}
        />
      )}

    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F2F2F7' },

  header: {
    backgroundColor: '#F2F2F7',
    paddingTop: 8,
    paddingBottom: 12,
    gap: 12,
  },
  headerTitle: {
    fontSize: 28,
    fontWeight: '800',
    color: '#1C1C1E',
    letterSpacing: -0.5,
    paddingHorizontal: 24,
  },

  searchBar: {
    alignItems: 'center',
    backgroundColor: '#fff',
    borderRadius: 16,
    paddingHorizontal: 14,
    paddingVertical: 10,
    marginHorizontal: 20,
    gap: 10,
    borderWidth: 1,
    borderColor: '#E5E5EA',
  },
  searchInput: { flex: 1, fontSize: 15, color: '#1C1C1E' },

  tabsScroll: { paddingHorizontal: 20, gap: 8 },
  tab: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    paddingHorizontal: 12,
    paddingVertical: 7,
    borderRadius: 20,
    backgroundColor: '#fff',
    borderWidth: 1.5,
    borderColor: '#E5E5EA',
  },
  tabTxt: { fontSize: 13, fontWeight: '600', color: '#8E8E93' },

  loadingWrap: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 12 },
  loadingTxt: { color: '#8E8E93', fontSize: 14 },

  grid: { paddingHorizontal: 20, paddingTop: 8, paddingBottom: 120, gap: 12 },
  resultCount: { fontSize: 13, color: '#8E8E93', fontWeight: '600', marginBottom: 8 },

  emptyWrap: { alignItems: 'center', paddingTop: 60, gap: 8 },
  emptyTxt: { fontSize: 17, fontWeight: '700', color: '#8E8E93' },
  emptySubTxt: { fontSize: 14, color: '#C7C7CC' },
});
