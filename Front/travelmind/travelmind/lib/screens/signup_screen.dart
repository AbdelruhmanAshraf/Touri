import 'package:flutter/material.dart';
import 'package:hive/hive.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'package:flutter_facebook_auth/flutter_facebook_auth.dart';
import '../models/user_model.dart';
import '../services/user_session_service.dart';

class SignupScreen extends StatefulWidget {
  const SignupScreen({super.key});

  @override
  _SignupScreenState createState() => _SignupScreenState();
}

class _SignupScreenState extends State<SignupScreen> {
  final _formKey = GlobalKey<FormState>();
  final emailController = TextEditingController();
  final passwordController = TextEditingController();
  final confirmPasswordController = TextEditingController();

  bool _obscurePassword = true;
  bool _isLoading = false;
  bool _rememberMe = false;
  int _passwordStrength = 0;

  final GoogleSignIn _googleSignIn = GoogleSignIn();

  void _checkPasswordStrength(String password) {
    int score = 0;
    if (password.length >= 6) score++;
    if (password.length >= 8 && password.contains(RegExp(r'[A-Z]'))) score++;
    if (password.contains(RegExp(r'[!@#\$%^&*(),.?":{}|<>]'))) score++;

    setState(() {
      _passwordStrength = score;
    });
  }

  String? validateEmail(String? value) {
    const pattern = r'^[\w-]+(\.[\w-]+)*@([\w-]+\.)+[a-zA-Z]{2,7}$';
    final regExp = RegExp(pattern);
    if (value == null || value.isEmpty) return "Please enter your email";
    if (!regExp.hasMatch(value)) return "Enter a valid email address";
    return null;
  }

  String? validatePassword(String? value) {
    if (value == null || value.isEmpty) return "Please enter a password";
    if (value.length < 6) return "Password must be at least 6 characters";
    return null;
  }

  String? validateConfirmPassword(String? value) {
    final password = passwordController.text.trim();
    if (value != password) return "Passwords do not match";
    return null;
  }

  Future<void> _signInWithGoogle() async {
    setState(() => _isLoading = true);
    try {
      final account = await _googleSignIn.signIn();
      if (account != null) {
        final user =
        UserModel(username: account.email, password: "GOOGLE_LOGIN");
        Hive.box<UserModel>('users').add(user); // Save user in Hive
        Navigator.pushReplacementNamed(context, '/home');
      }
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text("Google Sign-In Failed: $e")),
      );
    } finally {
      setState(() => _isLoading = false);
    }
  }

  Future<void> _signInWithFacebook() async {
    setState(() => _isLoading = true);
    try {
      final result = await FacebookAuth.instance.login(); // Trigger login

      if (result.status == LoginStatus.success) {
        final userData = await FacebookAuth.instance.getUserData();
        final user = UserModel(
          username: userData['email'] ?? '',
          password: "FACEBOOK_LOGIN",
        );
        if (user.username.isNotEmpty) {
          Hive.box<UserModel>('users').add(user); // Save user in Hive
          await UserSessionService.setCurrentUser(
              user.username); // Set current user session
          if (mounted) {
            Navigator.pushReplacementNamed(context, '/home');
          }
        }
      }
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text("Facebook Sign-In Failed: $e")),
      );
    } finally {
      setState(() => _isLoading = false);
    }
  }

  void signup() async {
    if (_formKey.currentState!.validate()) {
      setState(() => _isLoading = true);

      await Future.delayed(const Duration(seconds: 1));

      final email = emailController.text.trim();
      final password = passwordController.text.trim();

      final box = Hive.box<UserModel>('users');
      final exists = box.values.any((u) => u.username == email);

      if (!exists) {
        await box.add(UserModel(username: email, password: password));
        if (_rememberMe) {
          final settingsBox = Hive.box('settings');
          settingsBox.put('loggedInUser', email);
        }
        Navigator.pushReplacementNamed(context, '/login');
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text("Email already registered")),
        );
      }

      setState(() => _isLoading = false);
    }
  }

  Widget _buildInputField({
    required String labelText,
    required TextEditingController controller,
    bool obscureText = false,
    IconData? prefixIcon,
    Widget? suffixIcon,
    FormFieldValidator<String>? validator,
  }) {
    return TextFormField(
      controller: controller,
      obscureText: obscureText,
      onChanged: labelText == "Password" ? _checkPasswordStrength : null,
      validator: validator,
      decoration: InputDecoration(
        labelText: labelText,
        labelStyle: const TextStyle(color: Colors.blue),
        prefixIcon:
        prefixIcon != null ? Icon(prefixIcon, color: Colors.blue) : null,
        suffixIcon: suffixIcon,
        filled: true,
        fillColor: Colors.grey.shade200,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide.none,
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide(color: Colors.blue.shade700),
        ),
      ),
      style: const TextStyle(color: Colors.black),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      resizeToAvoidBottomInset: true,
      appBar: AppBar(
        title: const Text("Sign Up"),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back, color: Colors.blue),
          onPressed: () => Navigator.pop(context),
        ),
        backgroundColor: Colors.transparent,
        elevation: 0,
        foregroundColor: Colors.blue,
      ),
      body: Container(
        width: double.infinity,
        padding: const EdgeInsets.symmetric(horizontal: 24.0),
        color: Colors.white,
        child: SingleChildScrollView(
          child: Form(
            key: _formKey,
            child: Padding(
              padding: const EdgeInsets.only(top: 40),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  // App Title
                  const Text(
                    "Create Your Account",
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      fontSize: 28,
                      fontWeight: FontWeight.bold,
                      color: Colors.black,
                    ),
                  ),
                  const SizedBox(height: 12),
                  const Text(
                    "Join us by creating an account.",
                    textAlign: TextAlign.center,
                    style: TextStyle(color: Colors.grey),
                  ),
                  const SizedBox(height: 30),

                  // Email Field
                  _buildInputField(
                    labelText: "Email",
                    controller: emailController,
                    prefixIcon: Icons.email,
                    validator: validateEmail,
                  ),
                  const SizedBox(height: 20),

                  // Password Field
                  _buildInputField(
                    labelText: "Password",
                    controller: passwordController,
                    obscureText: _obscurePassword,
                    prefixIcon: Icons.lock_outline,
                    suffixIcon: IconButton(
                      onPressed: () {
                        setState(() {
                          _obscurePassword = !_obscurePassword;
                        });
                      },
                      icon: Icon(_obscurePassword
                          ? Icons.visibility_off
                          : Icons.visibility),
                    ),
                    validator: validatePassword,
                  ),

                  // Password Strength Indicator
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 8.0),
                    child: Row(
                      children: [
                        Expanded(
                          child: LinearProgressIndicator(
                            value: _passwordStrength / 3,
                            color: _passwordStrength <= 0
                                ? Colors.red
                                : _passwordStrength == 1
                                ? Colors.orange
                                : Colors.green,
                            backgroundColor: Colors.grey[300],
                            minHeight: 10,
                          ),
                        ),
                        const SizedBox(width: 10),
                        Text(
                          _passwordStrength <= 0
                              ? "Weak"
                              : _passwordStrength == 1
                              ? "Medium"
                              : "Strong",
                          style: TextStyle(
                            fontWeight: FontWeight.bold,
                            color: _passwordStrength <= 0
                                ? Colors.red
                                : _passwordStrength == 1
                                ? Colors.orange
                                : Colors.green,
                          ),
                        )
                      ],
                    ),
                  ),
                  const SizedBox(height: 20),

                  // Confirm Password Field
                  _buildInputField(
                    labelText: "Confirm Password",
                    controller: confirmPasswordController,
                    obscureText: _obscurePassword,
                    prefixIcon: Icons.lock_outline,
                    suffixIcon: IconButton(
                      onPressed: () {
                        setState(() {
                          _obscurePassword = !_obscurePassword;
                        });
                      },
                      icon: Icon(_obscurePassword
                          ? Icons.visibility_off
                          : Icons.visibility),
                    ),
                    validator: validateConfirmPassword,
                  ),

                  const SizedBox(height: 20),

                  // Remember Me Checkbox
                  Row(
                    children: [
                      Checkbox(
                        value: _rememberMe,
                        onChanged: (val) =>
                            setState(() => _rememberMe = val ?? false),
                      ),
                      const Text("Remember me"),
                    ],
                  ),

                  // Sign Up Button
                  ElevatedButton.icon(
                    onPressed: _isLoading ? null : signup,
                    icon: _isLoading
                        ? const SizedBox(
                      width: 20,
                      height: 20,
                      child:
                      CircularProgressIndicator(color: Colors.white),
                    )
                        : const Icon(Icons.app_registration),
                    label: _isLoading
                        ? const Text("Signing up...")
                        : const Text("Sign Up"),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.blue.shade700,
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(vertical: 16),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                    ),
                  ),

                  const SizedBox(height: 20),

                  // Divider
                  const Padding(
                    padding: EdgeInsets.symmetric(vertical: 8.0),
                    child: Text(
                      "Or continue with",
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        fontWeight: FontWeight.bold,
                        color: Colors.grey,
                      ),
                    ),
                  ),

                  const SizedBox(height: 12),

                  // Sign Up with Google
                  ElevatedButton.icon(
                    onPressed: _isLoading ? null : _signInWithGoogle,
                    icon: const Icon(Icons.g_mobiledata, color: Colors.blue),
                    label: const Text("Sign Up with Google"),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.white,
                      foregroundColor: Colors.black87,
                      padding: const EdgeInsets.symmetric(vertical: 14),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                      side: const BorderSide(color: Colors.grey),
                    ),
                  ),

                  const SizedBox(height: 12),

                  // Sign Up with Facebook
                  ElevatedButton.icon(
                    onPressed: _isLoading ? null : _signInWithFacebook,
                    icon: const Icon(Icons.facebook, color: Colors.blue),
                    label: const Text("Sign Up with Facebook"),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.white,
                      foregroundColor: Colors.black87,
                      padding: const EdgeInsets.symmetric(vertical: 14),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                      side: const BorderSide(color: Colors.grey),
                    ),
                  ),

                  const SizedBox(height: 20),

                  // Already have an account?
                  Align(
                    alignment: Alignment.center,
                    child: TextButton(
                      onPressed: () =>
                          Navigator.pushReplacementNamed(context, '/login'),
                      child: const Text("Already have an account? Login"),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
