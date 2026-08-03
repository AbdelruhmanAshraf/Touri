/**
 * Live chat screen.
 *
 * Connects to the FastAPI WebSocket at /api/chat/ws and streams tokens +
 * agent_trace events from the LangGraph multi-agent backend. There are no
 * mock messages, no hardcoded hotel cards — every piece of content comes
 * from the server. Itineraries and budget breakdowns are forwarded to the
 * Itinerary tab via AsyncStorage (``saveLastTrip``).
 *
 * Suggestion chips: shown pinned above the input after each AI reply.
 * Tapping a chip sends it as a message. When the user starts typing, chips
 * collapse.
 */

import { useEffect, useRef, useState } from 'react';
import {
  Alert,
  Animated,
  KeyboardAvoidingView,
  Modal,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { Image } from 'expo-image';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';
import { Feather, Ionicons, MaterialIcons } from '@expo/vector-icons';
import { useTranslation } from 'react-i18next';
import { useRouter } from 'expo-router';
import * as ImagePicker from 'expo-image-picker';
import * as DocumentPicker from 'expo-document-picker';
import * as FileSystem from 'expo-file-system/legacy';
import {
  useAudioRecorder,
  AudioModule,
  RecordingPresets,
  setAudioModeAsync,
} from 'expo-audio';

import { Colors } from '@/constants/Colors';
import { BG, SURFACE, BORDER_COLOR, PRIMARY, PRIMARY_DARK, PRIMARY_LIGHT, TEXT, MUTED, PLACEHOLDER, ERROR, RADIUS, RADIUS_XL, RADIUS_PILL } from '@/theme/tokens';
import AgentTracePanel from '@/components/AgentTracePanel';
import { GUEST_LIMITS, useAuth } from '@/hooks/useAuth';
import {
  api,
  type AgentStep,
  type ChatResponse,
  type ChatSessionSummary,
  type MultimodalPart,
  type RequirementsStatus,
  type SpotItem,
  type StructuredQuestionSet,
  type UiTrigger,
  type UiTriggerType,
  getOrCreateSessionId,
  getOrCreateUserId,
  openChatStream,
  resetSessionId,
  saveLastTrip,
  setSessionId,
} from '@/services/api';

type Attachment = { uri: string; mimeType: string; name: string };

type Turn = {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  attachments?: Attachment[];
  agent?: string;
  suggestions?: string[];
  structuredQuestions?: StructuredQuestionSet | null;
};

// ── Default starter suggestions ───────────────────────────────────────────────
const STARTER_EN = [
  'Plan a 5-day trip to Egypt',
  'Best time to visit Luxor',
  'Budget trip for 2 people',
  'Medical tourism in Cairo',
  'Top attractions in Aswan',
];
const STARTER_AR = [
  'خطّط رحلة 5 أيام لمصر',
  'أفضل وقت لزيارة الأقصر',
  'رحلة اقتصادية لشخصين',
  'السياحة العلاجية في القاهرة',
  'أبرز معالم أسوان',
];

export default function ChatScreen() {
  const { t, i18n } = useTranslation();
  const router = useRouter();
  const { user, isGuest, signOut } = useAuth();
  const isAr = i18n.language === 'ar';
  const insets = useSafeAreaInsets();

  const [turns, setTurns] = useState<Turn[]>([]);
  const [trace, setTrace] = useState<AgentStep[]>([]);
  const [input, setInput] = useState('');
  const [streaming, setStreaming] = useState(false);
  const [statusText, setStatusText] = useState<string | null>(null);
  const [activeAgent, setActiveAgent] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [isTraceVisible, setIsTraceVisible] = useState(false);
  const [activeSuggestions, setActiveSuggestions] = useState<string[]>(
    isAr ? STARTER_AR : STARTER_EN,
  );

  const [pendingAttachments, setPendingAttachments] = useState<Attachment[]>([]);
  const [isRecording, setIsRecording] = useState(false);
  // expo-audio hook-based recorder (replaces the imperative expo-av API).
  const audioRecorder = useAudioRecorder(RecordingPresets.HIGH_QUALITY);

  // ── Multi-select state for structured questions ──
  const [multiSelections, setMultiSelections] = useState<Record<string, Set<string>>>({});

  // ── Chat history drawer state ──
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [chatSessions, setChatSessions] = useState<ChatSessionSummary[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const drawerAnim = useRef(new Animated.Value(0)).current;

  // ── Requirements progress (from conversation state) ──
  const [reqStatus, setReqStatus] = useState<RequirementsStatus | null>(null);

  // ── UI Trigger confirmation modal state ──
  const [confirmModal, setConfirmModal] = useState<{
    visible: boolean;
    type: UiTriggerType;
    data: any;
  }>({ visible: false, type: 'plan', data: null });

  const userIdRef = useRef<string | null>(null);
  const sessionIdRef = useRef<string | null>(null);
  const scrollRef = useRef<ScrollView>(null);
  const chipsAnim = useRef(new Animated.Value(1)).current;
  // Buffer raw streamed tokens per assistant turn so we can re-strip the
  // *full* text on every chunk. This keeps markdown stripping correct even
  // when a `**` boundary spans two WebSocket tokens.
  const rawBufferRef = useRef<Record<string, string>>({});
  // Tracks the in-flight WS stream so we can cancel it when the user sends again
  const activeStreamRef = useRef<ReturnType<typeof openChatStream> | null>(null);
  // Guards against double-send while a request is in-flight
  const sendingRef = useRef(false);

  // ── Typing indicator animation ──
  const typingDots = useRef([
    new Animated.Value(0),
    new Animated.Value(0),
    new Animated.Value(0),
  ]).current;

  useEffect(() => {
    if (!streaming) return;
    const animations = typingDots.map((dot, i) =>
      Animated.loop(
        Animated.sequence([
          Animated.delay(i * 160),
          Animated.timing(dot, { toValue: 1, duration: 320, useNativeDriver: true }),
          Animated.timing(dot, { toValue: 0, duration: 320, useNativeDriver: true }),
        ]),
      ),
    );
    animations.forEach((a) => a.start());
    return () => animations.forEach((a) => a.stop());
  }, [streaming]);

  useEffect(() => {
    (async () => {
      const [uid, sid] = await Promise.all([getOrCreateUserId(), getOrCreateSessionId()]);
      userIdRef.current = user?.uid ?? uid;
      sessionIdRef.current = sid;
    })();
  }, [user?.uid]);

  // Reset chat state when user signs out
  useEffect(() => {
    if (!user) {
      setTurns([]);
      setTrace([]);
      setInput('');
      setStreaming(false);
      setStatusText(null);
      setActiveAgent(null);
      setActiveSuggestions(isAr ? STARTER_AR : STARTER_EN);
      setPendingAttachments([]);
      rawBufferRef.current = {};
      userIdRef.current = null;
      sessionIdRef.current = null;
    }
  }, [user]);

  // Collapse chips when user is typing
  useEffect(() => {
    Animated.timing(chipsAnim, {
      toValue: input.length > 0 ? 0 : 1,
      duration: 180,
      useNativeDriver: true,
    }).start();
  }, [input]);

  // ── Drawer animation ──────────────────────────────────────────────────────
  useEffect(() => {
    Animated.timing(drawerAnim, {
      toValue: drawerOpen ? 1 : 0,
      duration: 250,
      useNativeDriver: true,
    }).start();
  }, [drawerOpen]);

  const openDrawer = async () => {
    setDrawerOpen(true);
    setHistoryLoading(true);
    try {
      const uid = userIdRef.current ?? (await getOrCreateUserId());
      const data = await api.listSessions(uid);
      setChatSessions(data.sessions ?? []);
    } catch { /* silently fail */ }
    finally { setHistoryLoading(false); }
  };

  const loadSession = async (sid: string) => {
    setDrawerOpen(false);
    try {
      const uid = userIdRef.current ?? (await getOrCreateUserId());
      const data = await api.getSessionMessages(uid, sid);
      const loadedTurns: Turn[] = (data.messages ?? []).map((m, i) => ({
        id: `${sid}-${i}`,
        role: m.role,
        text: m.content,
        agent: m.agent ?? undefined,
      }));
      setTurns(loadedTurns);
      sessionIdRef.current = sid;
      await setSessionId(sid);
      setActiveSuggestions([]);
      setTrace([]);
      setReqStatus(null);
      setErr(null);
      setStatusText(null);
      setActiveAgent(null);
      setStreaming(false);
      rawBufferRef.current = {};
      setTimeout(() => scrollRef.current?.scrollToEnd({ animated: false }), 200);
    } catch {
      setErr(isAr ? 'فشل تحميل المحادثة' : 'Failed to load conversation');
    }
  };

  const startNewChat = async () => {
    // Cancel any in-flight stream before resetting
    activeStreamRef.current?.cancel();
    activeStreamRef.current = null;
    sendingRef.current = false;
    setDrawerOpen(false);
    const newSid = await resetSessionId();
    sessionIdRef.current = newSid;
    setTurns([]);
    setTrace([]);
    setInput('');
    setStreaming(false);
    setStatusText(null);
    setActiveAgent(null);
    setActiveSuggestions(isAr ? STARTER_AR : STARTER_EN);
    setReqStatus(null);
    rawBufferRef.current = {};
  };

  // ── Strip markdown bold/italic asterisks for clean bidi rendering ───────────
  // Handles both complete markdown tokens and partial mid-stream asterisks.
  // Aggressively strips all `*` used for formatting so the bidi layout never
  // shifts when a closing `*` arrives later in the token stream.
  const stripMarkdown = (text: string): string =>
    text
      .replace(/\*\*([^*]+)\*\*/g, '$1')
      .replace(/\*([^*]+)\*/g, '$1')
      .replace(/^\*{1,2}|\*{1,2}$/g, '')
      .replace(/\*{2,}/g, '');

  // ── Parse and extract UI trigger blocks from streamed text ─────────────────
  const parseUiTrigger = (text: string): { cleanText: string; trigger: UiTrigger | null } => {
    const marker = '---UI_TRIGGER---';
    if (!text.includes(marker)) return { cleanText: text, trigger: null };
    const [before, jsonPart] = text.split(marker, 2);
    try {
      const parsed = JSON.parse(jsonPart.trim()) as UiTrigger;
      if (parsed.ui_trigger === 'show_popup') {
        return { cleanText: before.trim(), trigger: parsed };
      }
    } catch { /* JSON parse failed — show full text */ }
    return { cleanText: before.trim(), trigger: null };
  };

  // ── Confirm and sync trigger to Firestore ─────────────────────────────────
  const handleConfirmTrigger = async () => {
    const { type, data } = confirmModal;
    setConfirmModal({ visible: false, type: 'plan', data: null });
    try {
      const uid = userIdRef.current ?? (await getOrCreateUserId());
      if (type === 'plan') {
        await api.patchInitialTrip(uid, { itinerary: data });
        await saveLastTrip({
          itinerary: data, budget_breakdown: null,
          country: data?.city ?? null, tourism_type: null,
          updated_at: new Date().toISOString(),
        });
      } else if (type === 'budget') {
        await api.patchInitialTrip(uid, { budget_breakdown: data });
        await saveLastTrip({
          itinerary: null, budget_breakdown: data,
          country: null, tourism_type: null,
          updated_at: new Date().toISOString(),
        });
      } else if (type === 'spots') {
        const spots = data as SpotItem[] | undefined;
        const msg = spots?.map((s) => `${s.name} (${s.city})`).join(', ') ?? '';
        await api.patchInitialTrip(uid, { message: `Recommended spots: ${msg}` });
      }
    } catch (e) {
      console.warn('[chat] trigger sync failed', e);
    }
  };

  // ── Image picker ──────────────────────────────────────────────────────────
  const pickImage = async () => {
    const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (status !== 'granted') {
      Alert.alert('Permission required', 'Camera roll access is needed to attach images.');
      return;
    }
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      quality: 0.7,
      allowsMultipleSelection: false,
    });
    if (!result.canceled && result.assets.length > 0) {
      const asset = result.assets[0];
      setPendingAttachments((prev) => [
        ...prev,
        { uri: asset.uri, mimeType: asset.mimeType ?? 'image/jpeg', name: asset.fileName ?? 'image.jpg' },
      ]);
    }
  };

  // ── Document picker (PDFs) ────────────────────────────────────────────────
  const pickDocument = async () => {
    try {
      const result = await DocumentPicker.getDocumentAsync({
        type: 'application/pdf',
        copyToCacheDirectory: true,
        multiple: false,
      });
      if (result.canceled || !result.assets || result.assets.length === 0) return;
      const asset = result.assets[0];
      setPendingAttachments((prev) => [
        ...prev,
        {
          uri: asset.uri,
          mimeType: asset.mimeType ?? 'application/pdf',
          name: asset.name ?? 'document.pdf',
        },
      ]);
    } catch (e) {
      console.warn('[chat] document picker error', e);
    }
  };

  // ── Base64-encode a local file URI for the WebSocket payload ──────────────
  const toBase64Part = async (a: Attachment): Promise<MultimodalPart | null> => {
    try {
      const data = await FileSystem.readAsStringAsync(a.uri, {
        encoding: FileSystem.EncodingType.Base64,
      });
      return { mime_type: a.mimeType, data };
    } catch (e) {
      console.warn('[chat] base64 encode failed for', a.uri, e);
      return null;
    }
  };

  // ── Audio recorder (expo-audio) ───────────────────────────────────────────
  const toggleRecording = async () => {
    if (isRecording) {
      // Stop and attach the audio
      try {
        await audioRecorder.stop();
        const uri = audioRecorder.uri;
        if (uri) {
          setPendingAttachments((prev) => [
            ...prev,
            { uri, mimeType: 'audio/m4a', name: 'voice.m4a' },
          ]);
        }
      } catch (e) { console.warn('[chat] stop recording error', e); }
      setIsRecording(false);
    } else {
      // Start recording
      try {
        const perm = await AudioModule.requestRecordingPermissionsAsync();
        if (!perm.granted) {
          Alert.alert('Permission required', 'Microphone access is needed to record voice.');
          return;
        }
        await setAudioModeAsync({ allowsRecording: true, playsInSilentMode: true });
        await audioRecorder.prepareToRecordAsync();
        audioRecorder.record();
        setIsRecording(true);
      } catch (e) { console.warn('[chat] start recording error', e); }
    }
  };

  const userMessageCount = turns.filter((m) => m.role === 'user').length;
  const guestLimitReached = isGuest && userMessageCount >= GUEST_LIMITS.maxChatMessagesPerSession;

  const send = async (overrideText?: string) => {
    const text = (overrideText ?? input).trim();
    // Allow sending with attachments only (no text), but never with neither.
    if (!text && pendingAttachments.length === 0) return;
    // Hard guard: prevent double-send if a send is already in-flight
    if (sendingRef.current) {
      // Cancel the previous stream so the new message takes over
      activeStreamRef.current?.cancel();
      activeStreamRef.current = null;
      sendingRef.current = false;
      setStreaming(false);
      setStatusText(null);
    }
    if (guestLimitReached) {
      setErr(t('chat.guestEnded', { used: userMessageCount, limit: GUEST_LIMITS.maxChatMessagesPerSession }) ?? 'Guest preview ended.');
      return;
    }

    const uid = userIdRef.current ?? (await getOrCreateUserId());
    const sid = sessionIdRef.current ?? (await getOrCreateSessionId());

    const attachments = pendingAttachments.slice();
    const userTurn: Turn = { id: `${Date.now()}-u`, role: 'user', text, attachments };
    const assistantTurnId = `${Date.now()}-a`;

    setTurns((prev) => [...prev, userTurn, { id: assistantTurnId, role: 'assistant', text: '' }]);
    setInput('');
    setPendingAttachments([]);
    setActiveSuggestions([]);
    setStreaming(true);
    sendingRef.current = true;
    setStatusText(t('chat.thinking'));
    setErr(null);
    setTrace([]);

    setTimeout(() => scrollRef.current?.scrollToEnd({ animated: true }), 100);

    // Reset the raw buffer for this turn — we re-strip the FULL text on each
    // token so a `**` boundary that spans two WS frames is still removed.
    rawBufferRef.current[assistantTurnId] = '';

    const appendToken = (token: string) => {
      const buffered = (rawBufferRef.current[assistantTurnId] ?? '') + token;
      rawBufferRef.current[assistantTurnId] = buffered;
      const clean = stripMarkdown(buffered);
      setTurns((prev) => prev.map((m) => (m.id === assistantTurnId ? { ...m, text: clean } : m)));
    };

    const stream = openChatStream({
      onStatus: (s) => {
        if (s.phase === 'thinking') {
          setStatusText(isAr ? 'جاري التفكير...' : 'Thinking...');
          setActiveAgent(null);
        }
        if (s.phase === 'streaming') {
          const node = (s as any).node || '';
          const agentLabel = (s as any).agent || '';
          const statusMsg = (s as any).status_msg || '';
          const phaseMap: Record<string, { en: string; ar: string }> = {
            memory: { en: 'Loading profile...', ar: 'جاري تحميل ملفك...' },
            enforcer: { en: 'Applying memory...', ar: 'جاري تطبيق الذاكرة...' },
            router: { en: 'Analyzing request...', ar: 'جاري تحليل طلبك...' },
            planner: { en: 'Building itinerary...', ar: 'جاري بناء خطتك...' },
            budget: { en: 'Calculating costs...', ar: 'جاري حساب التكاليف...' },
            concierge: { en: 'Finding recommendations...', ar: 'جاري البحث عن توصيات...' },
            general: { en: 'Preparing response...', ar: 'جاري إعداد الرد...' },
            needs_info: { en: 'Getting ready...', ar: 'جاري التحضير...' },
          };
          const mapped = node && phaseMap[node] ? (isAr ? phaseMap[node].ar : phaseMap[node].en) : null;
          setActiveAgent(agentLabel);
          setStatusText(mapped || statusMsg || agentLabel || (isAr ? 'جاري الكتابة...' : 'Writing...'));
        }
      },
      onTrace: (step) => setTrace((prev) => [...prev, step]),
      onToken: appendToken,
      onFinal: async (final) => {
        sendingRef.current = false;
        setStatusText(null);
        setActiveAgent(null);
        setStreaming(false);

        const suggestions: string[] = final.suggestions ?? [];

        // Parse ui_trigger block from the message and strip it for display
        const { cleanText, trigger } = parseUiTrigger(stripMarkdown(final.message));

        setTurns((prev) =>
          prev.map((m) =>
            m.id === assistantTurnId
              ? { ...m, text: cleanText, agent: final.agent, suggestions, structuredQuestions: final.structured_questions ?? null }
              : m,
          ),
        );
        setActiveSuggestions(suggestions);
        if (final.requirements_status) {
          setReqStatus(final.requirements_status as RequirementsStatus);
        }

        // If backend injected a ui_trigger, show the confirmation popup
        if (trigger) {
          setConfirmModal({ visible: true, type: trigger.type, data: trigger.payload });
        }

        if (final.session_id && final.session_id !== sid) {
          sessionIdRef.current = final.session_id;
          await setSessionId(final.session_id);
        }
        if (final.itinerary || final.budget_breakdown) {
          await saveLastTrip({
            itinerary: final.itinerary ?? null,
            budget_breakdown: final.budget_breakdown ?? null,
            country: final.itinerary?.city ?? null,
            tourism_type: null,
            updated_at: new Date().toISOString(),
          });
        }

        stream.close();
        activeStreamRef.current = null;
        setTimeout(() => scrollRef.current?.scrollToEnd({ animated: true }), 150);
      },
      onError: (msg) => {
        sendingRef.current = false;
        setErr(msg);
        setStreaming(false);
        setStatusText(null);
        stream.close();
        activeStreamRef.current = null;
      },
      onClose: () => {
        if (!stream.finalSeen) {
          sendingRef.current = false;
          setStreaming(false);
        }
      },
    });
    activeStreamRef.current = stream;

    // Encode all attachments to base64 before sending (parallel for speed).
    const encoded: MultimodalPart[] = [];
    if (attachments.length > 0) {
      const results = await Promise.all(attachments.map(toBase64Part));
      for (const r of results) if (r) encoded.push(r);
    }
    const hasMultimodal = encoded.length > 0;

    try {
      await stream.send({
        user_id: uid,
        session_id: sid,
        message: text,
        language: isAr ? 'ar' : 'en',
        history: turns.map((m) => ({ role: m.role, content: m.text })),
        use_graph: !hasMultimodal,
        ...(hasMultimodal ? { type: 'multimodal', parts: encoded } : {}),
      });
    } catch (wsErr: any) {
      // WebSocket unavailable or timed-out — degrade to single-shot REST once.
      // Guard: if WS already delivered a final event, skip REST to avoid double-final.
      if (stream.finalSeen) return;
      stream.cancel();
      activeStreamRef.current = null;
      try {
        const res: ChatResponse = await api.chat({
          user_id: uid,
          session_id: sid,
          message: text,
          language: isAr ? 'ar' : 'en',
          ...(hasMultimodal ? { type: 'multimodal', parts: encoded } : {}),
        });
        // Mark final seen so the WS onFinal (if it ever fires) is ignored
        stream.setFinalSeen();
        const { cleanText, trigger } = parseUiTrigger(stripMarkdown(res.message));
        setTurns((prev) =>
          prev.map((m) =>
            m.id === assistantTurnId
              ? { ...m, text: cleanText, agent: res.agent, suggestions: res.suggestions, structuredQuestions: res.structured_questions ?? null }
              : m,
          ),
        );
        setTrace(res.agent_trace || []);
        setActiveSuggestions(res.suggestions ?? []);
        if (res.requirements_status) setReqStatus(res.requirements_status as RequirementsStatus);
        if (trigger) setConfirmModal({ visible: true, type: trigger.type, data: trigger.payload });
        if (res.session_id && res.session_id !== sid) {
          sessionIdRef.current = res.session_id;
          await setSessionId(res.session_id);
        }
        if (res.itinerary || res.budget_breakdown) {
          await saveLastTrip({
            itinerary: res.itinerary ?? null,
            budget_breakdown: res.budget_breakdown ?? null,
            country: res.itinerary?.city ?? null,
            tourism_type: null,
            updated_at: new Date().toISOString(),
          });
        }
      } catch (e: any) {
        setErr(e?.message ?? 'Connection error. Please try again.');
      } finally {
        sendingRef.current = false;
        setStreaming(false);
        setStatusText(null);
      }
    }
  };

  // ── Chat session management ────────────────────────────────────────────────
  const deleteSession = async (sid: string) => {
    Alert.alert(
      isAr ? 'حذف المحادثة' : 'Delete Chat',
      isAr ? 'هل أنت متأكد من حذف هذه المحادثة؟' : 'Are you sure you want to delete this chat?',
      [
        { text: isAr ? 'إلغاء' : 'Cancel', style: 'cancel' },
        {
          text: isAr ? 'حذف' : 'Delete',
          style: 'destructive',
          onPress: async () => {
            setChatSessions((prev) => prev.filter((s) => s.session_id !== sid));
            if (sessionIdRef.current === sid) {
              await startNewChat();
            }
            try {
              const uid = userIdRef.current ?? (await getOrCreateUserId());
              await api.deleteSession(uid, sid);
            } catch { /* silent — local state already updated */ }
          },
        },
      ],
    );
  };

  const renameSession = (sid: string, currentName: string) => {
    Alert.prompt(
      isAr ? 'تسمية المحادثة' : 'Rename Chat',
      isAr ? 'أدخل اسمًا جديدًا' : 'Enter a new name',
      [
        { text: isAr ? 'إلغاء' : 'Cancel', style: 'cancel' },
        {
          text: isAr ? 'حفظ' : 'Save',
          onPress: async (newName?: string) => {
            if (newName?.trim()) {
              const trimmed = newName.trim();
              setChatSessions((prev) =>
                prev.map((s) =>
                  s.session_id === sid ? { ...s, destination: trimmed, title: trimmed } : s,
                ),
              );
              try {
                const uid = userIdRef.current ?? (await getOrCreateUserId());
                await api.renameSession(uid, sid, trimmed);
              } catch { /* silent — local state already updated */ }
            }
          },
        },
      ],
      'plain-text',
      currentName,
    );
  };

  const handleSignIn = async () => { await signOut(); router.replace('/'); };

  return (
    <View style={[styles.safeArea, { paddingTop: insets.top }]}>
      {/* ── Header ── */}
      <View style={[styles.header, { flexDirection: isAr ? 'row-reverse' : 'row' }]}>
        <View style={[styles.headerLeft, { flexDirection: isAr ? 'row-reverse' : 'row' }]}>
          <View style={styles.aiDot}>
            <MaterialIcons name="smart-toy" size={14} color="#fff" />
          </View>
          <Text style={styles.headerTitle}>{t('appName')}</Text>
        </View>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
          <TouchableOpacity
            onPress={() => setIsTraceVisible(true)}
            style={styles.traceBtn}
          >
            <MaterialIcons name="memory" size={16} color={Colors.primary} />
            <Text style={styles.traceBtnTxt}>{t('chat.trace')}</Text>
          </TouchableOpacity>
          <TouchableOpacity onPress={openDrawer} style={styles.hamburgerBtn}>
            <Feather name="menu" size={20} color={TEXT} />
          </TouchableOpacity>
        </View>
      </View>

      {/* Requirements progress indicator (compact) */}
      {reqStatus && reqStatus.percentage > 0 && reqStatus.percentage < 100 && (
        <View style={styles.headerProgress}>
          <View style={styles.headerProgressBar}>
            <View style={[styles.headerProgressFill, { width: `${reqStatus.percentage}%` }]} />
          </View>
          <Text style={styles.headerProgressTxt}>
            {isAr ? `${Math.round(reqStatus.percentage)}% مكتمل` : `${Math.round(reqStatus.percentage)}% complete`}
          </Text>
        </View>
      )}

      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        {/* ── Messages ── */}
        <ScrollView
          ref={scrollRef}
          contentContainerStyle={styles.scrollContent}
          showsVerticalScrollIndicator={false}
          onContentSizeChange={() => scrollRef.current?.scrollToEnd({ animated: true })}
        >
          {/* Empty state */}
          {turns.length === 0 && !streaming && (
            <View style={styles.emptyState}>
              <View style={styles.emptyIcon}>
                <MaterialIcons name="auto-awesome" size={32} color={PRIMARY} />
              </View>
              <Text style={[styles.emptyTitle, { textAlign: isAr ? 'right' : 'left' }]}>
                {t('chat.emptyTitle')}
              </Text>
              <Text style={[styles.emptySub, { textAlign: isAr ? 'right' : 'left' }]}>
                {t('chat.emptySub')}
              </Text>
            </View>
          )}

          <View style={{ gap: 20 }}>
            {turns.map((m) =>
              m.role === 'user' ? (
                <View key={m.id} style={[styles.userRow, { alignItems: isAr ? 'flex-start' : 'flex-end' }]}>
                  {m.attachments && m.attachments.length > 0 && (
                    <View style={styles.msgAttachmentsRow}>
                      {m.attachments.map((a, i) =>
                        a.mimeType.startsWith('image/') ? (
                          <Image key={i} source={{ uri: a.uri }} style={[styles.msgAttachImg, { borderRadius: 12 }]} contentFit="cover" />
                        ) : a.mimeType === 'application/pdf' ? (
                          <View key={i} style={styles.msgAttachAudio}>
                            <Feather name="file-text" size={14} color={PRIMARY} />
                            <Text style={styles.msgAttachAudioTxt}>{a.name}</Text>
                          </View>
                        ) : (
                          <View key={i} style={styles.msgAttachAudio}>
                            <Feather name="mic" size={14} color={PRIMARY} />
                            <Text style={styles.msgAttachAudioTxt}>Voice note</Text>
                          </View>
                        ),
                      )}
                    </View>
                  )}
                  <View style={styles.userBubble}>
                    <Text style={[styles.userText, { textAlign: isAr ? 'right' : 'left' }]}>{m.text}</Text>
                  </View>
                </View>
              ) : (
                <View key={m.id} style={styles.aiRow}>
                  <View style={[styles.aiMeta, { flexDirection: isAr ? 'row-reverse' : 'row' }]}>
                    <View style={styles.aiIcon}>
                      <MaterialIcons name="smart-toy" size={12} color="#fff" />
                    </View>
                    <Text style={styles.aiLabel}>{m.agent || t('chat.agentLabel')}</Text>
                  </View>
                  <View style={styles.aiBubble}>
                    {!m.text && streaming && m.id === turns[turns.length - 1]?.id ? (
                      <View style={styles.skeletonContainer}>
                        <View style={[styles.skeletonLine, { width: '90%' }]} />
                        <View style={[styles.skeletonLine, { width: '70%' }]} />
                        <View style={[styles.skeletonLine, { width: '45%' }]} />
                      </View>
                    ) : (
                      <Text
                        style={[
                          styles.aiText,
                          {
                            textAlign: isAr ? 'right' : 'left',
                            writingDirection: isAr ? 'rtl' : 'ltr',
                          },
                        ]}
                      >
                        {m.text || (streaming ? '…' : '')}
                      </Text>
                    )}
                  </View>
                  {/* Structured question cards */}
                  {m.structuredQuestions?.questions && m.structuredQuestions.questions.length > 0 && !streaming && (
                    <View style={styles.sqContainer}>
                      {m.structuredQuestions.questions.map((q) => {
                        const isMulti = q.input_type === 'multi_select';
                        const selected = multiSelections[q.field] ?? new Set<string>();
                        return (
                          <View key={q.field} style={styles.sqGroup}>
                            <Text style={[styles.sqQuestion, { textAlign: isAr ? 'right' : 'left' }]}>
                              {isAr ? q.question.ar : q.question.en}
                            </Text>
                            <View style={styles.sqOptionsRow}>
                              {q.options.map((opt) => {
                                const isSelected = selected.has(opt.id);
                                return (
                                  <TouchableOpacity
                                    key={opt.id}
                                    style={[styles.sqOption, isSelected && styles.sqOptionSelected]}
                                    activeOpacity={0.7}
                                    onPress={() => {
                                      if (isMulti) {
                                        setMultiSelections((prev) => {
                                          const cur = new Set(prev[q.field] ?? []);
                                          if (cur.has(opt.id)) cur.delete(opt.id);
                                          else cur.add(opt.id);
                                          return { ...prev, [q.field]: cur };
                                        });
                                      } else {
                                        const label = isAr ? opt.label.ar : opt.label.en;
                                        send(opt.emoji ? `${opt.emoji} ${label}` : label);
                                      }
                                    }}
                                  >
                                    {opt.emoji && <Text style={styles.sqEmoji}>{opt.emoji}</Text>}
                                    <Text style={[styles.sqOptionLabel, isSelected && styles.sqOptionLabelSelected]}>
                                      {isAr ? opt.label.ar : opt.label.en}
                                    </Text>
                                    {opt.description && (
                                      <Text style={[styles.sqOptionDesc]}>
                                        {isAr ? opt.description.ar : opt.description.en}
                                      </Text>
                                    )}
                                    {isMulti && isSelected && (
                                      <Feather name="check" size={14} color={PRIMARY} style={{ marginTop: 2 }} />
                                    )}
                                  </TouchableOpacity>
                                );
                              })}
                            </View>
                            {isMulti && selected.size > 0 && (
                              <TouchableOpacity
                                style={styles.sqConfirmBtn}
                                onPress={() => {
                                  const labels = q.options
                                    .filter((o) => selected.has(o.id))
                                    .map((o) => {
                                      const lbl = isAr ? o.label.ar : o.label.en;
                                      return o.emoji ? `${o.emoji} ${lbl}` : lbl;
                                    });
                                  send(labels.join(', '));
                                  setMultiSelections((prev) => {
                                    const next = { ...prev };
                                    delete next[q.field];
                                    return next;
                                  });
                                }}
                              >
                                <Text style={styles.sqConfirmTxt}>
                                  {isAr ? `تأكيد (${selected.size})` : `Confirm (${selected.size})`}
                                </Text>
                              </TouchableOpacity>
                            )}
                          </View>
                        );
                      })}
                    </View>
                  )}
                </View>
              ),
            )}

            {streaming && statusText && (
              <View style={[styles.statusRow, { justifyContent: isAr ? 'flex-end' : 'flex-start' }]}>
                <View style={styles.typingDotsRow}>
                  {typingDots.map((dot, i) => (
                    <Animated.View
                      key={i}
                      style={[
                        styles.typingDot,
                        { transform: [{ scale: dot.interpolate({ inputRange: [0, 1], outputRange: [0.7, 1.2] }) }], opacity: dot.interpolate({ inputRange: [0, 1], outputRange: [0.4, 1] }) },
                      ]}
                    />
                  ))}
                </View>
                <Text style={styles.statusTxt}>
                  {activeAgent ? `${activeAgent} · ${statusText}` : statusText}
                </Text>
              </View>
            )}
          </View>

          {err && (
            <View style={styles.errBanner}>
              <Ionicons name="warning-outline" size={16} color={ERROR} />
              <Text style={styles.errTxt}>{err}</Text>
            </View>
          )}
        </ScrollView>

        {/* ── Guest banner ── */}
        {isGuest && (
          <View style={[styles.guestBanner, { flexDirection: isAr ? 'row-reverse' : 'row' }]}>
            <MaterialIcons name="lock-outline" size={16} color={Colors.primary} />
            <Text style={[styles.guestTxt, { textAlign: isAr ? 'right' : 'left' }]}>
              {guestLimitReached
                ? t('chat.guestEnded', { used: userMessageCount, limit: GUEST_LIMITS.maxChatMessagesPerSession })
                : t('chat.guestBanner', { used: userMessageCount, limit: GUEST_LIMITS.maxChatMessagesPerSession })}
            </Text>
            <TouchableOpacity onPress={handleSignIn} style={styles.guestSignInBtn}>
              <Text style={styles.guestSignInTxt}>{t('chat.signIn')}</Text>
            </TouchableOpacity>
          </View>
        )}

        {/* ── Suggestion chips ── */}
        <Animated.View
          style={[
            styles.chipsContainer,
            {
              opacity: chipsAnim,
              transform: [{ translateY: chipsAnim.interpolate({ inputRange: [0, 1], outputRange: [12, 0] }) }],
              pointerEvents: activeSuggestions.length > 0 && !streaming ? 'auto' : 'none',
            },
          ]}
        >
          {activeSuggestions.length > 0 && !streaming && (
            <ScrollView
              horizontal
              showsHorizontalScrollIndicator={false}
              contentContainerStyle={styles.chipsScroll}
            >
              {activeSuggestions.map((chip, i) => (
                <TouchableOpacity
                  key={i}
                  style={styles.chip}
                  onPress={() => send(chip)}
                  activeOpacity={0.75}
                >
                  <Text style={styles.chipTxt}>{chip}</Text>
                </TouchableOpacity>
              ))}
            </ScrollView>
          )}
        </Animated.View>

        {/* ── Input bar ── */}
        <View style={styles.inputArea}>
          {/* Pending attachment previews */}
          {pendingAttachments.length > 0 && (
            <View style={styles.attachmentsRow}>
              {pendingAttachments.map((a, i) => (
                <View key={i} style={styles.attachmentChip}>
                  {a.mimeType.startsWith('image/') ? (
                    <Image source={{ uri: a.uri }} style={styles.attachThumb} contentFit="cover" />
                  ) : a.mimeType === 'application/pdf' ? (
                    <Feather name="file-text" size={16} color={PRIMARY} />
                  ) : (
                    <Feather name="mic" size={14} color={PRIMARY} />
                  )}
                  <TouchableOpacity
                    style={styles.attachRemove}
                    onPress={() => setPendingAttachments((prev) => prev.filter((_, j) => j !== i))}
                  >
                    <Feather name="x" size={10} color="#fff" />
                  </TouchableOpacity>
                </View>
              ))}
            </View>
          )}

          <View style={[styles.inputRow, { flexDirection: isAr ? 'row-reverse' : 'row' }]}>
            {/* Mic button */}
            <TouchableOpacity
              style={[styles.mediaBtn, isRecording && styles.mediaBtnActive]}
              onPress={toggleRecording}
              disabled={streaming || guestLimitReached}
            >
              <Feather name="mic" size={18} color={isRecording ? '#fff' : MUTED} />
            </TouchableOpacity>

            {/* Image picker button */}
            <TouchableOpacity
              style={styles.mediaBtn}
              onPress={pickImage}
              disabled={streaming || guestLimitReached}
            >
              <Feather name="image" size={18} color={MUTED} />
            </TouchableOpacity>

            {/* Document picker button (PDF) */}
            <TouchableOpacity
              style={styles.mediaBtn}
              onPress={pickDocument}
              disabled={streaming || guestLimitReached}
            >
              <Feather name="paperclip" size={18} color={MUTED} />
            </TouchableOpacity>

            <TextInput
              style={[styles.inputField, { textAlign: isAr ? 'right' : 'left' }]}
              placeholder={t('chat.placeholder')}
              placeholderTextColor={PLACEHOLDER}
              value={input}
              onChangeText={setInput}
              multiline
              editable={!streaming && !guestLimitReached}
              onSubmitEditing={() => send()}
              returnKeyType="send"
            />
            <TouchableOpacity
              style={[styles.sendBtn, (streaming || (!input.trim() && pendingAttachments.length === 0)) && styles.sendBtnDisabled]}
              onPress={() => send()}
              disabled={streaming || (!input.trim() && pendingAttachments.length === 0) || guestLimitReached}
            >
              <Feather name={isAr ? 'arrow-down' : 'arrow-up'} size={18} color="#fff" />
            </TouchableOpacity>
          </View>
        </View>
      </KeyboardAvoidingView>

      <AgentTracePanel
        isVisible={isTraceVisible}
        onClose={() => setIsTraceVisible(false)}
        trace={trace}
      />

      {/* ── Chat History Drawer ── */}
      <Modal visible={drawerOpen} animationType="slide" transparent presentationStyle="overFullScreen">
        <View style={styles.drawerOverlay}>
          <TouchableOpacity style={styles.drawerBackdrop} onPress={() => setDrawerOpen(false)} activeOpacity={1} />
          <Animated.View style={[styles.drawerPanel, { transform: [{ translateX: drawerAnim.interpolate({ inputRange: [0, 1], outputRange: [300, 0] }) }], paddingTop: insets.top }]}>
            <View style={styles.drawerHeader}>
              <Text style={styles.drawerTitle}>
                {isAr ? 'المحادثات' : 'Chat History'}
              </Text>
              <TouchableOpacity onPress={() => setDrawerOpen(false)}>
                <Feather name="x" size={22} color={MUTED} />
              </TouchableOpacity>
            </View>

            {/* New Chat button */}
            <TouchableOpacity style={styles.newChatBtn} onPress={startNewChat}>
              <Feather name="plus" size={16} color="#fff" />
              <Text style={styles.newChatTxt}>{isAr ? 'محادثة جديدة' : 'New Chat'}</Text>
            </TouchableOpacity>

            {/* Requirements progress bar */}
            {reqStatus && reqStatus.percentage > 0 && (
              <View style={styles.reqProgressContainer}>
                <View style={styles.reqProgressRow}>
                  <Text style={styles.reqProgressLabel}>
                    {isAr ? 'اكتمال المتطلبات' : 'Requirements'}
                  </Text>
                  <Text style={styles.reqProgressPct}>{reqStatus.percentage}%</Text>
                </View>
                <View style={styles.reqProgressBar}>
                  <View style={[styles.reqProgressFill, { width: `${reqStatus.percentage}%` }]} />
                </View>
              </View>
            )}

            <ScrollView style={{ flex: 1 }} contentContainerStyle={{ padding: 16, gap: 8 }}>
              {historyLoading ? (
                <View style={{ padding: 40, alignItems: 'center' }}>
                  <Text style={{ color: MUTED }}>{isAr ? 'جاري التحميل...' : 'Loading...'}</Text>
                </View>
              ) : chatSessions.length > 0 ? (
                chatSessions.map((s) => (
                  <TouchableOpacity
                    key={s.session_id}
                    style={[
                      styles.sessionCard,
                      s.session_id === sessionIdRef.current && styles.sessionCardActive,
                    ]}
                    onPress={() => loadSession(s.session_id)}
                    onLongPress={() => {
                      Alert.alert(
                        s.destination || (isAr ? 'محادثة' : 'Chat'),
                        '',
                        [
                          { text: isAr ? 'إعادة تسمية' : 'Rename', onPress: () => renameSession(s.session_id, s.destination || '') },
                          { text: isAr ? 'حذف' : 'Delete', style: 'destructive', onPress: () => deleteSession(s.session_id) },
                          { text: isAr ? 'إلغاء' : 'Cancel', style: 'cancel' },
                        ],
                      );
                    }}
                    activeOpacity={0.7}
                  >
                    <View style={styles.sessionCardTop}>
                      <View style={styles.sessionIcon}>
                        <Feather name="message-circle" size={14} color={PRIMARY} />
                      </View>
                      <View style={{ flex: 1 }}>
                        <Text style={styles.sessionDest} numberOfLines={1}>
                          {s.destination || (isAr ? 'محادثة' : 'Chat')}
                        </Text>
                        <Text style={styles.sessionPreview} numberOfLines={2}>
                          {s.preview || (isAr ? 'لا يوجد رسائل' : 'No messages')}
                        </Text>
                      </View>
                    </View>
                    <View style={styles.sessionMeta}>
                      <Text style={styles.sessionDate}>
                        {s.last_active ? new Date(s.last_active).toLocaleDateString() : ''}
                      </Text>
                      {s.message_count > 0 && (
                        <Text style={styles.sessionCount}>
                          {s.message_count} {isAr ? 'رسالة' : 'msgs'}
                        </Text>
                      )}
                    </View>
                  </TouchableOpacity>
                ))
              ) : (
                <View style={{ padding: 40, alignItems: 'center' }}>
                  <Feather name="message-circle" size={32} color={BORDER_COLOR} />
                  <Text style={{ color: MUTED, textAlign: 'center', marginTop: 12 }}>
                    {isAr ? 'لا توجد محادثات سابقة.\nابدأ محادثة جديدة!' : 'No previous chats.\nStart a new conversation!'}
                  </Text>
                </View>
              )}
            </ScrollView>
          </Animated.View>
        </View>
      </Modal>

      {/* ── Action Confirmation Pop-up ── */}
      <Modal visible={confirmModal.visible} animationType="fade" transparent>
        <View style={styles.confirmOverlay}>
          <View style={styles.confirmCard}>
            <View style={styles.confirmIcon}>
              <MaterialIcons
                name={
                  confirmModal.type === 'plan'
                    ? 'map'
                    : confirmModal.type === 'spots'
                      ? 'place'
                      : 'account-balance-wallet'
                }
                size={28}
                color={PRIMARY}
              />
            </View>
            <Text style={styles.confirmTitle}>
              {isAr
                ? 'هل تريد إضافة التعديلات لخطتك؟'
                : 'Would you like to sync this update to your plan?'}
            </Text>
            <Text style={styles.confirmSub}>
              {confirmModal.type === 'plan'
                ? (isAr ? 'سيتم تحديث جدولك السياحي' : 'Your travel itinerary will be updated')
                : confirmModal.type === 'spots'
                  ? (isAr ? 'سيتم حفظ الأماكن المقترحة في خطتك' : 'Recommended spots will be saved to your plan')
                  : (isAr ? 'سيتم تحديث تفاصيل ميزانيتك' : 'Your budget breakdown will be updated')}
            </Text>
            <View style={styles.confirmActions}>
              <TouchableOpacity
                style={styles.confirmBtnSecondary}
                onPress={() => setConfirmModal({ visible: false, type: 'plan', data: null })}
              >
                <Text style={styles.confirmBtnSecondaryTxt}>{isAr ? 'لاحقًا' : 'Later'}</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.confirmBtnPrimary} onPress={handleConfirmTrigger}>
                <Text style={styles.confirmBtnPrimaryTxt}>{isAr ? 'نعم، حدّث' : 'Yes, Sync'}</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: BG },

  header: {
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingVertical: 14,
    backgroundColor: 'rgba(255,255,255,0.96)',
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: 'rgba(0,0,0,0.07)',
  },
  headerLeft: { alignItems: 'center', gap: 8 },
  aiDot: {
    width: 28, height: 28, borderRadius: 14,
    backgroundColor: PRIMARY, alignItems: 'center', justifyContent: 'center',
  },
  headerTitle: { fontSize: 18, fontWeight: '800', color: TEXT, letterSpacing: -0.3 },

  // ── Header progress bar (requirements completion) ──
  headerProgress: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    paddingHorizontal: 20, paddingVertical: 6,
    backgroundColor: 'rgba(255,255,255,0.96)',
  },
  headerProgressBar: {
    flex: 1, height: 3, backgroundColor: BORDER_COLOR, borderRadius: 2, overflow: 'hidden',
  },
  headerProgressFill: {
    height: '100%', backgroundColor: PRIMARY, borderRadius: 2,
  },
  headerProgressTxt: {
    fontSize: 10, fontWeight: '600', color: MUTED, minWidth: 80, textAlign: 'right',
  },

  traceBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 5,
    backgroundColor: BG,
    paddingHorizontal: 10, paddingVertical: 6, borderRadius: RADIUS,
  },
  traceBtnTxt: { color: MUTED, fontWeight: '600', fontSize: 12 },

  scrollContent: { padding: 20, paddingBottom: 20 },

  emptyState: { paddingVertical: 32, alignItems: 'flex-start', gap: 10 },
  emptyIcon: {
    width: 56, height: 56, borderRadius: 18,
    backgroundColor: PRIMARY_LIGHT, alignItems: 'center', justifyContent: 'center', marginBottom: 4,
  },
  emptyTitle: { fontSize: 22, fontWeight: '800', color: TEXT, letterSpacing: -0.3 },
  emptySub: { fontSize: 14, color: MUTED, lineHeight: 22, maxWidth: 320 },

  userRow: { width: '100%' },
  userBubble: {
    maxWidth: '82%', backgroundColor: TEXT,
    paddingHorizontal: 18, paddingVertical: 12, borderRadius: 20,
    borderBottomRightRadius: 4,
  },
  userText: { fontSize: 15, color: '#fff', lineHeight: 22 },

  aiRow: { gap: 6 },
  aiMeta: { alignItems: 'center', gap: 6 },
  aiIcon: {
    width: 22, height: 22, borderRadius: 11,
    backgroundColor: PRIMARY, alignItems: 'center', justifyContent: 'center',
  },
  aiLabel: { fontSize: 12, fontWeight: '700', color: PRIMARY },
  aiBubble: {
    backgroundColor: SURFACE, borderRadius: 20, borderTopLeftRadius: 4,
    paddingHorizontal: 18, paddingVertical: 14,
    borderWidth: 1, borderColor: BORDER_COLOR,
    minHeight: 52, // keep bubble height stable while tokens stream in
  },
  // Fixed lineHeight + Android font-padding off => zero layout shift while
  // tokens append word-by-word in either RTL (Arabic) or LTR (English).
  aiText: {
    fontSize: 15,
    color: TEXT,
    lineHeight: 24,
    includeFontPadding: false,
  },

  statusRow: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 4 },
  typingDotsRow: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  typingDot: { width: 6, height: 6, borderRadius: 3, backgroundColor: PRIMARY },
  statusTxt: { color: MUTED, fontSize: 13, fontWeight: '500' },

  errBanner: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    backgroundColor: '#FFF1F0', borderRadius: 12,
    paddingHorizontal: 14, paddingVertical: 10, marginTop: 8,
  },
  errTxt: { color: ERROR, fontSize: 13, flex: 1 },

  guestBanner: {
    alignItems: 'center', gap: 8,
    marginHorizontal: 16, marginBottom: 8,
    paddingHorizontal: 12, paddingVertical: 10,
    backgroundColor: PRIMARY_LIGHT, borderRadius: 12,
  },
  guestTxt: { flex: 1, fontSize: 12, color: PRIMARY_DARK, fontWeight: '500' },
  guestSignInBtn: { paddingHorizontal: 12, paddingVertical: 6, backgroundColor: PRIMARY, borderRadius: RADIUS_PILL },
  guestSignInTxt: { color: '#fff', fontSize: 12, fontWeight: '700' },

  chipsContainer: { paddingBottom: 4 },
  chipsScroll: { paddingHorizontal: 16, gap: 8 },
  chip: {
    paddingHorizontal: 14, paddingVertical: 8,
    backgroundColor: SURFACE, borderRadius: 20,
    borderWidth: 1.5, borderColor: '#00A89640',
  },
  chipTxt: { fontSize: 13, fontWeight: '600', color: PRIMARY },

  inputArea: {
    padding: 12,
    paddingBottom: Platform.OS === 'ios' ? 28 : 12,
    backgroundColor: BG,
  },
  inputRow: {
    alignItems: 'center',
    backgroundColor: SURFACE,
    borderWidth: 1.5,
    borderColor: BORDER_COLOR,
    borderRadius: RADIUS_XL,
    paddingHorizontal: 8,
    paddingVertical: 6,
    gap: 6,
  },
  inputField: {
    flex: 1, paddingHorizontal: 8,
    fontSize: 15, maxHeight: 120, color: TEXT,
  },
  sendBtn: {
    width: 38, height: 38, backgroundColor: PRIMARY,
    borderRadius: 19, alignItems: 'center', justifyContent: 'center',
  },
  sendBtnDisabled: { opacity: 0.4 },

  // ── Media buttons ──
  mediaBtn: {
    width: 34, height: 34, borderRadius: 17,
    alignItems: 'center', justifyContent: 'center',
    backgroundColor: 'transparent',
  },
  mediaBtnActive: { backgroundColor: ERROR },

  // ── Pending attachment previews (above input) ──
  attachmentsRow: {
    flexDirection: 'row', gap: 8, paddingHorizontal: 4, paddingBottom: 6, flexWrap: 'wrap',
  },
  attachmentChip: {
    width: 52, height: 52, borderRadius: 12,
    backgroundColor: PRIMARY_LIGHT, alignItems: 'center', justifyContent: 'center',
    overflow: 'hidden',
  },
  attachThumb: { width: '100%', height: '100%' },
  attachRemove: {
    position: 'absolute', top: 2, right: 2,
    width: 16, height: 16, borderRadius: 8,
    backgroundColor: 'rgba(0,0,0,0.55)', alignItems: 'center', justifyContent: 'center',
  },

  // ── Message attachment thumbnails ──
  msgAttachmentsRow: {
    flexDirection: 'row', gap: 6, marginBottom: 6, flexWrap: 'wrap',
    alignSelf: 'flex-end',
  },
  msgAttachImg: { width: 120, height: 120 },
  msgAttachAudio: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    backgroundColor: PRIMARY_LIGHT, paddingHorizontal: 10, paddingVertical: 6,
    borderRadius: 12,
  },
  msgAttachAudioTxt: { fontSize: 12, color: PRIMARY, fontWeight: '600' },

  // ── Hamburger button ──
  hamburgerBtn: {
    width: 36, height: 36, borderRadius: 18,
    alignItems: 'center', justifyContent: 'center',
    backgroundColor: BG,
  },

  // ── Chat History Drawer ──
  drawerOverlay: {
    flex: 1, flexDirection: 'row',
  },
  drawerBackdrop: {
    flex: 1, backgroundColor: 'rgba(0,0,0,0.3)',
  },
  drawerPanel: {
    width: 300, backgroundColor: SURFACE,
    borderTopLeftRadius: RADIUS_XL, borderBottomLeftRadius: RADIUS_XL,
    ...Platform.select({ ios: {}, android: { elevation: 8 } }),
  },
  drawerHeader: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: 20, paddingVertical: 16,
    borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: BORDER_COLOR,
  },
  drawerTitle: { fontSize: 16, fontWeight: '700', color: TEXT },

  newChatBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
    marginHorizontal: 16, marginTop: 12,
    paddingVertical: 12, borderRadius: 12,
    backgroundColor: PRIMARY,
  },
  newChatTxt: { color: '#fff', fontSize: 14, fontWeight: '700' },

  // ── Requirements progress ──
  reqProgressContainer: {
    marginHorizontal: 16, marginTop: 12, gap: 4,
  },
  reqProgressRow: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
  },
  reqProgressLabel: { fontSize: 11, fontWeight: '600', color: MUTED },
  reqProgressPct: { fontSize: 11, fontWeight: '700', color: PRIMARY },
  reqProgressBar: {
    height: 4, backgroundColor: BORDER_COLOR, borderRadius: 2, overflow: 'hidden',
  },
  reqProgressFill: {
    height: '100%', backgroundColor: PRIMARY, borderRadius: 2,
  },

  // ── Session cards ──
  sessionCard: {
    backgroundColor: BG, borderRadius: RADIUS,
    padding: 12, gap: 8,
    borderWidth: 1, borderColor: BORDER_COLOR,
  },
  sessionCardActive: {
    borderColor: PRIMARY, backgroundColor: PRIMARY_LIGHT,
  },
  sessionCardTop: {
    flexDirection: 'row', alignItems: 'flex-start', gap: 10,
  },
  sessionIcon: {
    width: 28, height: 28, borderRadius: 14,
    backgroundColor: PRIMARY_LIGHT, alignItems: 'center', justifyContent: 'center',
    marginTop: 2,
  },
  sessionDest: {
    fontSize: 14, fontWeight: '700', color: TEXT,
  },
  sessionPreview: {
    fontSize: 12, color: MUTED, lineHeight: 18, marginTop: 2,
  },
  sessionMeta: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    paddingLeft: 38,
  },
  sessionDate: {
    fontSize: 11, color: MUTED,
  },
  sessionCount: {
    fontSize: 11, color: PRIMARY, fontWeight: '600',
  },

  // ── Confirmation Modal ──
  confirmOverlay: {
    flex: 1, backgroundColor: 'rgba(0,0,0,0.4)',
    alignItems: 'center', justifyContent: 'center', padding: 24,
  },
  confirmCard: {
    width: '100%', maxWidth: 340, backgroundColor: SURFACE,
    borderRadius: RADIUS_XL, padding: 28, alignItems: 'center', gap: 14,
    borderWidth: 1, borderColor: BORDER_COLOR,
  },
  confirmIcon: {
    width: 56, height: 56, borderRadius: 28,
    backgroundColor: PRIMARY_LIGHT, alignItems: 'center', justifyContent: 'center',
  },
  confirmTitle: {
    fontSize: 16, fontWeight: '700', color: TEXT, textAlign: 'center', lineHeight: 24,
  },
  confirmSub: {
    fontSize: 13, color: MUTED, textAlign: 'center', lineHeight: 20,
  },
  confirmActions: {
    flexDirection: 'row', gap: 12, marginTop: 8, width: '100%',
  },
  confirmBtnSecondary: {
    flex: 1, paddingVertical: 12, borderRadius: 12,
    backgroundColor: BG, alignItems: 'center',
    borderWidth: 1, borderColor: BORDER_COLOR,
  },
  confirmBtnSecondaryTxt: { fontSize: 14, fontWeight: '600', color: MUTED },
  confirmBtnPrimary: {
    flex: 1, paddingVertical: 12, borderRadius: 12,
    backgroundColor: PRIMARY, alignItems: 'center',
  },
  confirmBtnPrimaryTxt: { fontSize: 14, fontWeight: '700', color: '#fff' },

  // ── Structured question cards ──
  sqContainer: { gap: 14, marginTop: 8 },
  sqGroup: { gap: 8 },
  sqQuestion: { fontSize: 13, fontWeight: '600', color: TEXT, paddingHorizontal: 4 },
  sqOptionsRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  sqOption: {
    backgroundColor: SURFACE,
    borderRadius: 14,
    borderWidth: 1.5,
    borderColor: `${PRIMARY}30`,
    paddingHorizontal: 14,
    paddingVertical: 10,
    minWidth: 80,
    alignItems: 'center',
    gap: 2,
  },
  sqEmoji: { fontSize: 18 },
  sqOptionLabel: { fontSize: 13, fontWeight: '700', color: TEXT },
  sqOptionLabelSelected: { color: PRIMARY },
  sqOptionSelected: {
    borderColor: PRIMARY,
    backgroundColor: PRIMARY_LIGHT,
  },
  sqOptionDesc: { fontSize: 11, color: MUTED },
  sqConfirmBtn: {
    backgroundColor: PRIMARY,
    borderRadius: 12,
    paddingVertical: 10,
    paddingHorizontal: 20,
    alignSelf: 'flex-start',
    marginTop: 4,
  },
  sqConfirmTxt: { color: '#fff', fontSize: 13, fontWeight: '700' },

  // ── Loading skeletons ──
  skeletonContainer: { gap: 8, paddingVertical: 4 },
  skeletonLine: {
    height: 12,
    borderRadius: 6,
    backgroundColor: BORDER_COLOR,
    opacity: 0.6,
  },
});
