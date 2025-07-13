import 'package:flutter/material.dart';
import '../models/chat_log.dart';
import '../services/api_service.dart';
import '../services/user_session_service.dart';
import '../services/hive_service.dart';
import '../widgets/message_bubble.dart';

class ChatScreen extends StatefulWidget {
  final String query;
  const ChatScreen({super.key, required this.query});

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final List<Map<String, dynamic>> _messages = [];
  final TextEditingController _controller = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  bool _isLoading = false;
  Map<String, dynamic> _session = {};
  List<String> _cityRecommendations = [];

  @override
  void initState() {
    super.initState();
    _sendInitialQuery(widget.query);
  }

  Future<void> _sendInitialQuery(String question) async {
    setState(() {
      _messages.add({'message': question, 'isUser': true});
      _isLoading = true;
    });

    try {
      final response =
      await ApiService.sendUserMessage(question, session: _session);
      _session = response['session'] ?? _session;
      await _handleResponse(response);
    } catch (e) {
      setState(() {
        _messages.add({'message': '⚠️ Error: $e', 'isUser': false});
      });
    } finally {
      setState(() => _isLoading = false);
      _scrollToBottom();
    }
  }

  Future<void> _sendNewMessage() async {
    final text = _controller.text.trim();
    if (text.isEmpty || _isLoading) return;

    setState(() {
      _messages.add({'message': text, 'isUser': true});
      _controller.clear();
      _isLoading = true;
    });

    try {
      final isReachable = await ApiService.isServerReachable();
      if (!isReachable) {
        setState(() {
          _messages.add({
            'message': 'Server unreachable. Check connection.',
            'isUser': false
          });
        });
      } else {
        final response =
        await ApiService.sendUserMessage(text, session: _session);
        _session = response['session'] ?? {};
        await _handleResponse(response);
      }
    } catch (e) {
      setState(() {
        _messages.add({'message': '⚠️ Error: $e', 'isUser': false});
      });
    } finally {
      setState(() => _isLoading = false);
      _scrollToBottom();
    }
  }

  Future<String> _handleResponse(Map<String, dynamic> response) async {
    final type = response['type'];
    String responseText;

    switch (type) {
      case 'general':
        responseText = response['response'];
        break;
      case 'profile_question':
        responseText = response['question'];
        break;
      case 'city_recommendation':
        final cities = response['cities'];
        final question = response['question'];
        final newRecommendations =
        cities is List ? List<String>.from(cities) : [cities.toString()];
        final isDuplicate =
        _areSameRecommendations(_cityRecommendations, newRecommendations);
        if (!isDuplicate) {
          _cityRecommendations = newRecommendations;
          responseText = '${_cityRecommendations.join('\n')}\n\n$question';
        } else {
          responseText = question;
        }
        break;
      case 'trip_plan':
        responseText = response['plan'];
        _session = {};
        break;
      default:
        responseText = response['response'] ?? 'Unexpected response: $type';
    }

    setState(() {
      _messages.add({'message': responseText, 'isUser': false});
    });

    return responseText;
  }

  bool _areSameRecommendations(List<String> list1, List<String> list2) {
    if (list1.length != list2.length) return false;
    for (int i = 0; i < list1.length; i++) {
      if (list1[i] != list2[i]) return false;
    }
    return true;
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  Future<void> _saveCurrentChatToAllChats() async {
    final lastUserMessage = _messages.reversed.firstWhere(
          (msg) => msg['isUser'] == true,
      orElse: () => {},
    );

    final lastBotMessage = _messages.reversed.firstWhere(
          (msg) => msg['isUser'] == false,
      orElse: () => {},
    );

    if (lastUserMessage.isEmpty || lastBotMessage.isEmpty) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('No messages to save')),
        );
      }
      return;
    }

    final currentUserId = UserSessionService.getCurrentUserId();
    if (currentUserId == null || currentUserId.isEmpty) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Please log in to save chats')),
        );
      }
      return;
    }

    final chat = ChatLog(
      title: lastUserMessage['message'],
      message: lastBotMessage['message'],
      createdAt: DateTime.now(),
      userId: currentUserId,
    );

    try {
      await HiveService.saveChatLogForCurrentUser(chat);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Chat saved')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error saving chat: $e')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 0,
        foregroundColor: Colors.black,
        title: const Text("Travel Mind",
            style: TextStyle(fontWeight: FontWeight.bold)),
        centerTitle: true,
      ),
      body: Column(
        children: [
          Expanded(
            child: ListView.builder(
              controller: _scrollController,
              itemCount: _messages.length,
              itemBuilder: (context, index) {
                final msg = _messages[index];
                return MessageBubble(
                  message: msg['message'],
                  isUser: msg['isUser'],
                );
              },
            ),
          ),
          if (_isLoading)
            const Padding(
              padding: EdgeInsets.all(8.0),
              child: CircularProgressIndicator(),
            ),

          // ✅ زر الحفظ واضح بعد الرسائل مباشرة
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16.0, vertical: 8),
            child: ElevatedButton.icon(
              onPressed: _saveCurrentChatToAllChats,
              icon: const Icon(Icons.save),
              label: const Text("Save Chat"),
              style: ElevatedButton.styleFrom(
                backgroundColor: Colors.teal,
                foregroundColor: Colors.white,
                minimumSize: const Size.fromHeight(48),
              ),
            ),
          ),

          // ✅ خانة الكتابة
          Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _controller,
                  onSubmitted: (_) => _sendNewMessage(),
                  decoration: InputDecoration(
                    hintText: 'Ask me anything...',
                    filled: true,
                    fillColor: Colors.grey[200],
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(24),
                      borderSide: BorderSide.none,
                    ),
                  ),
                ),
              ),
              IconButton(
                icon: const Icon(Icons.send),
                onPressed: _isLoading ? null : _sendNewMessage,
              ),
            ],
          ),
        ],
      ),
    );
  }
}