import 'package:hive/hive.dart';

part 'chat_log.g.dart';

@HiveType(typeId: 3)
class ChatLog extends HiveObject {
  @HiveField(0)
  final String title;

  @HiveField(1)
  final String message;

  @HiveField(2)
  final DateTime createdAt;

  @HiveField(3)
  final String userId; // Add user identification

  ChatLog({
    required this.title,
    required this.message,
    required this.createdAt,
    this.userId = 'unknown_user', // Default value for backward compatibility
  });
}
