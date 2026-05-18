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
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { Image } from 'expo-image';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Feather, Ionicons, MaterialIcons } from '@expo/vector-icons';
import { useTranslation } from 'react-i18next';
import { useRouter } from 'expo-router';
import * as ImagePicker from 'expo-image-picker';
import * as DocumentPicker from 'expo-document-picker';
import * as FileSystem from 'expo-file-system/legacy';
import { Audio } from 'expo-av';

import { Colors } from '@/constants/Colors';
import { BG, SURFACE, BORDER_COLOR, PRIMARY, PRIMARY_DARK, PRIMARY_LIGHT, TEXT, MUTED, PLACEHOLDER, ERROR, RADIUS, RADIUS_XL, RADIUS_PILL } from '@/theme/tokens';
import AgentTracePanel from '@/components/AgentTracePanel';
import { GUEST_LIMITS, useAuth } from '@/hooks/useAuth';
import {
  api,
  type AgentStep,
  type ChatResponse,
  type MultimodalPart,
  getOrCreateSessionId,
  getOrCreateUserId,
  openChatStream,
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
  const recordingRef = useRef<Audio.Recording | null>(null);

  const userIdRef = useRef<string | null>(null);
  const sessionIdRef = useRef<string | null>(null);
  const scrollRef = useRef<ScrollView>(null);
  const chipsAnim = useRef(new Animated.Value(1)).current;

  useEffect(() => {
    (async () => {
      const [uid, sid] = await Promise.all([getOrCreateUserId(), getOrCreateSessionId()]);
      userIdRef.current = user?.uid ?? uid;
      sessionIdRef.current = sid;
    })();
  }, [user?.uid]);

  // Collapse chips when user is typing
  useEffect(() => {
    Animated.timing(chipsAnim, {
      toValue: input.length > 0 ? 0 : 1,
      duration: 180,
      useNativeDriver: true,
    }).start();
  }, [input]);

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

  // ── Audio recorder ────────────────────────────────────────────────────────
  const toggleRecording = async () => {
    if (isRecording) {
      // Stop and attach the audio
      try {
        await recordingRef.current?.stopAndUnloadAsync();
        const uri = recordingRef.current?.getURI();
        if (uri) {
          setPendingAttachments((prev) => [
            ...prev,
            { uri, mimeType: 'audio/m4a', name: 'voice.m4a' },
          ]);
        }
      } catch (e) { console.warn('[chat] stop recording error', e); }
      recordingRef.current = null;
      setIsRecording(false);
    } else {
      // Start recording
      try {
        const { status } = await Audio.requestPermissionsAsync();
        if (status !== 'granted') {
          Alert.alert('Permission required', 'Microphone access is needed to record voice.');
          return;
        }
        await Audio.setAudioModeAsync({ allowsRecordingIOS: true, playsInSilentModeIOS: true });
        const { recording } = await Audio.Recording.createAsync(
          Audio.RecordingOptionsPresets.HIGH_QUALITY,
        );
        recordingRef.current = recording;
        setIsRecording(true);
      } catch (e) { console.warn('[chat] start recording error', e); }
    }
  };

  const userMessageCount = turns.filter((m) => m.role === 'user').length;
  const guestLimitReached = isGuest && userMessageCount >= GUEST_LIMITS.maxChatMessagesPerSession;

  const send = async (overrideText?: string) => {
    const text = (overrideText ?? input).trim();
    // Allow sending with attachments only (no text), but never with neither.
    if ((!text && pendingAttachments.length === 0) || streaming) return;
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
    setStatusText(t('chat.thinking'));
    setErr(null);
    setTrace([]);

    setTimeout(() => scrollRef.current?.scrollToEnd({ animated: true }), 100);

    const appendToken = (token: string) => {
      setTurns((prev) => prev.map((m) => m.id === assistantTurnId ? { ...m, text: m.text + token } : m));
    };

    let finalSeen = false;

    const stream = openChatStream({
      onStatus: (s) => {
        if (s.phase === 'thinking') {
          setStatusText(t('chat.thinking'));
          setActiveAgent(null);
        }
        if (s.phase === 'streaming') {
          // Show the live agent name + status message from the graph
          const agentLabel = (s as any).agent || '';
          const statusMsg = (s as any).status_msg || '';
          setActiveAgent(agentLabel);
          setStatusText(statusMsg || agentLabel || t('chat.streaming'));
        }
      },
      onTrace: (step) => setTrace((prev) => [...prev, step]),
      onToken: appendToken,
      onFinal: async (final) => {
        finalSeen = true;
        setStatusText(null);
        setActiveAgent(null);
        setStreaming(false);

        const suggestions: string[] = final.suggestions ?? [];

        setTurns((prev) =>
          prev.map((m) =>
            m.id === assistantTurnId
              ? { ...m, text: final.message, agent: final.agent, suggestions }
              : m,
          ),
        );
        setActiveSuggestions(suggestions);

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
        setTimeout(() => scrollRef.current?.scrollToEnd({ animated: true }), 150);
      },
      onError: (msg) => {
        setErr(msg);
        setStreaming(false);
        setStatusText(null);
        stream.close();
      },
      onClose: () => { if (!finalSeen) setStreaming(false); },
    });

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
        ...(hasMultimodal ? { type: 'multimodal', parts: encoded } : {}),
      });
    } catch {
      // WebSocket unavailable — degrade to single-shot REST.
      try {
        const res: ChatResponse = await api.chat({
          user_id: uid,
          session_id: sid,
          message: text,
          language: isAr ? 'ar' : 'en',
          ...(hasMultimodal ? { type: 'multimodal', parts: encoded } : {}),
        });
        setTurns((prev) =>
          prev.map((m) =>
            m.id === assistantTurnId
              ? { ...m, text: res.message, agent: res.agent, suggestions: res.suggestions }
              : m,
          ),
        );
        setTrace(res.agent_trace || []);
        setActiveSuggestions(res.suggestions ?? []);
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
        setErr(e?.message ?? 'Connection error');
      } finally {
        setStreaming(false);
        setStatusText(null);
      }
    }
  };

  const handleSignIn = async () => { await signOut(); router.replace('/'); };

  return (
    <SafeAreaView style={styles.safeArea} edges={['top']}>
      {/* ── Header ── */}
      <View style={[styles.header, { flexDirection: isAr ? 'row-reverse' : 'row' }]}>
        <View style={[styles.headerLeft, { flexDirection: isAr ? 'row-reverse' : 'row' }]}>
          <View style={styles.aiDot}>
            <MaterialIcons name="smart-toy" size={14} color="#fff" />
          </View>
          <Text style={styles.headerTitle}>{t('appName')}</Text>
        </View>
        <TouchableOpacity
          onPress={() => setIsTraceVisible(true)}
          style={styles.traceBtn}
        >
          <MaterialIcons name="memory" size={16} color={Colors.primary} />
          <Text style={styles.traceBtnTxt}>{t('chat.trace')}</Text>
        </TouchableOpacity>
      </View>

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
                    <Text style={[styles.aiText, { textAlign: isAr ? 'right' : 'left' }]}>
                      {m.text || (streaming ? '…' : '')}
                    </Text>
                  </View>
                </View>
              ),
            )}

            {streaming && statusText && (
              <View style={[styles.statusRow, { justifyContent: isAr ? 'flex-end' : 'flex-start' }]}>
                <View style={styles.statusDot} />
                <Text style={styles.statusTxt}>
                  {activeAgent ? `[${activeAgent}] ${statusText}` : statusText}
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
    </SafeAreaView>
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
  },
  aiText: { fontSize: 15, color: TEXT, lineHeight: 24 },

  statusRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  statusDot: { width: 6, height: 6, borderRadius: 3, backgroundColor: PRIMARY },
  statusTxt: { color: MUTED, fontSize: 13, fontStyle: 'italic' },

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
    paddingBottom: Platform.OS === 'ios' ? 16 : 12,
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
});
