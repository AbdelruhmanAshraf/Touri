/**
 * Legacy itinerary route — redirects to the Plan tab.
 *
 * This standalone route has been superseded by ``/(tabs)/plan.tsx``.
 * Any deep-links or navigations targeting ``/itinerary`` are seamlessly
 * forwarded to the unified Plan tab.
 */

import { useEffect } from 'react';
import { useRouter } from 'expo-router';

export default function ItineraryRedirect() {
  const router = useRouter();

  useEffect(() => {
    router.replace('/(tabs)/plan');
  }, [router]);

  return null;
}
