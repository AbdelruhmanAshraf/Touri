/**
 * TripMind Flat 2D Design Tokens — Phase 4
 *
 * Flat iOS 16+ minimal design language:
 *   - NO shadows anywhere. Depth is achieved via tonal background contrast.
 *   - BG (off-white) sits behind SURFACE (pure white) cards — that contrast
 *     IS the perceived elevation.
 *   - Hairline borders replace drop shadows on interactive elements.
 */

import { StyleSheet } from 'react-native';

// ── Surface tones ─────────────────────────────────────────────────────────────
/** Primary app background: off-white. All screens use this. */
export const BG = '#F2F2F7';

/** Interactive surface: cards, bubbles, inputs, modals. Pops on BG. */
export const SURFACE = '#FFFFFF';

/** Elevated surface tint (section headers, nav bars). Barely off-white. */
export const SURFACE_ALT = '#F5F5F7';

// ── Separator / border ────────────────────────────────────────────────────────
/** Hairline border — replaces ALL drop shadows. */
export const BORDER_COLOR = '#E5E5EA';
export const BORDER_WIDTH = StyleSheet.hairlineWidth;

/** Slightly heavier separator (1 px) for card outlines. */
export const BORDER_WIDTH_CARD = 1;

// ── Brand colours ─────────────────────────────────────────────────────────────
export const PRIMARY = '#00A896';
export const PRIMARY_DARK = '#028090';
export const PRIMARY_LIGHT = '#E6F7F5';

// ── Typography ────────────────────────────────────────────────────────────────
export const TEXT = '#1C1C1E';
export const TEXT_SECONDARY = '#3C3C43';
export const MUTED = '#8E8E93';
export const PLACEHOLDER = '#C7C7CC';

// ── Status colours ────────────────────────────────────────────────────────────
export const ERROR = '#FF3B30';
export const SUCCESS = '#34C759';
export const WARNING = '#FF9500';

// ── Radius tokens ─────────────────────────────────────────────────────────────
/** Global default — all cards, inputs, buttons. */
export const RADIUS = 16;

/** Larger pill containers (chips, pills). */
export const RADIUS_PILL = 999;

/** Smaller radius for icon containers and badges. */
export const RADIUS_SM = 10;

/** Extra-large for hero cards and sheets. */
export const RADIUS_XL = 24;

// ── Spacing ───────────────────────────────────────────────────────────────────
export const SPACING_XS = 4;
export const SPACING_SM = 8;
export const SPACING = 16;
export const SPACING_LG = 24;
export const SPACING_XL = 32;

// ── Tab bar ───────────────────────────────────────────────────────────────────
export const TAB_BAR_HEIGHT = 83;
export const TAB_BAR_BG = '#FFFFFF';

// ── Convenience flat card style (spread into StyleSheet) ──────────────────────
export const flatCard = {
  backgroundColor: SURFACE,
  borderRadius: RADIUS,
  borderWidth: BORDER_WIDTH_CARD,
  borderColor: BORDER_COLOR,
} as const;

export const flatInput = {
  backgroundColor: SURFACE,
  borderRadius: RADIUS,
  borderWidth: BORDER_WIDTH_CARD,
  borderColor: BORDER_COLOR,
} as const;
