import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// Tokens are kept in the platform's secure storage (Android Keystore / iOS Keychain).
class TokenStore {
  static const _access = 'access_token';
  static const _refresh = 'refresh_token';
  final FlutterSecureStorage _s = const FlutterSecureStorage();

  Future<String?> get access => _s.read(key: _access);
  Future<String?> get refresh => _s.read(key: _refresh);

  Future<void> save(String access, String refresh) async {
    await _s.write(key: _access, value: access);
    await _s.write(key: _refresh, value: refresh);
  }

  Future<void> clear() async {
    await _s.delete(key: _access);
    await _s.delete(key: _refresh);
  }
}
