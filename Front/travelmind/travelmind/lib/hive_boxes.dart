import 'package:hive/hive.dart';
import 'models/message_model.dart';
import 'models/user_model.dart';

class HiveBoxes {
  static Box<MessageModel> getMessagesBox() => Hive.box<MessageModel>('messages');
  static Box<UserModel> getUsersBox() => Hive.box<UserModel>('users');
}