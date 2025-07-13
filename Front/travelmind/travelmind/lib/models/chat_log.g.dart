// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'chat_log.dart';

// **************************************************************************
// TypeAdapterGenerator
// **************************************************************************

class ChatLogAdapter extends TypeAdapter<ChatLog> {
  @override
  final int typeId = 3;

  @override
  ChatLog read(BinaryReader reader) {
    final numOfFields = reader.readByte();
    final fields = <int, dynamic>{
      for (int i = 0; i < numOfFields; i++) reader.readByte(): reader.read(),
    };
    return ChatLog(
      title: fields[0] as String? ?? 'Unknown Title',
      message: fields[1] as String? ?? 'Unknown Message',
      createdAt: fields[2] as DateTime? ?? DateTime.now(),
      userId: fields[3] as String? ?? 'unknown_user',
    );
  }

  @override
  void write(BinaryWriter writer, ChatLog obj) {
    writer
      ..writeByte(4)
      ..writeByte(0)
      ..write(obj.title)
      ..writeByte(1)
      ..write(obj.message)
      ..writeByte(2)
      ..write(obj.createdAt)
      ..writeByte(3)
      ..write(obj.userId);
  }

  @override
  int get hashCode => typeId.hashCode;

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
          other is ChatLogAdapter &&
              runtimeType == other.runtimeType &&
              typeId == other.typeId;
}
