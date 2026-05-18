/**
 * TripMind Tab Navigator — Phase 4 (Native OS tabs)
 *
 * Replaces the custom glassmorphic floating bar with Expo Router's
 * production-grade native <Tabs>. Platform maps directly to iOS
 * UITabBarController / Android BottomNavigationView defaults.
 *
 * Routes (unchanged): index | itinerary | search | chat | profile
 */

import { Tabs } from 'expo-router';
import { Feather } from '@expo/vector-icons';
import { Platform, StyleSheet } from 'react-native';

import { BG, BORDER_COLOR, MUTED, PRIMARY, SURFACE } from '@/theme/tokens';

type FeatherName = React.ComponentProps<typeof Feather>['name'];

function tabIcon(name: FeatherName, focused: boolean) {
  return (
    <Feather
      name={name}
      size={22}
      color={focused ? PRIMARY : MUTED}
    />
  );
}

export default function TabLayout() {
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: PRIMARY,
        tabBarInactiveTintColor: MUTED,
        tabBarLabelStyle: styles.label,
        tabBarStyle: styles.tabBar,
        tabBarItemStyle: styles.item,
        // iOS: use native blur on iOS 15+ bar
        tabBarBackground: undefined,
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          tabBarLabel: 'Home',
          tabBarIcon: ({ focused }) => tabIcon('home', focused),
        }}
      />
      <Tabs.Screen
        name="itinerary"
        options={{
          tabBarLabel: 'Itinerary',
          tabBarIcon: ({ focused }) => tabIcon('map', focused),
        }}
      />
      <Tabs.Screen
        name="search"
        options={{
          tabBarLabel: 'Discover',
          tabBarIcon: ({ focused }) => tabIcon('search', focused),
        }}
      />
      <Tabs.Screen
        name="chat"
        options={{
          tabBarLabel: 'Chat',
          tabBarIcon: ({ focused }) => tabIcon('message-circle', focused),
        }}
      />
      <Tabs.Screen
        name="profile"
        options={{
          tabBarLabel: 'Profile',
          tabBarIcon: ({ focused }) => tabIcon('user', focused),
        }}
      />
    </Tabs>
  );
}

const styles = StyleSheet.create({
  tabBar: {
    backgroundColor: SURFACE,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: BORDER_COLOR,
    // Flat — no elevation / shadow
    elevation: 0,
    height: Platform.OS === 'ios' ? 83 : 64,
    paddingTop: 6,
  },
  label: {
    fontSize: 10,
    fontWeight: '600',
    marginBottom: Platform.OS === 'ios' ? 0 : 4,
  },
  item: {
    paddingTop: 4,
  },
});
