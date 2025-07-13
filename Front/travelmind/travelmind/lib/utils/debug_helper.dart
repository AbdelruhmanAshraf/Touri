import '../services/user_session_service.dart';
import '../services/hive_service.dart';

class DebugHelper {
  /// Test user session functionality
  static Future<void> testUserSession() async {
    try {
      print('=== Testing User Session ===');

      // Test getting current user (should be null initially)
      final currentUser = UserSessionService.getCurrentUserId();
      print('Current user: $currentUser');

      // Test setting a user
      await UserSessionService.setCurrentUser('test@example.com');
      print('Set user: test@example.com');

      // Test getting current user again
      final newCurrentUser = UserSessionService.getCurrentUserId();
      print('Current user after setting: $newCurrentUser');

      // Test if user is logged in
      final isLoggedIn = UserSessionService.isUserLoggedIn();
      print('Is user logged in: $isLoggedIn');

      print('=== User Session Test Complete ===');
    } catch (e) {
      print('Error in user session test: $e');
    }
  }

  /// Test chat storage functionality
  static Future<void> testChatStorage() async {
    try {
      print('=== Testing Chat Storage ===');

      // Ensure a user is set
      await UserSessionService.setCurrentUser('test@example.com');

      // Test getting chat logs (should be empty initially)
      final chatLogs = await HiveService.getChatLogsForCurrentUser();
      print('Current chat logs count: ${chatLogs.length}');

      print('=== Chat Storage Test Complete ===');
    } catch (e) {
      print('Error in chat storage test: $e');
    }
  }

  /// Run all tests
  static Future<void> runAllTests() async {
    await testUserSession();
    await testChatStorage();
  }
}
