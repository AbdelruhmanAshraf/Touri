// models/chat_model.dart
import 'package:hive/hive.dart';

part 'chat_model.g.dart';

@HiveType(typeId: 2) // 🔄 changed from 0 → 2
class ChatModel extends HiveObject {
  @HiveField(0)
  String title;

  @HiveField(1)
  DateTime createdAt;

  @HiveField(2)
  String userId; // Add user identification

  ChatModel(
      {required this.title,
        required this.createdAt,
        this.userId = 'unknown_user' // Default value for backward compatibility
      });
}
