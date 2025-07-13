import 'package:hive_flutter/hive_flutter.dart';
import '../models/user_model.dart';
import '../models/message_model.dart';
import '../models/chat_log.dart';
import '../models/chat_model.dart';
import 'user_session_service.dart';

class HiveService {
  static Future<void> init() async {
    await Hive.initFlutter();
    Hive.registerAdapter(UserModelAdapter());
    Hive.registerAdapter(MessageModelAdapter());
    await Hive.openBox<UserModel>('users');
    await Hive.openBox<MessageModel>('messages');
  }

  static Box<UserModel> get userBox => Hive.box<UserModel>('users');
  static Box<MessageModel> get messageBox => Hive.box<MessageModel>('messages');

  /// Get user-specific chat logs
  static Future<Box<ChatLog>> getUserChatLogsBox(String userId) async {
    if (userId.isEmpty) {
      throw ArgumentError('userId cannot be empty');
    }

    try {
      final sanitizedUserId = userId
          .replaceAll('@', '_')
          .replaceAll('.', '_')
          .replaceAll(' ', '_')
          .replaceAll('/', '_')
          .replaceAll('\\', '_');
      final boxName = 'user_chat_logs_$sanitizedUserId';

      if (!Hive.isBoxOpen(boxName)) {
        return await Hive.openBox<ChatLog>(boxName);
      }
      return Hive.box<ChatLog>(boxName);
    } catch (e) {
      print('Error opening user chat logs box for user $userId: $e');
      rethrow;
    }
  }

  /// Get user-specific chats
  static Future<Box<ChatModel>> getUserChatsBox(String userId) async {
    final boxName =
        'user_chats_${userId.replaceAll('@', '_').replaceAll('.', '_')}';
    if (!Hive.isBoxOpen(boxName)) {
      return await Hive.openBox<ChatModel>(boxName);
    }
    return Hive.box<ChatModel>(boxName);
  }

  /// Get user-specific messages
  static Future<Box<MessageModel>> getUserMessagesBox(String userId) async {
    final boxName =
        'user_messages_${userId.replaceAll('@', '_').replaceAll('.', '_')}';
    if (!Hive.isBoxOpen(boxName)) {
      return await Hive.openBox<MessageModel>(boxName);
    }
    return Hive.box<MessageModel>(boxName);
  }

  /// Save a chat log for the current user
  static Future<void> saveChatLogForCurrentUser(ChatLog chatLog) async {
    final userId = UserSessionService.getCurrentUserId();
    if (userId == null || userId.isEmpty) {
      throw Exception('No user logged in');
    }

    try {
      final userChatLogsBox = await getUserChatLogsBox(userId);
      await userChatLogsBox.add(chatLog);
    } catch (e) {
      print('Error saving chat log: $e');
      rethrow;
    }
  }

  /// Get chat logs for the current user
  static Future<List<ChatLog>> getChatLogsForCurrentUser() async {
    final userId = UserSessionService.getCurrentUserId();
    if (userId == null || userId.isEmpty) {
      return [];
    }

    try {
      final userChatLogsBox = await getUserChatLogsBox(userId);
      return userChatLogsBox.values.toList().reversed.toList();
    } catch (e) {
      print('Error getting chat logs: $e');
      return [];
    }
  }
}
