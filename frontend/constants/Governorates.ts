/**
 * All 27 Egyptian governorates used across onboarding and profile.
 */

export const EGYPT_GOVERNORATES = [
  'Cairo (القاهرة)',
  'Alexandria (الإسكندرية)',
  'Giza (الجيزة)',
  'Qalyubia (القليوبية)',
  'Gharbia (الغربية)',
  'Dakahlia (الدقهلية)',
  'Sharqia (الشرقية)',
  'Kafr El-Sheikh (كفر الشيخ)',
  'Monufia (المنوفية)',
  'Beheira (البحيرة)',
  'Ismailia (الإسماعيلية)',
  'Suez (السويس)',
  'Port Said (بورسعيد)',
  'North Sinai (شمال سيناء)',
  'South Sinai (جنوب سيناء)',
  'Fayyum (الفيوم)',
  'Beni Suef (بني سويف)',
  'Al-Minya (المنيا)',
  'Asyut (أسيوط)',
  'Sohag (سوهاج)',
  'Qena (قنا)',
  'Luxor (الأقصر)',
  'Aswan (أسوان)',
  'Red Sea / Hurghada (البحر الأحمر)',
  'Matrouh (مطروح)',
  'New Valley (الوادي الجديد)',
  'Damietta (دمياط)',
];

export const COUNTRY_CODE: Record<string, string> = Object.fromEntries(
  EGYPT_GOVERNORATES.map((g) => [g, 'egypt']),
);
