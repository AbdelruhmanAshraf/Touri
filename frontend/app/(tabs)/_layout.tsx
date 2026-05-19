/**
 * Touri Tab Navigator — Phase 7 (i18n-aware native tabs)
 *
 * Uses ``react-i18next`` for bilingual tab labels so Arabic users see
 * "الرئيسية | الخطة | اكتشف | المحادثة | الملف" natively.
 *
 * Routes: index | plan | search | chat | profile
 */

import { Tabs } from 'expo-router';
import { Feather } from '@expo/vector-icons';
import { Platform, StyleSheet } from 'react-native';
import { useTranslation } from 'react-i18next';

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
  const { t } = useTranslation();

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
          tabBarLabel: t('tabs.home'),
          tabBarIcon: ({ focused }) => tabIcon('home', focused),
        }}
      />
      <Tabs.Screen
        name="plan"
        options={{
          tabBarLabel: t('tabs.plan'),
          tabBarIcon: ({ focused }) => tabIcon('map', focused),
        }}
      />
      <Tabs.Screen
        name="search"
        options={{
          tabBarLabel: t('tabs.discover'),
          tabBarIcon: ({ focused }) => tabIcon('search', focused),
        }}
      />
      <Tabs.Screen
        name="chat"
        options={{
          tabBarLabel: t('tabs.chat'),
          tabBarIcon: ({ focused }) => tabIcon('message-circle', focused),
        }}
      />
      <Tabs.Screen
        name="profile"
        options={{
          tabBarLabel: t('tabs.profile'),
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
    elevation: 0,
    height: Platform.OS === 'ios' ? 88 : 64,
    paddingTop: 6,
    paddingBottom: Platform.OS === 'ios' ? 28 : 0,
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
