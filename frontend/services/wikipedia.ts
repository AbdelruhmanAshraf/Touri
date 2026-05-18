/**
 * Wikipedia Image Service
 *
 * Fetches high-quality images from Wikipedia for destinations used
 * in the Tripmind onboarding flow and throughout the app.
 *
 * Uses the MediaWiki API (pageimages + imageinfo) to retrieve
 * the primary thumbnail / original image for any article title.
 */

const WIKI_API = 'https://en.wikipedia.org/w/api.php';

/** In-memory cache to avoid redundant network requests. */
const imageCache = new Map<string, string>();

/**
 * Maps user-facing destination labels to their Wikipedia article titles.
 * This ensures we always hit the correct article regardless of UI text.
 */
export const DESTINATION_WIKI_TITLES: Record<string, string> = {
  // Original destinations
  'Cairo (القاهرة)': 'Cairo',
  'Alexandria (الإسكندرية)': 'Alexandria',
  'Luxor (الأقصر)': 'Luxor',
  'Aswan (أسوان)': 'Aswan',
  'Sharm El-Sheikh (شرم الشيخ)': 'Sharm El Sheikh',
  'Hurghada (الغردقة)': 'Hurghada',
  // All 27 Egyptian governorates
  'Giza (الجيزة)': 'Giza',
  'Qalyubia (القليوبية)': 'Qalyubia Governorate',
  'Gharbia (الغربية)': 'Gharbia Governorate',
  'Dakahlia (الدقهلية)': 'Dakahlia Governorate',
  'Sharqia (الشرقية)': 'Sharqia Governorate',
  'Kafr El-Sheikh (كفر الشيخ)': 'Kafr El Sheikh Governorate',
  'Monufia (المنوفية)': 'Monufia Governorate',
  'Beheira (البحيرة)': 'Beheira Governorate',
  'Ismailia (الإسماعيلية)': 'Ismailia',
  'Suez (السويس)': 'Suez',
  'Port Said (بورسعيد)': 'Port Said',
  'North Sinai (شمال سيناء)': 'North Sinai Governorate',
  'South Sinai (جنوب سيناء)': 'South Sinai Governorate',
  'Fayyum (الفيوم)': 'Faiyum',
  'Beni Suef (بني سويف)': 'Beni Suef Governorate',
  'Al-Minya (المنيا)': 'Minya, Egypt',
  'Asyut (أسيوط)': 'Asyut',
  'Sohag (سوهاج)': 'Sohag Governorate',
  'Qena (قنا)': 'Qena Governorate',
  'Red Sea / Hurghada (البحر الأحمر)': 'Red Sea Governorate',
  'Matrouh (مطروح)': 'Matrouh Governorate',
  'New Valley (الوادي الجديد)': 'New Valley Governorate',
  'Damietta (دمياط)': 'Damietta Governorate',
};

/**
 * Fetch the primary Wikipedia image URL for a given article title.
 *
 * Strategy:
 *   1. Try `pageimages` prop for a 800px thumbnail (fast, reliable).
 *   2. Fall back to `images` + `imageinfo` for the first usable image.
 *   3. Return a curated Unsplash fallback if everything fails.
 */
export async function getWikipediaImage(
  articleTitle: string,
  width = 800,
): Promise<string> {
  // Check cache first
  const cacheKey = `${articleTitle}_${width}`;
  if (imageCache.has(cacheKey)) {
    return imageCache.get(cacheKey)!;
  }

  try {
    // ── Approach 1: pageimages (thumbnail) ──────────────────────────────
    const thumbUrl = new URL(WIKI_API);
    thumbUrl.searchParams.set('action', 'query');
    thumbUrl.searchParams.set('titles', articleTitle);
    thumbUrl.searchParams.set('prop', 'pageimages');
    thumbUrl.searchParams.set('format', 'json');
    thumbUrl.searchParams.set('origin', '*');
    thumbUrl.searchParams.set('pithumbsize', String(width));

    const thumbRes = await fetch(thumbUrl.toString());
    const thumbData = await thumbRes.json();
    const pages = thumbData?.query?.pages;

    if (pages) {
      const page = Object.values(pages)[0] as any;
      if (page?.thumbnail?.source) {
        const imgUrl = page.thumbnail.source;
        imageCache.set(cacheKey, imgUrl);
        return imgUrl;
      }
    }

    // ── Approach 2: images list → imageinfo ─────────────────────────────
    const imagesUrl = new URL(WIKI_API);
    imagesUrl.searchParams.set('action', 'query');
    imagesUrl.searchParams.set('titles', articleTitle);
    imagesUrl.searchParams.set('prop', 'images');
    imagesUrl.searchParams.set('format', 'json');
    imagesUrl.searchParams.set('origin', '*');
    imagesUrl.searchParams.set('imlimit', '5');

    const imagesRes = await fetch(imagesUrl.toString());
    const imagesData = await imagesRes.json();
    const imgPages = imagesData?.query?.pages;

    if (imgPages) {
      const imgPage = Object.values(imgPages)[0] as any;
      const images: Array<{ title: string }> = imgPage?.images ?? [];

      // Pick the first .jpg / .jpeg / .png image (skip .svg / icons)
      const usableImage = images.find((img) =>
        /\.(jpe?g|png)$/i.test(img.title),
      );

      if (usableImage) {
        const infoUrl = new URL(WIKI_API);
        infoUrl.searchParams.set('action', 'query');
        infoUrl.searchParams.set('titles', usableImage.title);
        infoUrl.searchParams.set('prop', 'imageinfo');
        infoUrl.searchParams.set('iiprop', 'url');
        infoUrl.searchParams.set('iiurlwidth', String(width));
        infoUrl.searchParams.set('format', 'json');
        infoUrl.searchParams.set('origin', '*');

        const infoRes = await fetch(infoUrl.toString());
        const infoData = await infoRes.json();
        const infoPages = infoData?.query?.pages;

        if (infoPages) {
          const infoPage = Object.values(infoPages)[0] as any;
          const thumbUrl2 =
            infoPage?.imageinfo?.[0]?.thumburl ??
            infoPage?.imageinfo?.[0]?.url;
          if (thumbUrl2) {
            imageCache.set(cacheKey, thumbUrl2);
            return thumbUrl2;
          }
        }
      }
    }
  } catch (err) {
    // eslint-disable-next-line no-console
    console.warn(`[wikipedia] Failed to fetch image for "${articleTitle}":`, err);
  }

  // ── Fallback: curated Unsplash images ────────────────────────────────
  const fallback = FALLBACK_IMAGES[articleTitle] ?? FALLBACK_IMAGES._default;
  imageCache.set(cacheKey, fallback);
  return fallback;
}

/** Curated Unsplash fallbacks keyed by Wikipedia article title. */
const FALLBACK_IMAGES: Record<string, string> = {
  Cairo:
    'https://images.unsplash.com/photo-1572252009286-268acec5ca0a?w=800&auto=format',
  Alexandria:
    'https://images.unsplash.com/photo-1570107945034-28e7e3f1b2c0?w=800&auto=format',
  Luxor:
    'https://images.unsplash.com/photo-1539650116574-8efeb43e2b50?w=800&auto=format',
  Aswan:
    'https://images.unsplash.com/photo-1590059390258-ba2e75401788?w=800&auto=format',
  'Sharm El Sheikh':
    'https://images.unsplash.com/photo-1544551763-46a013bb70d5?w=800&auto=format',
  Hurghada:
    'https://images.unsplash.com/photo-1544551763-46a013bb70d5?w=800&auto=format',
  _default:
    'https://images.unsplash.com/photo-1539650116574-8efeb43e2b50?w=800&auto=format',
};

/**
 * Prefetch all destination images in parallel so they're cached
 * by the time the user reaches the destination step.
 */
export async function prefetchDestinationImages(): Promise<
  Record<string, string>
> {
  const entries = Object.entries(DESTINATION_WIKI_TITLES);
  const results = await Promise.allSettled(
    entries.map(async ([label, wikiTitle]) => {
      const url = await getWikipediaImage(wikiTitle);
      return [label, url] as const;
    }),
  );

  const map: Record<string, string> = {};
  for (const r of results) {
    if (r.status === 'fulfilled') {
      const [label, url] = r.value;
      map[label] = url;
    }
  }
  return map;
}
