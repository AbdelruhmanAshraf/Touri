import 'package:hive/hive.dart';

part 'favorite_chats.g.dart';

@HiveType(typeId: 4)
class FavoriteChat {
  @HiveField(0)
  final String title;

  @HiveField(1)
  final String message;

  @HiveField(2)
  final DateTime createdAt;

  FavoriteChat({
    required this.title,
    required this.message,
    required this.createdAt,
  });
}

