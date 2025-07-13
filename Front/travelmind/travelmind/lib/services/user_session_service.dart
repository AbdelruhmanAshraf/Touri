import 'package:hive/hive.dart';
import '../models/user_model.dart';

class UserSessionService {
  static const String _currentUserKey = 'current_user';
  static const String _settingsBoxName = 'settings';

  /// Initialize and migrate old data if needed
  static Future<void> initialize() async {
    try {
      if (!Hive.isBoxOpen(_settingsBoxName)) {
        print('Settings box not open during initialization');
        return;
      }

      final settingsBox = Hive.box(_settingsBoxName);

      // Check for old 'loggedInUser' key and migrate to new system
      final oldLoggedInUser = settingsBox.get('loggedInUser');
      if (oldLoggedInUser != null && oldLoggedInUser is String) {
        await setCurrentUser(oldLoggedInUser);
        await settingsBox.delete('loggedInUser'); // Remove old key
        print('Migrated old user session: $oldLoggedInUser');
      }
    } catch (e) {
      print('Error during user session initialization: $e');
    }
  }

  /// Get the currently logged-in user's username
  static String? getCurrentUserId() {
    try {
      if (!Hive.isBoxOpen(_settingsBoxName)) {
        print('Settings box is not open');
        return null;
      }
      final settingsBox = Hive.box(_settingsBoxName);
      final userId = settingsBox.get(_currentUserKey);
      return userId is String ? userId : null;
    } catch (e) {
      print('Error getting current user: $e');
      return null;
    }
  }

  /// Set the current logged-in user
  static Future<void> setCurrentUser(String userId) async {
    try {
      if (!Hive.isBoxOpen(_settingsBoxName)) {
        print('Settings box is not open, cannot set user');
        return;
      }
      final settingsBox = Hive.box(_settingsBoxName);
      await settingsBox.put(_currentUserKey, userId);
    } catch (e) {
      print('Error setting current user: $e');
    }
  }

  /// Clear the current user session (logout)
  static Future<void> clearCurrentUser() async {
    try {
      final settingsBox = Hive.box(_settingsBoxName);
      await settingsBox.delete(_currentUserKey);
    } catch (e) {
      print('Error clearing current user: $e');
    }
  }

  /// Check if a user is currently logged in
  static bool isUserLoggedIn() {
    return getCurrentUserId() != null;
  }

  /// Get the current user's UserModel from Hive
  static UserModel? getCurrentUser() {
    final userId = getCurrentUserId();
    if (userId == null) return null;

    try {
      final userBox = Hive.box<UserModel>('users');
      return userBox.values.firstWhere(
            (user) => user.username == userId,
        orElse: () => throw StateError('User not found'),
      );
    } catch (e) {
      print('Error getting current user model: $e');
      return null;
    }
  }

  /// Get user-specific box name for chats
  static String getUserChatBoxName(String userId) {
    return 'user_chats_${userId.replaceAll('@', '_').replaceAll('.', '_')}';
  }

  /// Get user-specific box name for messages
  static String getUserMessageBoxName(String userId) {
    return 'user_messages_${userId.replaceAll('@', '_').replaceAll('.', '_')}';
  }
}
