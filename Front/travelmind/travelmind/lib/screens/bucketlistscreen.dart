import 'package:flutter/material.dart';
import 'package:hive/hive.dart';
import '../models/favorite_chats.dart';

class BucketlistScreen extends StatelessWidget {
  const BucketlistScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final box = Hive.box<FavoriteChat>('favorite_chats');
    final items = box.values.toList();

    return Scaffold(
      appBar: AppBar(title: Text("Favorite Chats")),
      body: items.isEmpty
          ? Center(child: Text("No favorites yet"))
          : ListView.builder(
        itemCount: items.length,
        itemBuilder: (context, index) {
          final item = items[index];
          return ListTile(
            title: Text(item.message),
            trailing: IconButton(
              icon: Icon(Icons.delete),
              onPressed: () => box.deleteAt(index),
            ),
            onTap: () {
              Navigator.pushNamed(context, '/chat', arguments: item.message);
            },
          );
        },
      ),
    );
  }
}