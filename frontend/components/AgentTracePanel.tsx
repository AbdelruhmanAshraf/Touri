/**
 * Bottom-sheet that mirrors the multi-agent ``agent_trace`` payload streamed
 * by the FastAPI WebSocket. Each row is one node hop (Router, Travel Planner,
 * Budget Specialist, Local Concierge) with its tool, reasoning and result.
 */

import React, { useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  Animated,
  Dimensions,
  TouchableOpacity,
} from 'react-native';
import { BlurView } from 'expo-blur';
import { Feather, MaterialIcons } from '@expo/vector-icons';
import { useTranslation } from 'react-i18next';

import { Colors } from '@/constants/Colors';
import type { AgentStep } from '@/services/api';

const { height } = Dimensions.get('window');

type Props = {
  isVisible: boolean;
  onClose: () => void;
  trace: AgentStep[];
};

export default function AgentTracePanel({ isVisible, onClose, trace }: Props) {
  const { t, i18n } = useTranslation();
  const isAr = i18n.language === 'ar';
  const writingDirection = isAr ? 'rtl' : 'ltr';
  const translateY = React.useRef(new Animated.Value(height)).current;

  useEffect(() => {
    Animated.spring(translateY, {
      toValue: isVisible ? height * 0.25 : height,
      useNativeDriver: true,
      bounciness: 4,
      speed: 12,
    }).start();
  }, [isVisible]);

  return (
    <Animated.View
      style={[styles.container, { transform: [{ translateY }] }]}
      pointerEvents={isVisible ? 'auto' : 'none'}
    >
      <BlurView intensity={90} tint="light" style={StyleSheet.absoluteFill} />

      <View style={styles.header}>
        <View style={styles.handle} />
        <View
          style={[styles.headerRow, { flexDirection: isAr ? 'row-reverse' : 'row' }]}
        >
          <View style={[styles.headerTitleRow, { flexDirection: isAr ? 'row-reverse' : 'row' }]}>
            <MaterialIcons name="memory" size={20} color={Colors.primary} />
            <Text style={styles.title}>{t('agentTrace.title')}</Text>
          </View>
          <TouchableOpacity onPress={onClose}>
            <Feather name="x" size={22} color={Colors.onSurfaceVariant} />
          </TouchableOpacity>
        </View>
      </View>

      <ScrollView contentContainerStyle={styles.scrollContent}>
        {trace.length === 0 ? (
          <Text style={[styles.empty, { writingDirection }]}>{t('agentTrace.empty')}</Text>
        ) : (
          trace.map((step, idx) => (
            <View key={idx} style={styles.traceStep}>
              {idx < trace.length - 1 && <View style={styles.timelineLine} />}
              <View style={styles.nodeIcon}>
                <Feather name="check" size={12} color="#fff" />
              </View>
              <View style={[styles.stepContent, { alignItems: isAr ? 'flex-end' : 'flex-start' }]}>
                <Text style={[styles.agentName, { writingDirection }]}>{step.agent}</Text>
                <Text style={[styles.actionText, { writingDirection }]}>{step.action}</Text>

                <View style={styles.metadataBox}>
                  {step.tool && (
                    <Text style={[styles.metaText, { writingDirection }]}>
                      🔧 {t('agentTrace.tool')}: {step.tool}
                    </Text>
                  )}
                  {step.reasoning && (
                    <Text style={[styles.metaText, { writingDirection }]}>
                      🧠 {t('agentTrace.reasoning')}: {step.reasoning}
                    </Text>
                  )}
                  {step.result && (
                    <Text style={[styles.metaText, { writingDirection }]}>
                      ✅ {t('agentTrace.result')}: {step.result}
                    </Text>
                  )}
                </View>
              </View>
            </View>
          ))
        )}
      </ScrollView>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  container: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    zIndex: 100,
    borderTopLeftRadius: 28,
    borderTopRightRadius: 28,
    overflow: 'hidden',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: -10 },
    shadowOpacity: 0.1,
    shadowRadius: 20,
    elevation: 20,
  },
  header: { padding: 16 },
  handle: {
    alignSelf: 'center',
    width: 40,
    height: 4,
    backgroundColor: '#cbd5e1',
    borderRadius: 2,
    marginBottom: 12,
  },
  headerRow: { justifyContent: 'space-between', alignItems: 'center' },
  headerTitleRow: { alignItems: 'center', gap: 8 },
  title: { fontSize: 18, fontWeight: '700', color: Colors.onSurface },
  scrollContent: { padding: 20, paddingBottom: height * 0.3 },
  empty: { color: Colors.onSurfaceVariant, fontSize: 14, marginTop: 12 },
  traceStep: { flexDirection: 'row', marginBottom: 18, position: 'relative' },
  timelineLine: {
    position: 'absolute',
    left: 11,
    top: 22,
    bottom: -22,
    width: 2,
    backgroundColor: '#e2e8f0',
  },
  nodeIcon: {
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: Colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  stepContent: { flex: 1 },
  agentName: { fontSize: 15, fontWeight: '700', color: Colors.onSurface, marginBottom: 2 },
  actionText: { fontSize: 13, color: Colors.onSurfaceVariant, marginBottom: 8 },
  metadataBox: {
    backgroundColor: 'rgba(255,255,255,0.7)',
    padding: 12,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: Colors.outlineVariant,
    gap: 4,
  },
  metaText: { fontSize: 12, color: Colors.onSurfaceVariant, lineHeight: 18 },
});
