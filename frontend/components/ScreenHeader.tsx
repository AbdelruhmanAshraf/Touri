/**
 * ScreenHeader — unified flat header component.
 *
 * Usage on every screen that wants a custom header instead of the Expo Router
 * default (i.e., screens with headerShown: false):
 *
 *   <ScreenHeader title="Discover Egypt" />
 *   <ScreenHeader title="Chat" onBack={() => router.back()} />
 *   <ScreenHeader isModal onBack={() => router.back()} right={<SaveBtn />} />
 *
 * Design: flat 2D, no shadow — relies on the BG/SURFACE tonal contrast.
 */

import React from 'react';
import {
  Platform,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Feather } from '@expo/vector-icons';

import { BORDER_COLOR, MUTED, SURFACE, TEXT } from '@/theme/tokens';

export type ScreenHeaderProps = {
  /** Screen / modal title shown in the center. */
  title?: string;
  /**
   * When provided, renders a back / close button on the left.
   * For modals pass `isModal: true` to render "✕" instead of "‹".
   */
  onBack?: () => void;
  /** Use "✕" close icon instead of "‹" chevron (for full-screen modals). */
  isModal?: boolean;
  /** Optional right-side element (e.g. action button, avatar, indicator). */
  right?: React.ReactNode;
  /**
   * When true the header is transparent (no background / border).
   * Useful for screens with a hero image at the top.
   */
  transparent?: boolean;
};

export default function ScreenHeader({
  title,
  onBack,
  isModal = false,
  right,
  transparent = false,
}: ScreenHeaderProps) {
  const insets = useSafeAreaInsets();

  return (
    <View
      style={[
        styles.container,
        { paddingTop: insets.top + (Platform.OS === 'android' ? 4 : 0) },
        transparent && styles.transparent,
      ]}
    >
      {/* ── Left: back / close ── */}
      <View style={styles.side}>
        {onBack ? (
          <TouchableOpacity
            onPress={onBack}
            style={styles.iconBtn}
            hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
            accessibilityRole="button"
            accessibilityLabel={isModal ? 'Close' : 'Back'}
          >
            <Feather
              name={isModal ? 'x' : 'chevron-left'}
              size={24}
              color={TEXT}
            />
          </TouchableOpacity>
        ) : (
          <View style={styles.placeholder} />
        )}
      </View>

      {/* ── Center: title ── */}
      <View style={styles.center} pointerEvents="none">
        {title ? (
          <Text style={styles.title} numberOfLines={1}>
            {title}
          </Text>
        ) : null}
      </View>

      {/* ── Right: action slot ── */}
      <View style={[styles.side, styles.sideRight]}>
        {right ?? <View style={styles.placeholder} />}
      </View>
    </View>
  );
}

const ICON_BTN_SIZE = 36;

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: SURFACE,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: BORDER_COLOR,
    paddingHorizontal: 16,
    paddingBottom: 12,
    minHeight: 56,
  },
  transparent: {
    backgroundColor: 'transparent',
    borderBottomColor: 'transparent',
  },
  side: {
    width: ICON_BTN_SIZE + 8,
    alignItems: 'flex-start',
    justifyContent: 'center',
  },
  sideRight: {
    alignItems: 'flex-end',
  },
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  title: {
    fontSize: 17,
    fontWeight: '700',
    color: TEXT,
    letterSpacing: -0.2,
  },
  iconBtn: {
    width: ICON_BTN_SIZE,
    height: ICON_BTN_SIZE,
    borderRadius: ICON_BTN_SIZE / 2,
    backgroundColor: '#F2F2F7',
    alignItems: 'center',
    justifyContent: 'center',
  },
  placeholder: {
    width: ICON_BTN_SIZE,
    height: ICON_BTN_SIZE,
  },
});
