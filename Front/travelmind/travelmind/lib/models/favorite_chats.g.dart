// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'favorite_chats.dart';

// **************************************************************************
// TypeAdapterGenerator
// **************************************************************************

class FavoriteChatAdapter extends TypeAdapter<FavoriteChat> {
  @override
  final int typeId = 4;

  @override
  FavoriteChat read(BinaryReader reader) {
    final numOfFields = reader.readByte();
    final fields = <int, dynamic>{
      for (int i = 0; i < numOfFields; i++) reader.readByte(): reader.read(),
    };
    return FavoriteChat(
      title: fields[0] as String,
      message: fields[1] as String,
      createdAt: fields[2] as DateTime,
    );
  }

  @override
  void write(BinaryWriter writer, FavoriteChat obj) {
    writer
      ..writeByte(3)
      ..writeByte(0)
      ..write(obj.title)
      ..writeByte(1)
      ..write(obj.message)
      ..writeByte(2)
      ..write(obj.createdAt);
  }

  @override
  int get hashCode => typeId.hashCode;

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
          other is FavoriteChatAdapter &&
              runtimeType == other.runtimeType &&
              typeId == other.typeId;
}
