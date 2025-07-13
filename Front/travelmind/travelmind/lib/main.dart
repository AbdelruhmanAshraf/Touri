import 'package:flutter/material.dart';
import 'package:hive_flutter/hive_flutter.dart';
import 'package:travelmind/screens/allchats_screen.dart';
import 'package:travelmind/screens/foreget_password_screen.dart';
import 'package:travelmind/screens/onbording_screen.dart';

// Import models
import 'models/chat_log.dart';
import 'models/user_model.dart';
import 'models/bucketlist_item.dart';
import 'models/favorite_chats.dart';
import 'models/chat_model.dart';
import 'models/message_model.dart';

// Import services
import 'services/user_session_service.dart';
import 'utils/data_migration.dart';

// Import screens
import 'screens/splash_screen.dart';
import 'screens/login_screen.dart';
import 'screens/signup_screen.dart';
import 'screens/home_screen.dart';
import 'screens/chat_screen.dart';
import 'screens/bucketlistscreen.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Initialize Hive
  await Hive.initFlutter();

  // Register adapters
  Hive.registerAdapter(UserModelAdapter());
  Hive.registerAdapter(BucketlistItemAdapter());
  Hive.registerAdapter(FavoriteChatAdapter());
  Hive.registerAdapter(ChatLogAdapter());
  Hive.registerAdapter(ChatModelAdapter());
  Hive.registerAdapter(MessageModelAdapter());

  // Open boxes
  await Hive.openBox<UserModel>('users');
  await Hive.openBox('settings');
  await Hive.openBox<String>('bucketlist');
  await Hive.openBox<FavoriteChat>('favorite_chats');
  await Hive.openBox<ChatLog>('all_chats');
  await Hive.openBox<ChatModel>('chats');
  await Hive.openBox<MessageModel>('messages');

  // Run data migration if needed
  await DataMigration.runMigrationIfNeeded();

  // Initialize user session service
  await UserSessionService.initialize();

  // Debug: Test basic functionality
  try {
    print('Hive initialization complete');
    print('Settings box open: ${Hive.isBoxOpen('settings')}');
  } catch (e) {
    print('Error during initialization: $e');
  }

  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'TripMind',
      theme: ThemeData(
        primarySwatch: Colors.blue,
        scaffoldBackgroundColor: Colors.white,
        appBarTheme: const AppBarTheme(
          backgroundColor: Colors.transparent,
          elevation: 0,
          foregroundColor: Colors.black,
          iconTheme: IconThemeData(
              color: Colors.black), // ✅ علشان الأيقونات تظهر بوضوح
        ),
      ),
      initialRoute: '/splash',
      routes: {
        '/splash': (context) => const SplashScreen(),
        '/onboarding': (context) => const OnboardingScreen(),
        '/login': (context) => const LoginScreen(),
        '/signup': (context) => const SignupScreen(),
        '/home': (context) => const HomeScreen(),
        '/chat': (context) => ChatScreen(
            query: ModalRoute.of(context)!.settings.arguments as String),
        '/bucketlist': (context) => const BucketlistScreen(),
        '/forgot_password': (context) => ForgotPasswordScreen(),
        '/all_chats': (context) => const AllChatsScreen(),
      },
    );
  }
}
