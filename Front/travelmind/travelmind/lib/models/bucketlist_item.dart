import 'package:hive/hive.dart';
part 'bucketlist_item.g.dart';

@HiveType(typeId: 1)
class BucketlistItem {
  @HiveField(0)
  final String title;

  BucketlistItem({required this.title});
}