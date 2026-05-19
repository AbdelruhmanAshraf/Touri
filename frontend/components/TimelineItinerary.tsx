import React from 'react';
import { View, Text, StyleSheet, ScrollView } from 'react-native';

// Types matching Backend Phase 16 schemas
interface Activity {
    title: string;
    location: string;
    duration_hours: number;
}

interface DayPlan {
    day_number: number;
    morning_activities: Activity[];
    afternoon_activities: Activity[];
    evening_activities: Activity[];
}

interface TimelineItineraryProps {
    days: DayPlan[];
}

export const TimelineItinerary: React.FC<TimelineItineraryProps> = ({ days }) => {
    return (
        <ScrollView style={styles.container}>
            {days.map((day) => (
                <View key={day.day_number} style={styles.dayCard}>
                    <Text style={styles.dayHeader}>Day {day.day_number}</Text>
                    
                    <View style={styles.timeSection}>
                        <View style={styles.timelineDot} />
                        <Text style={styles.sectionHeader}>Morning</Text>
                        {day.morning_activities.map((act, idx) => (
                            <Text key={`morning-${idx}`} style={styles.activityText}>
                                • {act.title} ({act.duration_hours}h) - {act.location}
                            </Text>
                        ))}
                    </View>

                    <View style={styles.timeSection}>
                        <View style={styles.timelineDot} />
                        <Text style={styles.sectionHeader}>Afternoon</Text>
                        {day.afternoon_activities.map((act, idx) => (
                            <Text key={`afternoon-${idx}`} style={styles.activityText}>
                                • {act.title} ({act.duration_hours}h) - {act.location}
                            </Text>
                        ))}
                    </View>

                    <View style={styles.timeSection}>
                        <View style={styles.timelineDot} />
                        <Text style={styles.sectionHeader}>Evening</Text>
                        {day.evening_activities.map((act, idx) => (
                            <Text key={`evening-${idx}`} style={styles.activityText}>
                                • {act.title} ({act.duration_hours}h) - {act.location}
                            </Text>
                        ))}
                    </View>
                </View>
            ))}
        </ScrollView>
    );
};

const styles = StyleSheet.create({
    container: { flex: 1, padding: 16, backgroundColor: '#FFFFFF' },
    dayCard: { 
        backgroundColor: '#F8FAFC', 
        borderRadius: 12, 
        padding: 16, 
        marginBottom: 16,
        borderWidth: 1,
        borderColor: '#E2E8F0',
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 2 },
        shadowOpacity: 0.1,
        shadowRadius: 4,
        elevation: 2,
    },
    dayHeader: { fontSize: 22, fontWeight: '700', marginBottom: 16, color: '#1E293B' },
    timeSection: { marginBottom: 16, paddingLeft: 12, borderLeftWidth: 2, borderLeftColor: '#CBD5E1', position: 'relative' },
    timelineDot: {
        position: 'absolute',
        left: -7,
        top: 2,
        width: 12,
        height: 12,
        borderRadius: 6,
        backgroundColor: '#3B82F6',
    },
    sectionHeader: { fontSize: 16, fontWeight: '600', color: '#475569', marginBottom: 8 },
    activityText: { fontSize: 14, color: '#334155', marginLeft: 8, marginBottom: 4 },
});
