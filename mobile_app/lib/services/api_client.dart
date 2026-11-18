import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;

import '../config.dart';
import '../models/feature_spec.dart';
import '../models/prediction_result.dart';
import 'token_store.dart';

enum ApiErrorKind { network, timeout, unauthorized, validation, locked, server }

class ApiException implements Exception {
  final ApiErrorKind kind;
  final String message;

  /// Server-side validation messages keyed by feature `key` (e.g. {"temperature": "..."}).
  final Map<String, String> fieldErrors;
  const ApiException(this.kind, this.message, {this.fieldErrors = const {}});

  @override
  String toString() => message;
}

class ApiClient {
  ApiClient(this._store);

  final TokenStore _store;
  final http.Client _http = http.Client();

  /// UI listens to this: false => show the login screen.
  final ValueNotifier<bool> signedIn = ValueNotifier<bool>(false);

  Uri _u(String path) => Uri.parse('${AppConfig.baseUrl}/api/v1$path');

  // ---------------------------------------------------------------- session
  Future<void> restoreSession() async {
    signedIn.value = (await _store.refresh) != null;
  }

  Future<void> login(String username, String password) async {
    final r = await _send(() => _http.post(
          _u('/auth/login'),
          headers: {'Content-Type': 'application/x-www-form-urlencoded'},
          body: {'username': username, 'password': password},
        ));
    if (r.statusCode == 200) {
      final j = jsonDecode(r.body) as Map<String, dynamic>;
      await _store.save(j['access_token'] as String, j['refresh_token'] as String);
      signedIn.value = true;
      return;
    }
    if (r.statusCode == 429) {
      throw ApiException(ApiErrorKind.locked, _detail(r) ?? 'Too many attempts. Try again later.');
    }
    if (r.statusCode == 401) {
      throw const ApiException(ApiErrorKind.unauthorized, 'Incorrect username or password.');
    }
    throw _serverError(r);
  }

  Future<void> logout() async {
    final access = await _store.access;
    final refresh = await _store.refresh;
    if (access != null && refresh != null) {
      try {
        await _http
            .post(_u('/auth/logout'),
                headers: {'Authorization': 'Bearer $access', 'Content-Type': 'application/json'},
                body: jsonEncode({'refresh_token': refresh}))
            .timeout(const Duration(seconds: 5));
      } catch (_) {
        // best effort: tokens are removed locally either way
      }
    }
    await _store.clear();
    signedIn.value = false;
  }

  Future<bool> _refresh() async {
    final refresh = await _store.refresh;
    if (refresh == null) return false;
    try {
      final r = await _send(() => _http.post(_u('/auth/refresh'),
          headers: {'Content-Type': 'application/json'}, body: jsonEncode({'refresh_token': refresh})));
      if (r.statusCode == 200) {
        final j = jsonDecode(r.body) as Map<String, dynamic>;
        await _store.save(j['access_token'] as String, j['refresh_token'] as String);
        return true;
      }
    } on ApiException {
      rethrow; // network problems must not log the user out
    }
    return false;
  }

  // ---------------------------------------------------------------- API calls
  Future<ModelSchema> fetchSchema() async {
    final r = await _authed((h) => _http.get(_u('/model/schema'), headers: h));
    if (r.statusCode == 200) {
      return ModelSchema.fromJson(jsonDecode(r.body) as Map<String, dynamic>);
    }
    throw _serverError(r);
  }

  Future<PredictionResult> predict(Map<String, num> values) async {
    final r = await _authed((h) => _http.post(_u('/predict'),
        headers: {...h, 'Content-Type': 'application/json'}, body: jsonEncode(values)));
    if (r.statusCode == 200) {
      return PredictionResult.fromJson(jsonDecode(r.body) as Map<String, dynamic>);
    }
    if (r.statusCode == 422) {
      final j = jsonDecode(r.body) as Map<String, dynamic>;
      final fe = <String, String>{};
      for (final e in (j['errors'] ?? []) as List) {
        final f = e['field'];
        if (f != null) fe[f as String] = e['message'] as String;
      }
      throw ApiException(ApiErrorKind.validation, 'Some inputs were rejected by the server.',
          fieldErrors: fe);
    }
    throw _serverError(r);
  }

  // ---------------------------------------------------------------- plumbing
  /// Sends an authenticated request; on 401 tries one token refresh, then retries once.
  Future<http.Response> _authed(Future<http.Response> Function(Map<String, String> headers) send) async {
    var access = await _store.access;
    if (access == null) await _expire();
    var r = await _send(() => send({'Authorization': 'Bearer $access'}));
    if (r.statusCode == 401) {
      if (await _refresh()) {
        access = await _store.access;
        r = await _send(() => send({'Authorization': 'Bearer $access'}));
      }
      if (r.statusCode == 401) await _expire();
    }
    return r;
  }

  Future<Never> _expire() async {
    await _store.clear();
    signedIn.value = false;
    throw const ApiException(ApiErrorKind.unauthorized, 'Your session has expired. Please log in again.');
  }

  Future<http.Response> _send(Future<http.Response> Function() call) async {
    try {
      return await call().timeout(AppConfig.timeout);
    } on TimeoutException {
      throw const ApiException(ApiErrorKind.timeout, 'The server took too long to respond. Please try again.');
    } on SocketException {
      throw const ApiException(ApiErrorKind.network,
          'Cannot reach the server. Check your internet connection and the server address.');
    } on HandshakeException {
      throw const ApiException(ApiErrorKind.network, 'Secure (HTTPS) connection to the server failed.');
    } on http.ClientException {
      throw const ApiException(ApiErrorKind.network, 'Network error. Please try again.');
    }
  }

  String? _detail(http.Response r) {
    try {
      final d = (jsonDecode(r.body) as Map<String, dynamic>)['detail'];
      return d is String ? d : null;
    } catch (_) {
      return null;
    }
  }

  ApiException _serverError(http.Response r) => ApiException(ApiErrorKind.server,
      _detail(r) ?? 'Server error (${r.statusCode}). Please try again later.');
}
