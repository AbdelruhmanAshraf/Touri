import 'dart:convert';
import 'package:http/http.dart' as http;

class ApiService {
  // Static variable to allow updating the URL at runtime
  static String currentBaseUrl = 'https://44c1-34-169-231-106.ngrok-free.app';

  // Method to update the base URL
  static void updateBaseUrl(String newUrl) {
    currentBaseUrl = newUrl;
    print('🔄 API URL updated to: $currentBaseUrl');
  }

  /// Send user message with optional session tracking
  static Future<Map<String, dynamic>> sendUserMessage(
      String message, {
        Map<String, dynamic>? session,
      }) async {
    final url = Uri.parse('$currentBaseUrl/chat');
    try {
      final response = await http.post(
        url,
        headers: {
          'Content-Type': 'application/json',
          'ngrok-skip-browser-warning': 'true',
        },
        body: jsonEncode({
          'message': message,
          if (session != null) 'session': session,
        }),
      );

      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      } else {
        throw Exception("❌ Failed: ${response.statusCode}\n${response.body}");
      }
    } catch (e) {
      print('❌ Error sending message: $e');
      rethrow;
    }
  }

  /// Check if server is reachable
  static Future<bool> isServerReachable() async {
    try {
      final response = await http.get(
        Uri.parse('$currentBaseUrl/'),
        headers: {'ngrok-skip-browser-warning': 'true'},
      ).timeout(const Duration(seconds: 5));
      return response.statusCode == 200;
    } catch (e) {
      print('❌ Server unreachable: $e');
      return false;
    }
  }
}
