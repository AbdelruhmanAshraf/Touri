/**
 * Tripmind API client (Phase 2).
 *
 * Live connection to the FastAPI backend at ``EXPO_PUBLIC_API_BASE_URL``:
 *   - REST:     POST /api/chat
 *               GET  /api/user/:uid/persona
 *               POST /api/user/:uid/persona
 *   - WS:       /api/chat/ws            (token-by-token streaming + agent_trace)
 *
 * Also persists a stable anonymous user_id + session_id + intake/last-trip
 * caches via AsyncStorage so screens can rehydrate offline.
 */

import AsyncStorage from '@react-native-async-storage/async-storage';
import * as Crypto from 'expo-crypto';

import { SECURE_KEYS, deleteSecure, getSecure, setSecure } from './secureStore';

const RAW_BASE =
  process.env.EXPO_PUBLIC_API_BASE_URL?.replace(/\/$/, '') ??
  'http://localhost:8000';

export const API_BASE_URL = RAW_BASE;

// ── Types (kept in sync with backend/routes/chat.py + agents/state.py) ────────
export type Language = 'en' | 'ar';

export type AgentStep = {
  agent: string;
  action: string;
  tool?: string | null;
  reasoning: string;
  result?: string | null;
  timestamp?: string;
};

export type Activity = {
  time?: string;
  emoji?: string;
  title?: string;
  type?: 'attraction' | 'restaurant' | 'hotel' | 'transport' | 'medical';
  rating?: number | null;
};

export type ItineraryDay = {
  day: number;
  date_label?: string;
  activities: Activity[];
};

export type Itinerary = {
  city?: string;
  duration?: number;
  transportation?: string;
  days?: ItineraryDay[];
  [k: string]: unknown;
};

export type BudgetBreakdown = {
  city?: string;
  duration?: number;
  trip_type?: string;
  people?: number;
  currency?: string;
  breakdown?: {
    flights?: number;
    accommodation?: number;
    meals?: number;
    activities?: number;
    local_transport?: number;
  };
  total_usd?: number;
  per_person_usd?: number;
  [k: string]: unknown;
};

export type MultimodalPart = {
  mime_type: string;
  data: string; // base64-encoded blob, no data: prefix
};

export type ChatRequest = {
  user_id: string;
  message: string;
  session_id?: string;
  language?: Language;
  history?: Array<{ role: 'user' | 'assistant'; content: string }>;
  // Optional multimodal attachments — when populated, the backend routes the
  // request to the native Gemini multimodal handler instead of LangGraph.
  parts?: MultimodalPart[];
  type?: 'multimodal' | 'text';
};

export type InitialTrip = {
  found: boolean;
  session_id?: string;
  destination?: string;
  party_size?: number;
  tourism_type?: string;
  budget_bracket?: string;
  message?: string;
  itinerary?: Itinerary | null;
  budget_breakdown?: BudgetBreakdown | null;
  suggestions?: string[];
  agent?: string;
  generated_at?: string;
};

export type ChatResponse = {
  session_id: string;
  message: string;
  agent: string;
  intent: string;
  language: Language;
  agent_trace: AgentStep[];
  itinerary?: Itinerary | null;
  budget_breakdown?: BudgetBreakdown | null;
  suggestions?: string[];
};

// ── Catalog types ─────────────────────────────────────────────────────────────
export type CatalogItemType =
  | 'attraction'
  | 'hotel'
  | 'restaurant'
  | 'transport'
  | 'flight'
  | 'event'
  | 'medical';

export type CatalogCard = {
  id: string;
  type: CatalogItemType;
  name: string;
  city: string;
  subtype: string;
  rating: number | null;
  price_egp: number | null;
  price_usd: number | null;
  currency: string;
  image: string;
  best_season: string;
  best_hours: string;
  entry_fee: string;
  event_date: string;
  transport_from: string;
  transport_to: string;
  transport_mode: string;
};

export type CatalogItem = CatalogCard & {
  image_urls: string[];
  description: string;
  location_url: string;
  distance_from_cairo_km: number | null;
  amenities: string[];
  cuisine: string;
  dishes: string[];
  dietary: string[];
  reviews_summary: string;
  event_duration: string;
  audience: string;
  organizer: string;
  transport_duration_h: number | null;
  transport_frequency: string;
  airline: string;
  flight_duration_min: number | null;
  stops: string;
  weekly_flights: number | null;
  departure_date: string;
  booking_link: string;
  services: string[];
  price_category: string;
};

export type CatalogHome = {
  events: CatalogCard[];
  best_now: CatalogCard[];
  offers: CatalogCard[];
  off_peak: CatalogCard[];
  popular: CatalogCard[];
  featured_hotels: CatalogCard[];
  local_food: CatalogCard[];
  // Phase-5 named proximity sections (only present when ``city`` is provided).
  nearby_suggestions?: CatalogCard[];
  localized_offers?: CatalogCard[];
  hot_spots?: CatalogCard[];
  meta: {
    total_attractions: number;
    total_hotels: number;
    total_restaurants: number;
    total_events: number;
    total_transport: number;
    total_medical: number;
  };
};

export type SearchResults = {
  query: string;
  type: string;
  results: CatalogCard[];
  count: number;
};

export type UserPersona = {
  user_id: string;
  preferred_destination: string | null;
  tourism_type: 'leisure' | 'medical';
  party_size: number;
  budget_bracket: 'economy' | 'mid_range' | 'luxury';
  extras: Record<string, unknown>;
  created_at?: string | null;
  updated_at?: string | null;
};

export type PersonaWrite = Partial<{
  preferred_destination: string;
  tourism_type: 'leisure' | 'medical';
  party_size: number;
  budget_bracket: 'economy' | 'mid_range' | 'luxury';
  extras: Record<string, unknown>;
}>;

export type IntakeData = {
  country: string;
  num_travelers: number;
  total_budget_usd: number;
  tourism_type: 'standard' | 'medical';
};

// ── Session token helpers (Phase 5) ──────────────────────────────────────────
export type AuthSession = {
  user_id: string;
  access_token: string;
  refresh_token?: string;
  expires_in: number;
};

export async function getAccessToken(): Promise<string | null> {
  return getSecure(SECURE_KEYS.ACCESS_TOKEN);
}

async function setAccessToken(token: string): Promise<void> {
  await setSecure(SECURE_KEYS.ACCESS_TOKEN, token);
}

async function setRefreshToken(token: string): Promise<void> {
  await setSecure(SECURE_KEYS.REFRESH_TOKEN, token);
}

export async function clearSessionTokens(): Promise<void> {
  await Promise.all([
    deleteSecure(SECURE_KEYS.ACCESS_TOKEN),
    deleteSecure(SECURE_KEYS.REFRESH_TOKEN),
  ]);
}

// ── Fetch helper ──────────────────────────────────────────────────────────────
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...((init?.headers as Record<string, string> | undefined) ?? {}),
  };

  // Attach the access token automatically when one is stored. Cookies are
  // also honoured server-side via `credentials: 'include'`.
  const token = await getAccessToken();
  if (token && !headers.Authorization) {
    headers.Authorization = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE_URL}${path}`, {
    credentials: 'include',
    ...init,
    headers,
  });
  if (!res.ok) {
    const body = await res.text().catch(() => '');
    throw new Error(`API ${res.status} ${res.statusText}: ${body}`);
  }
  return (await res.json()) as T;
}

export const api = {
  chat: (body: ChatRequest) =>
    request<ChatResponse>('/api/chat', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  getPersona: (uid: string) =>
    request<UserPersona>(`/api/user/${encodeURIComponent(uid)}/persona`),
  updatePersona: (uid: string, body: PersonaWrite) =>
    request<UserPersona>(`/api/user/${encodeURIComponent(uid)}/persona`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  deletePersona: (uid: string) =>
    request<{ deleted: boolean }>(`/api/user/${encodeURIComponent(uid)}/persona`, {
      method: 'DELETE',
    }),
  getInitialTrip: (uid: string) =>
    request<InitialTrip>(`/api/user/${encodeURIComponent(uid)}/trips/initial`),
  health: () =>
    fetch(`${API_BASE_URL}/health`).then(
      (r) => r.json() as Promise<Record<string, unknown>>,
    ),

  // ── Catalog ──────────────────────────────────────────────────────────────
  getCatalogHome: (params?: { city?: string; limit?: number }) => {
    const qs = new URLSearchParams();
    if (params?.city) qs.set('city', params.city);
    if (params?.limit) qs.set('limit', String(params.limit));
    const q = qs.toString();
    return request<CatalogHome>(`/api/catalog/home${q ? `?${q}` : ''}`);
  },
  getCatalogPlace: (type: CatalogItemType, id: string) =>
    request<CatalogItem>(`/api/catalog/place/${encodeURIComponent(type)}/${encodeURIComponent(id)}`),
  searchCatalog: (q: string, type: string = 'all', limit: number = 20) =>
    request<SearchResults>(
      `/api/catalog/search?q=${encodeURIComponent(q)}&type=${encodeURIComponent(type)}&limit=${limit}`,
    ),
  getCatalogCategories: () =>
    request<Record<string, string[]>>('/api/catalog/categories'),

  // ── Auth / Session (Phase 5) ─────────────────────────────────────────────
  startSession: async (body: { user_id: string; id_token?: string }) => {
    const data = await request<AuthSession>('/api/auth/session', {
      method: 'POST',
      body: JSON.stringify(body),
    });
    if (data.access_token) await setAccessToken(data.access_token);
    if (data.refresh_token) await setRefreshToken(data.refresh_token);
    return data;
  },
  refreshSession: async () => {
    const data = await request<AuthSession>('/api/auth/refresh', {
      method: 'POST',
    });
    if (data.access_token) await setAccessToken(data.access_token);
    if (data.refresh_token) await setRefreshToken(data.refresh_token);
    return data;
  },
  logoutSession: async () => {
    try {
      await request<{ ok: boolean }>('/api/auth/logout', { method: 'POST' });
    } finally {
      await clearSessionTokens();
    }
  },
  getMe: () =>
    request<{ user_id: string; authenticated: boolean; expires_at?: string }>(
      '/api/auth/me',
    ),
};

// ── WebSocket streaming ───────────────────────────────────────────────────────
export type WSEvent =
  | { type: 'status'; phase: 'thinking' | 'streaming'; session_id?: string; agent?: string; intent?: string; status_msg?: string; node?: string }
  | { type: 'trace'; step: AgentStep }
  | { type: 'token'; content: string }
  | {
      type: 'final';
      session_id: string;
      message: string;
      agent: string;
      intent: string;
      language: Language;
      agent_trace: AgentStep[];
      itinerary?: Itinerary | null;
      budget_breakdown?: BudgetBreakdown | null;
      suggestions?: string[];
    }
  | { type: 'error'; message: string };

export type StreamHandlers = {
  onToken?: (text: string) => void;
  onTrace?: (step: AgentStep) => void;
  onStatus?: (status: { phase: string; agent?: string; intent?: string; session_id?: string; status_msg?: string; node?: string }) => void;
  onFinal?: (final: Extract<WSEvent, { type: 'final' }>) => void;
  onError?: (error: string) => void;
  onClose?: () => void;
};

/**
 * Opens a WebSocket to /api/chat/ws and dispatches typed events to handlers.
 * Returns a small controller with ``send`` and ``close``.
 */
export function openChatStream(handlers: StreamHandlers) {
  const wsUrl =
    API_BASE_URL.replace(/^http/, 'ws') + '/api/chat/ws';
  const ws = new WebSocket(wsUrl);

  ws.onmessage = (ev) => {
    try {
      const data: WSEvent = JSON.parse(ev.data as string);
      switch (data.type) {
        case 'status':
          handlers.onStatus?.(data);
          break;
        case 'trace':
          handlers.onTrace?.(data.step);
          break;
        case 'token':
          handlers.onToken?.(data.content);
          break;
        case 'final':
          handlers.onFinal?.(data);
          break;
        case 'error':
          handlers.onError?.(data.message);
          break;
      }
    } catch (e) {
      handlers.onError?.(String(e));
    }
  };
  ws.onerror = () => handlers.onError?.('WebSocket error');
  ws.onclose = () => handlers.onClose?.();

  return {
    send: (payload: ChatRequest) =>
      new Promise<void>((resolve, reject) => {
        const trySend = () => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify(payload));
            resolve();
          } else if (ws.readyState === WebSocket.CONNECTING) {
            ws.addEventListener('open', () => {
              ws.send(JSON.stringify(payload));
              resolve();
            }, { once: true });
            ws.addEventListener('error', () => reject(new Error('WS failed')), { once: true });
          } else {
            reject(new Error('WS already closed'));
          }
        };
        trySend();
      }),
    close: () => ws.close(),
  };
}

// ── Persistent client identifiers ────────────────────────────────────────────
const USER_ID_KEY = 'tripmind_user_id';
const SESSION_ID_KEY = 'tripmind_session_id';
const INTAKE_KEY = 'tripmind_intake';
const LAST_TRIP_KEY = 'tripmind_last_trip';

function uuid(): string {
  return Crypto.randomUUID();
}

export async function getOrCreateUserId(): Promise<string> {
  const existing = await AsyncStorage.getItem(USER_ID_KEY);
  if (existing) return existing;
  const id = uuid();
  await AsyncStorage.setItem(USER_ID_KEY, id);
  return id;
}

export async function getOrCreateSessionId(): Promise<string> {
  const existing = await AsyncStorage.getItem(SESSION_ID_KEY);
  if (existing) return existing;
  const id = uuid();
  await AsyncStorage.setItem(SESSION_ID_KEY, id);
  return id;
}

export async function setSessionId(id: string): Promise<void> {
  await AsyncStorage.setItem(SESSION_ID_KEY, id);
}

export async function resetSessionId(): Promise<string> {
  const id = uuid();
  await AsyncStorage.setItem(SESSION_ID_KEY, id);
  return id;
}

export async function getIntake(): Promise<IntakeData | null> {
  const raw = await AsyncStorage.getItem(INTAKE_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as IntakeData;
  } catch {
    return null;
  }
}

export async function setIntake(data: IntakeData): Promise<void> {
  await AsyncStorage.setItem(INTAKE_KEY, JSON.stringify(data));
}

export type LastTrip = {
  itinerary?: Itinerary | null;
  budget_breakdown?: BudgetBreakdown | null;
  country?: string | null;
  tourism_type?: string | null;
  updated_at: string;
};

export async function saveLastTrip(trip: LastTrip): Promise<void> {
  await AsyncStorage.setItem(LAST_TRIP_KEY, JSON.stringify(trip));
}

export async function getLastTrip(): Promise<LastTrip | null> {
  const raw = await AsyncStorage.getItem(LAST_TRIP_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as LastTrip;
  } catch {
    return null;
  }
}
