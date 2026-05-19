/**
 * NotionAvatar — Notion-style B&W minimal illustration avatar.
 *
 * Clean black-and-white illustrations with filled hair, simple dot eyes,
 * and distinctive silhouettes. Deterministic per user ID so the same
 * user always sees the same face.
 *
 * Usage:
 *   <NotionAvatar id={user?.uid ?? user?.email ?? 'guest'} size={64} />
 */

import React, { useMemo } from 'react';
import { View, StyleSheet, ViewStyle } from 'react-native';
import Svg, { Circle, Ellipse, Path, Rect } from 'react-native-svg';

import { BORDER_COLOR, SURFACE, TEXT } from '@/theme/tokens';

export type NotionAvatarProps = {
  id?: string | null;
  gender?: 'male' | 'female' | 'unspecified';
  size?: number;
  stroke?: string;
  background?: string;
  style?: ViewStyle;
};

type Variant = {
  hair: string;
  hairFill?: boolean;
  brows: string;
  eyes: string;
  mouth: string;
  extras?: string;
  extrasFill?: boolean;
  neck?: string;
};

// Male variants — filled hair, distinctive styles
const MALE_VARIANTS: Variant[] = [
  {
    // Short cropped hair
    hair: 'M28,44 Q28,22 50,20 Q72,22 72,44 Q68,34 58,30 Q50,28 42,30 Q32,34 28,44 Z',
    hairFill: true,
    brows: 'M39,48 L45,47 M55,47 L61,48',
    eyes: 'M42,53 a2,2 0 1,0 0.01,0 M58,53 a2,2 0 1,0 0.01,0',
    mouth: 'M44,65 Q50,68 56,65',
  },
  {
    // Side-swept hair with glasses
    hair: 'M28,42 Q26,20 50,18 Q74,20 72,42 Q68,30 56,26 Q44,24 34,28 Q28,32 28,42 Z',
    hairFill: true,
    brows: 'M39,46 L45,46 M55,46 L61,46',
    eyes: 'M42,52 a2,2 0 1,0 0.01,0 M58,52 a2,2 0 1,0 0.01,0',
    mouth: 'M44,65 Q50,68 56,65',
    extras: 'M37,52 a6,5 0 1,0 12,0 a6,5 0 1,0 -12,0 M51,52 a6,5 0 1,0 12,0 a6,5 0 1,0 -12,0 M49,52 L51,52',
  },
  {
    // Curly top
    hair: 'M30,40 Q26,18 42,16 Q48,12 54,14 Q62,12 68,18 Q76,26 72,40 Q68,30 58,28 Q50,26 42,28 Q32,30 30,40 Z',
    hairFill: true,
    brows: 'M40,48 Q43,46 46,48 M54,48 Q57,46 60,48',
    eyes: 'M42,54 a2,2 0 1,0 0.01,0 M58,54 a2,2 0 1,0 0.01,0',
    mouth: 'M45,66 Q50,69 55,66',
  },
  {
    // Beanie
    hair: 'M30,38 Q30,16 50,16 Q70,16 70,38 L30,38 Z',
    hairFill: true,
    brows: 'M40,48 L46,47 M54,47 L60,48',
    eyes: 'M42,54 a2,2 0 1,0 0.01,0 M58,54 a2,2 0 1,0 0.01,0',
    mouth: 'M44,66 Q50,68 56,66',
    extras: 'M28,38 L72,38 M48,16 Q50,10 52,16',
  },
  {
    // Buzz cut
    hair: 'M30,44 Q30,26 50,24 Q70,26 70,44 Q66,36 58,34 Q50,32 42,34 Q34,36 30,44 Z',
    hairFill: true,
    brows: 'M39,48 Q42,46 45,48 M55,48 Q58,46 61,48',
    eyes: 'M42,53 a1.8,1.8 0 1,0 0.01,0 M58,53 a1.8,1.8 0 1,0 0.01,0',
    mouth: 'M46,66 L54,66',
  },
];

// Female variants — filled hair, distinctive styles
const FEMALE_VARIANTS: Variant[] = [
  {
    // Bob cut
    hair: 'M26,44 Q24,18 50,16 Q76,18 74,44 Q74,56 70,64 L68,44 Q68,28 50,26 Q32,28 32,44 L30,64 Q26,56 26,44 Z',
    hairFill: true,
    brows: 'M40,46 Q43,44 46,46 M54,46 Q57,44 60,46',
    eyes: 'M42,52 a2,2 0 1,0 0.01,0 M58,52 a2,2 0 1,0 0.01,0',
    mouth: 'M44,64 Q50,68 56,64',
  },
  {
    // Long straight hair
    hair: 'M28,42 Q26,18 50,16 Q74,18 72,42 Q72,58 68,74 Q66,42 66,32 Q58,24 50,24 Q42,24 34,32 Q34,42 34,74 Q28,58 28,42 Z',
    hairFill: true,
    brows: 'M40,46 L46,45 M54,45 L60,46',
    eyes: 'M42,52 a2,2 0 1,0 0.01,0 M58,52 a2,2 0 1,0 0.01,0',
    mouth: 'M44,64 Q50,67 56,64',
  },
  {
    // Ponytail
    hair: 'M30,42 Q28,20 50,18 Q72,20 70,42 Q66,32 58,28 Q50,26 42,28 Q34,32 30,42 Z M68,30 Q78,28 80,38 Q82,48 76,52',
    hairFill: true,
    brows: 'M40,48 Q43,46 46,48 M54,48 Q57,46 60,48',
    eyes: 'M42,54 a2,2 0 1,0 0.01,0 M58,54 a2,2 0 1,0 0.01,0',
    mouth: 'M44,66 Q50,69 56,66',
  },
  {
    // Curly/voluminous hair
    hair: 'M24,42 Q20,16 38,14 Q44,10 52,14 Q60,10 66,16 Q80,20 76,42 Q78,36 72,30 Q66,24 58,26 Q50,22 42,26 Q34,24 30,30 Q24,36 24,42 Z',
    hairFill: true,
    brows: 'M40,48 Q43,46 46,48 M54,48 Q57,46 60,48',
    eyes: 'M42,54 a2,2 0 1,0 0.01,0 M58,54 a2,2 0 1,0 0.01,0',
    mouth: 'M44,66 Q50,70 56,66',
  },
  {
    // Bun updo
    hair: 'M30,42 Q28,22 50,20 Q72,22 70,42 Q66,32 58,28 Q50,26 42,28 Q34,32 30,42 Z',
    hairFill: true,
    brows: 'M40,46 Q43,44 46,46 M54,46 Q57,44 60,46',
    eyes: 'M42,52 a2,2 0 1,0 0.01,0 M58,52 a2,2 0 1,0 0.01,0',
    mouth: 'M44,64 Q50,67 56,64',
    extras: 'M42,16 Q44,6 54,8 Q62,10 60,18 Q56,12 48,12 Q44,14 42,16 Z',
    extrasFill: true,
  },
];

const VARIANTS = [...MALE_VARIANTS, ...FEMALE_VARIANTS];

function hashString(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) {
    h = (h * 31 + s.charCodeAt(i)) | 0;
  }
  return Math.abs(h);
}

export default function NotionAvatar({
  id,
  gender,
  size = 64,
  stroke = TEXT,
  background = SURFACE,
  style,
}: NotionAvatarProps) {
  const variant = useMemo(() => {
    const list = gender === 'male' ? MALE_VARIANTS : gender === 'female' ? FEMALE_VARIANTS : VARIANTS;
    const idx = hashString(id || 'guest') % list.length;
    return list[idx];
  }, [id, gender]);

  const sw = 1.8;

  return (
    <View
      style={[
        styles.shell,
        { width: size, height: size, borderRadius: size / 2, backgroundColor: background },
        style,
      ]}
    >
      <Svg width={size} height={size} viewBox="0 0 100 100">
        {/* Head shape */}
        <Ellipse
          cx="50"
          cy="54"
          rx="22"
          ry="24"
          fill={background}
          stroke={stroke}
          strokeWidth={sw}
        />
        {/* Hair */}
        <Path
          d={variant.hair}
          fill={variant.hairFill ? stroke : 'none'}
          stroke={stroke}
          strokeWidth={sw}
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        {/* Brows */}
        <Path d={variant.brows} fill="none" stroke={stroke} strokeWidth={1.4} strokeLinecap="round" />
        {/* Eyes — filled dots for Notion style */}
        <Path d={variant.eyes} fill={stroke} stroke={stroke} strokeWidth={1.2} strokeLinecap="round" />
        {/* Mouth */}
        <Path d={variant.mouth} fill="none" stroke={stroke} strokeWidth={1.4} strokeLinecap="round" />
        {/* Extras (glasses, accessories) */}
        {variant.extras ? (
          <Path
            d={variant.extras}
            fill={variant.extrasFill ? stroke : 'none'}
            stroke={stroke}
            strokeWidth={1.4}
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        ) : null}
        {/* Neck & shoulders */}
        <Path
          d="M44,76 L44,82 Q44,84 42,84 L22,90 M56,76 L56,82 Q56,84 58,84 L78,90"
          fill="none"
          stroke={stroke}
          strokeWidth={sw}
          strokeLinecap="round"
        />
      </Svg>
    </View>
  );
}

const styles = StyleSheet.create({
  shell: {
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1.5,
    borderColor: BORDER_COLOR,
    overflow: 'hidden',
  },
});
