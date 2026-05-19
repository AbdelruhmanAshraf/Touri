/**
 * Module augmentation: expose the React Native-only `getReactNativePersistence`
 * export to TypeScript.
 *
 * The `firebase` meta-package's `exports."./auth"` field does NOT declare a
 * `react-native` condition, so TypeScript resolves `firebase/auth` to the
 * default `.d.ts` (which doesn't include `getReactNativePersistence`). At
 * runtime, however, Metro DOES match the `react-native` condition inside
 * `@firebase/auth`, so the function is available.
 *
 * This augmentation just teaches the type-checker about it.
 */

declare module 'firebase/auth' {
  import type { Persistence } from 'firebase/auth';
  export function getReactNativePersistence(storage: unknown): Persistence;
}

export {};
