import { Tabs } from 'expo-router';
import { Ionicons, Feather } from '@expo/vector-icons';
import { BlurView } from 'expo-blur';
import { View, StyleSheet, Platform, Text, TouchableOpacity } from 'react-native';
import { BottomTabBarProps } from '@react-navigation/bottom-tabs';

function CustomTabBar({ state, descriptors, navigation }: BottomTabBarProps) {
  // We want to group routes:
  // Left Pill: index (Home), journal (Itinerary), chat (Chat), profile (Profile)
  // Right Circle: search (Search)
  const leftRoutes = state.routes.filter(r => r.name !== 'search');
  const searchRoute = state.routes.find(r => r.name === 'search');

  const renderTab = (route: any, isSearch: boolean) => {
    const { options } = descriptors[route.key];
    const isFocused = state.index === state.routes.findIndex(r => r.name === route.name);

    const onPress = () => {
      const event = navigation.emit({
        type: 'tabPress',
        target: route.key,
        canPreventDefault: true,
      });

      if (!isFocused && !event.defaultPrevented) {
        navigation.navigate(route.name);
      }
    };

    const color = isFocused ? '#1C1C1E' : '#8E8E93';

    let icon = null;
    if (route.name === 'index') icon = <Feather name="home" size={22} color={color} />;
    if (route.name === 'journal') icon = <Feather name="map" size={22} color={color} />;
    if (route.name === 'search') icon = <Feather name="search" size={22} color={color} />;
    if (route.name === 'chat') {
      icon = (
        <View>
          <Feather name="message-circle" size={22} color={color} />
          {/* Notification Badge */}
          <View style={[styles.badge, isSearch && { borderColor: '#fff' }]}>
            <Text style={styles.badgeText}>3</Text>
          </View>
        </View>
      );
    }
    if (route.name === 'profile') icon = <Feather name="user" size={22} color={color} />;

    const label = typeof options.tabBarLabel === 'string' 
      ? options.tabBarLabel 
      : options.title !== undefined ? options.title : route.name;

    return (
      <TouchableOpacity
        key={route.key}
        accessibilityRole="button"
        accessibilityState={isFocused ? { selected: true } : {}}
        accessibilityLabel={options.tabBarAccessibilityLabel}
        onPress={onPress}
        style={isSearch ? styles.searchTabButton : styles.tabButton}
      >
        {icon}
        {!isSearch && <Text style={[styles.tabLabel, { color }]}>{label}</Text>}
      </TouchableOpacity>
    );
  };

  return (
    <View style={styles.container}>
      {/* Left Partition (Pill) */}
      <View style={[styles.leftPill, styles.shadow]}>
        {Platform.OS === 'ios' && (
          <BlurView tint="light" intensity={100} style={StyleSheet.absoluteFill} />
        )}
        <View style={styles.leftPillContent}>
          {leftRoutes.map(r => renderTab(r, false))}
        </View>
      </View>

      {/* Right Partition (Circle) */}
      <View style={[styles.rightCircle, styles.shadow]}>
        {Platform.OS === 'ios' && (
          <BlurView tint="light" intensity={100} style={StyleSheet.absoluteFill} />
        )}
        {searchRoute && renderTab(searchRoute, true)}
      </View>
    </View>
  );
}

export default function TabLayout() {
  return (
    <Tabs
      tabBar={props => <CustomTabBar {...props} />}
      screenOptions={{
        headerShown: false,
      }}
    >
      <Tabs.Screen name="index" options={{ tabBarLabel: 'Home' }} />
      <Tabs.Screen name="journal" options={{ tabBarLabel: 'Itinerary' }} />
      <Tabs.Screen name="search" options={{ tabBarLabel: 'Search' }} />
      <Tabs.Screen name="chat" options={{ tabBarLabel: 'Chat' }} />
      <Tabs.Screen name="profile" options={{ tabBarLabel: 'Profile' }} />
    </Tabs>
  );
}

const styles = StyleSheet.create({
  container: {
    position: 'absolute',
    bottom: 30,
    left: 16,
    right: 16,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    height: 64,
  },
  leftPill: {
    flex: 1,
    height: '100%',
    borderRadius: 32,
    marginRight: 12,
    backgroundColor: Platform.OS === 'ios' ? 'rgba(255, 255, 255, 0.7)' : '#FFFFFF',
    overflow: 'hidden',
  },
  leftPillContent: {
    flex: 1,
    flexDirection: 'row',
    justifyContent: 'space-evenly',
    alignItems: 'center',
  },
  rightCircle: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: Platform.OS === 'ios' ? 'rgba(255, 255, 255, 0.7)' : '#FFFFFF',
    overflow: 'hidden',
    alignItems: 'center',
    justifyContent: 'center',
  },
  tabButton: {
    alignItems: 'center',
    justifyContent: 'center',
    flex: 1,
  },
  searchTabButton: {
    alignItems: 'center',
    justifyContent: 'center',
    width: '100%',
    height: '100%',
  },
  tabLabel: {
    fontSize: 10,
    fontWeight: '700',
    marginTop: 4,
  },
  shadow: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.12,
    shadowRadius: 16,
    elevation: 10,
  },
  badge: {
    position: 'absolute',
    top: -6,
    right: -8,
    backgroundColor: '#FF3B30',
    borderRadius: 10,
    width: 16,
    height: 16,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1.5,
    borderColor: '#FFFFFF',
  },
  badgeText: {
    color: '#FFF',
    fontSize: 9,
    fontWeight: 'bold',
  }
});
