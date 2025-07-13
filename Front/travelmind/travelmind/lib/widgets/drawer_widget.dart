import 'package:flutter/material.dart';
import 'package:hive/hive.dart';
import '../models/chat_model.dart';
import '../services/user_session_service.dart';

class ChatDrawer extends StatefulWidget {
  final Function(String) onNewChat;
  final Function(ChatModel) onSelectChat;

  const ChatDrawer(
      {super.key, required this.onNewChat, required this.onSelectChat});

  @override
  State<ChatDrawer> createState() => _ChatDrawerState();
}

class _ChatDrawerState extends State<ChatDrawer> {
  final Box<ChatModel> chatBox = Hive.box<ChatModel>('chats');
  bool isBucketList = false;

  void createNewChat() {
    final currentUserId = UserSessionService.getCurrentUserId();
    if (currentUserId == null || currentUserId.isEmpty) {
      // Handle case where no user is logged in
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please log in to create chats')),
      );
      return;
    }

    final newChat = ChatModel(
      title: 'New Chat',
      createdAt: DateTime.now(),
      userId: currentUserId,
    );
    chatBox.add(newChat);
    widget.onNewChat(newChat.title);
    setState(() {}); // Refresh the list
  }

  String formatDate(DateTime date) {
    final now = DateTime.now();
    if (date.day == now.day &&
        date.month == now.month &&
        date.year == now.year) {
      return 'Today';
    } else if (now.difference(date).inDays <= 30) {
      return '1 month ago';
    } else {
      return '2 months ago';
    }
  }

  @override
  Widget build(BuildContext context) {
    List<ChatModel> chats = chatBox.values.toList();
    Map<String, List<ChatModel>> groupedChats = {};

    for (var chat in chats) {
      String key = formatDate(chat.createdAt);
      groupedChats.putIfAbsent(key, () => []).add(chat);
    }

    return Drawer(
      child: SafeArea(
        child: Column(
          children: [
            // Profile Header
            ListTile(
              leading: const CircleAvatar(child: Text('MS')),
              title: const Text("Manal Salama",
                  style: TextStyle(fontWeight: FontWeight.bold)),
            ),

            // Bucketlist Toggle
            ListTile(
              leading: Icon(Icons.favorite_border,
                  color: isBucketList ? Colors.red : Colors.grey),
              title: const Text('Bucketlist'),
              onTap: () {
                setState(() {
                  isBucketList = !isBucketList;
                });
              },
            ),

            // New Chat
            ListTile(
              leading: const Icon(Icons.edit_outlined),
              title:
              const Text('New Chat', style: TextStyle(color: Colors.grey)),
              onTap: createNewChat,
            ),

            const Divider(),

            // Chat list grouped by time
            Expanded(
              child: ListView(
                children: groupedChats.entries.map((entry) {
                  return Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Padding(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 16, vertical: 8),
                        child: Text(entry.key,
                            style:
                            const TextStyle(fontWeight: FontWeight.bold)),
                      ),
                      ...entry.value.map((chat) {
                        return ListTile(
                          title: Text(chat.title),
                          trailing: const Icon(Icons.more_horiz),
                          onTap: () => widget.onSelectChat(chat),
                        );
                      }),
                    ],
                  );
                }).toList(),
              ),
            ),

            // Footer
            const Divider(),
            const ListTile(
              title: Text('Information and Support'),
              trailing: Icon(Icons.expand_more),
            ),
            const Padding(
              padding: EdgeInsets.only(bottom: 16),
              child: Text('LAYLA',
                  style: TextStyle(
                      color: Colors.cyan, fontWeight: FontWeight.bold)),
            )
          ],
        ),
      ),
    );
  }
}
