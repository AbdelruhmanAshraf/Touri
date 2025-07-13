import 'package:hive/hive.dart';
part 'message_model.g.dart';

@HiveType(typeId: 5)
class MessageModel extends HiveObject {
  @HiveField(0)
  String sender;

  @HiveField(1)
  String content;

  @HiveField(2)
  DateTime timestamp;

  @HiveField(3)
  String owner;

  MessageModel({
    required this.sender,
    required this.content,
    required this.timestamp,
    required this.owner,
  });
}
