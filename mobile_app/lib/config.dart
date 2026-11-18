/// Build-time configuration. The server URL is NOT a secret; credentials are never compiled in.
///
///   flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000        (Android emulator -> your PC)
///   flutter build apk --dart-define=API_BASE_URL=https://api.example.com
class AppConfig {
  static const String baseUrl =
      String.fromEnvironment('API_BASE_URL', defaultValue: 'http://10.0.2.2:8000');
  static const Duration timeout = Duration(seconds: 20);
}
