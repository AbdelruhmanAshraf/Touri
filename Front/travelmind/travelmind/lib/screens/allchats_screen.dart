import 'package:flutter/material.dart';
import '../models/chat_log.dart';
import '../services/hive_service.dart';

class AllChatsScreen extends StatelessWidget {
  const AllChatsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text("All Chats"),
      ),
      body: FutureBuilder<List<ChatLog>>(
        future: HiveService.getChatLogsForCurrentUser(),
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }

          if (snapshot.hasError) {
            return Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  const Text("Please log in to view your chats"),
                  const SizedBox(height: 16),
                  ElevatedButton(
                    onPressed: () =>
                        Navigator.pushReplacementNamed(context, '/login'),
                    child: const Text("Go to Login"),
                  ),
                ],
              ),
            );
          }

          final chats = snapshot.data ?? [];

          if (chats.isEmpty) {
            return const Center(child: Text("No chat logs yet."));
          }

          return ListView.builder(
            itemCount: chats.length,
            itemBuilder: (context, index) {
              final chat = chats[index];
              return ListTile(
                title: Text(chat.title),
                subtitle: Text(
                  chat.createdAt.toString().substring(0, 16),
                  style: const TextStyle(fontSize: 12),
                ),
                onTap: () {
                  Navigator.pushNamed(
                    context,
                    '/chat',
                    arguments: chat.title, // نرجّع للمحادثة بنفس الرسالة
                  );
                },
              );
            },
          );
        },
      ),
    );
  }
}
