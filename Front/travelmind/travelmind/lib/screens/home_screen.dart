import 'package:flutter/material.dart';
import 'package:hive/hive.dart';
import '../models/favorite_chats.dart';
import '../models/chat_log.dart'; // ✅ replaced
import '../services/api_service.dart';
import '../services/user_session_service.dart';
import '../services/hive_service.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final TextEditingController _textController = TextEditingController();
  final List<Map<String, dynamic>> _chatMessages = [];
  bool _isChatMode = false;
  bool _isLoading = false;
  Map<String, dynamic> _session = {};
  List<String> _cityRecommendations = [];

  void _handleTextSubmission(String input) async {
    if (input.trim().isEmpty || _isLoading) return;

    setState(() {
      _chatMessages.add({'type': 'user', 'message': input});
      _textController.clear();
      _isChatMode = true;
      _isLoading = true;
    });

    try {
      final response =
      await ApiService.sendUserMessage(input, session: _session);
      _session = response['session'] ?? _session;

      final type = response['type'];

      switch (type) {
        case 'general':
          _chatMessages.add({'type': 'bot', 'message': response['response']});
          break;
        case 'profile_question':
          _chatMessages.add({'type': 'bot', 'message': response['question']});
          break;
        case 'city_recommendation':
          final cities = response['cities'];
          final question = response['question'];
          _cityRecommendations =
          cities is List ? List<String>.from(cities) : [cities.toString()];
          final citiesList = _cityRecommendations.join('\n');
          _chatMessages
              .add({'type': 'bot', 'message': '$citiesList\n\n$question'});
          break;
        case 'trip_plan':
          _chatMessages.add({'type': 'bot', 'message': response['plan']});
          break;
        case 'error':
        case 'unknown':
          _chatMessages.add({'type': 'bot', 'message': response['response']});
          break;
        default:
          _chatMessages.add({
            'type': 'bot',
            'message': response['response'] ?? 'Unexpected response type: $type'
          });
      }

      /// ✅ بعد إضافة رسالة البوت، خزّني المحادثة
      final currentUserId = UserSessionService.getCurrentUserId();
      if (currentUserId != null) {
        final fullMessage = _chatMessages
            .map((msg) =>
        "${msg['type'] == 'user' ? 'You' : 'Bot'}: ${msg['message']}")
            .join("\n");
        final title =
        _chatMessages.firstWhere((msg) => msg['type'] == 'user')['message'];
        final chat = ChatLog(
            title: title,
            message: fullMessage,
            createdAt: DateTime.now(),
            userId: currentUserId);
        await HiveService.saveChatLogForCurrentUser(chat);
      }
    } catch (e) {
      _chatMessages.add({'type': 'bot', 'message': '⚠️ Error: $e'});
    } finally {
      setState(() => _isLoading = false);
    }
  }

  void _resetChat() {
    setState(() {
      _isChatMode = false;
      _chatMessages.clear();
      _textController.clear();
      _session = {};
    });
  }

  void _updateApiUrl() {
    showDialog(
      context: context,
      builder: (context) {
        final TextEditingController urlController =
        TextEditingController(text: ApiService.currentBaseUrl);
        return AlertDialog(
          title: const Text('Update API URL'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                controller: urlController,
                decoration: const InputDecoration(
                  hintText: 'Enter ngrok URL',
                  labelText: 'API URL',
                ),
              ),
              const SizedBox(height: 10),
              Text('Current URL: ${ApiService.currentBaseUrl}',
                  style: const TextStyle(fontSize: 12, color: Colors.grey)),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Cancel'),
            ),
            TextButton(
              onPressed: () async {
                final newUrl = urlController.text.trim();
                if (newUrl.isNotEmpty) {
                  final formattedUrl =
                  newUrl.startsWith('http') ? newUrl : 'https://$newUrl';
                  ApiService.updateBaseUrl(formattedUrl);
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(
                      content: Text('API URL updated to: $formattedUrl'),
                      backgroundColor: Colors.green,
                    ),
                  );
                }
                Navigator.pop(context);
              },
              child: const Text('Update'),
            ),
          ],
        );
      },
    );
  }

  void _saveFavoriteChat() async {
    if (_chatMessages.isEmpty) return;
    final box = await Hive.openBox<FavoriteChat>('favorite_chats');
    final fullMessage = _chatMessages
        .map((msg) =>
    "${msg['type'] == 'user' ? 'You' : 'Bot'}: ${msg['message']}")
        .join("\n");
    final title =
    _chatMessages.firstWhere((msg) => msg['type'] == 'user')['message'];
    final chat = FavoriteChat(
      title: title,
      message: fullMessage,
      createdAt: DateTime.now(),
    );
    await box.add(chat);
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Chat saved to favorites')),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 0,
        title: Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            PopupMenuButton<String>(
              onSelected: (value) {
                if (value == 'all_chats') {
                  Navigator.pushNamed(context, '/all_chats');
                } else if (value == 'favorite_chats') {
                  Navigator.pushNamed(context, '/bucketlist');
                } else if (value == 'reset_chat') {
                  _resetChat();
                } else if (value == 'update_api') {
                  _updateApiUrl();
                }
              },
              itemBuilder: (context) => const [
                PopupMenuItem(value: 'all_chats', child: Text('All Chats')),
                PopupMenuItem(
                    value: 'favorite_chats', child: Text('Favorite Chats')),
                PopupMenuItem(value: 'reset_chat', child: Text('Reset Chat')),
                PopupMenuItem(
                    value: 'update_api', child: Text('Update API URL')),
              ],
              icon: const Icon(Icons.menu),
            ),
            Row(
              children: const [
                CircleAvatar(
                  backgroundImage: AssetImage('lib/assets/images/avatar.jpg'),
                  radius: 20,
                ),
                SizedBox(width: 8),
                Text(
                  'travel mind',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                ),
              ],
            ),
            Row(
              children: [
                IconButton(
                  icon: const Icon(Icons.favorite_border),
                  onPressed: _saveFavoriteChat,
                ),
              ],
            ),
          ],
        ),
      ),
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            if (!_isChatMode)
              Container(
                decoration: BoxDecoration(
                  color: Colors.grey[200],
                  borderRadius: BorderRadius.circular(8),
                ),
                padding: const EdgeInsets.all(16),
                margin: const EdgeInsets.only(bottom: 24),
                child: const Text(
                  'Here we are again, what are we chatting about today? Ask me literally anything related to travel.',
                  style: TextStyle(fontSize: 16),
                ),
              ),
            Expanded(
              child: _isChatMode
                  ? Column(
                children: [
                  Expanded(
                    child: ListView.builder(
                      reverse: true,
                      itemCount: _chatMessages.length,
                      itemBuilder: (context, index) {
                        final message = _chatMessages[
                        _chatMessages.length - 1 - index];
                        final isUser = message['type'] == 'user';
                        return Align(
                          alignment: isUser
                              ? Alignment.centerRight
                              : Alignment.centerLeft,
                          child: Container(
                            margin: const EdgeInsets.symmetric(
                                vertical: 4, horizontal: 8),
                            padding: const EdgeInsets.all(12),
                            constraints: BoxConstraints(
                              maxWidth:
                              MediaQuery.of(context).size.width * 0.8,
                            ),
                            decoration: BoxDecoration(
                              color: isUser
                                  ? Colors.blue[200]
                                  : Colors.grey[300],
                              borderRadius: BorderRadius.circular(16),
                            ),
                            child: Text(
                              message['message'],
                              style: TextStyle(
                                fontSize: 16,
                                color:
                                isUser ? Colors.white : Colors.black,
                              ),
                            ),
                          ),
                        );
                      },
                    ),
                  ),
                  if (_isLoading)
                    const Padding(
                      padding: EdgeInsets.all(8.0),
                      child: CircularProgressIndicator(),
                    ),
                ],
              )
                  : GridView.count(
                crossAxisCount: 2,
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                crossAxisSpacing: 16,
                mainAxisSpacing: 16,
                children: [
                  buildCard(
                    imageUrl: 'lib/assets/images/1.jpg',
                    headline: 'Inspire me where to go',
                    onTap: () =>
                        _handleTextSubmission('Inspire me where to go'),
                  ),
                  buildCard(
                    imageUrl: 'lib/assets/images/2.jpg',
                    headline: 'Find me cheap flights',
                    onTap: () =>
                        _handleTextSubmission('Find me cheap flights'),
                  ),
                  buildCard(
                    imageUrl: 'lib/assets/images/3.jpg',
                    headline: 'Build me an itinerary',
                    onTap: () =>
                        _handleTextSubmission('Build me an itinerary'),
                  ),
                  buildCard(
                    imageUrl: 'lib/assets/images/4.jpg',
                    headline: 'Show me amazing hotels',
                    onTap: () =>
                        _handleTextSubmission('Show me amazing hotels'),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 24),
            Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _textController,
                    enabled: !_isLoading,
                    onSubmitted: _handleTextSubmission,
                    decoration: InputDecoration(
                      hintText: 'Ask me anything',
                      filled: true,
                      fillColor: Colors.grey[200],
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(24),
                        borderSide: BorderSide.none,
                      ),
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                IconButton(
                  icon: Icon(_isChatMode ? Icons.refresh : Icons.send),
                  onPressed: _isLoading
                      ? null
                      : () {
                    final input = _textController.text.trim();
                    if (_isChatMode && input.isEmpty) {
                      _resetChat();
                    } else if (input.isNotEmpty) {
                      _handleTextSubmission(input);
                    }
                  },
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget buildCard({
    required String imageUrl,
    required String headline,
    required VoidCallback onTap,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: Card(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
        clipBehavior: Clip.hardEdge,
        child: Stack(
          children: [
            Positioned.fill(
              child: Image.asset(
                imageUrl,
                fit: BoxFit.cover,
                errorBuilder: (context, error, stackTrace) {
                  return Container(
                    color: Colors.grey[300],
                    child: const Icon(Icons.image_not_supported),
                  );
                },
              ),
            ),
            Positioned.fill(
              child: Container(
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    colors: [Colors.black.withOpacity(0.5), Colors.transparent],
                    begin: Alignment.bottomCenter,
                    end: Alignment.topCenter,
                  ),
                ),
              ),
            ),
            Positioned(
              bottom: 16,
              left: 16,
              right: 16,
              child: Text(
                headline,
                style: const TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.bold,
                  color: Colors.white,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
