import 'package:hive/hive.dart';
import '../models/chat_log.dart';
import '../models/chat_model.dart';

class DataMigration {
  /// Clear old incompatible data to prevent type casting errors
  static Future<void> clearOldData() async {
    try {
      print('Starting data migration...');

      // Clear old chat logs that might not have userId field
      if (Hive.isBoxOpen('all_chats')) {
        final oldChatsBox = Hive.box<ChatLog>('all_chats');
        await oldChatsBox.clear();
        print('Cleared old chat logs');
      }

      // Clear old chats that might not have userId field
      if (Hive.isBoxOpen('chats')) {
        final oldChatsModelBox = Hive.box<ChatModel>('chats');
        await oldChatsModelBox.clear();
        print('Cleared old chat models');
      }

      print('Data migration completed');
    } catch (e) {
      print('Error during data migration: $e');
    }
  }

  /// Check if migration is needed
  static Future<bool> isMigrationNeeded() async {
    try {
      // Check if there's old data without userId
      if (Hive.isBoxOpen('all_chats')) {
        final oldChatsBox = Hive.box<ChatLog>('all_chats');
        if (oldChatsBox.isNotEmpty) {
          return true; // Old data exists
        }
      }

      if (Hive.isBoxOpen('chats')) {
        final oldChatsModelBox = Hive.box<ChatModel>('chats');
        if (oldChatsModelBox.isNotEmpty) {
          return true; // Old data exists
        }
      }

      return false;
    } catch (e) {
      print('Error checking migration status: $e');
      return true; // Assume migration is needed if we can't check
    }
  }

  /// Run migration if needed
  static Future<void> runMigrationIfNeeded() async {
    try {
      final needsMigration = await isMigrationNeeded();
      if (needsMigration) {
        print('Migration needed, clearing old data...');
        await clearOldData();
      } else {
        print('No migration needed');
      }
    } catch (e) {
      print('Error during migration check: $e');
      // Clear data anyway to be safe
      await clearOldData();
    }
  }
}
