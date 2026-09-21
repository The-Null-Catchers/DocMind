import 'dart:async';
import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class ApiClient {
  ApiClient({
    String baseUrl = const String.fromEnvironment(
      'API_URL',
      defaultValue: 'http://10.0.2.2:8000/api/v1',
    ),
  }) : _storage = const FlutterSecureStorage(),
       dio = Dio(
         BaseOptions(
           baseUrl: baseUrl,
           connectTimeout: const Duration(seconds: 15),
           receiveTimeout: const Duration(seconds: 60),
         ),
       ) {
    dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) async {
          final token = await _storage.read(key: 'access_token');
          if (token != null && token.isNotEmpty) {
            options.headers['Authorization'] = 'Bearer $token';
          }
          handler.next(options);
        },
        onError: (error, handler) async {
          final request = error.requestOptions;
          final isAuthRoute =
              request.path.contains('/auth/login') ||
              request.path.contains('/auth/register') ||
              request.path.contains('/auth/refresh');
          if (error.response?.statusCode != 401 ||
              isAuthRoute ||
              request.extra['retried'] == true) {
            handler.next(error);
            return;
          }

          try {
            final refreshed = await _refreshAccessToken();
            if (!refreshed) {
              handler.next(error);
              return;
            }
            final token = await _storage.read(key: 'access_token');
            request.extra['retried'] = true;
            request.headers['Authorization'] = 'Bearer $token';
            final response = await dio.fetch<dynamic>(request);
            handler.resolve(response);
          } catch (_) {
            handler.next(error);
          }
        },
      ),
    );
  }

  final Dio dio;
  final FlutterSecureStorage _storage;
  Future<bool>? _refreshInFlight;

  Future<String?> accessToken() => _storage.read(key: 'access_token');

  Future<String?> accountId() => _storage.read(key: 'account_id');

  Future<Map<String, dynamic>?> cachedUser() async {
    final raw = await _storage.read(key: 'session_user');
    if (raw == null || raw.isEmpty) return null;
    try {
      final decoded = jsonDecode(raw);
      if (decoded is Map) return Map<String, dynamic>.from(decoded);
    } on FormatException {
      await _storage.delete(key: 'session_user');
    }
    return null;
  }

  Future<void> saveTokens(String access, String refresh) async {
    await _storage.write(key: 'access_token', value: access);
    await _storage.write(key: 'refresh_token', value: refresh);
  }

  Future<void> saveSession(
    String access,
    String refresh,
    Map<String, dynamic> user,
  ) async {
    await saveTokens(access, refresh);
    await cacheUser(user);
  }

  Future<void> cacheUser(Map<String, dynamic> user) async {
    final id = user['id']?.toString();
    if (id == null || id.isEmpty) {
      throw StateError('Authenticated user is missing an id');
    }
    await _storage.write(key: 'account_id', value: id);
    await _storage.write(key: 'session_user', value: jsonEncode(user));
  }

  Future<bool> hasRefreshToken() async {
    final token = await _storage.read(key: 'refresh_token');
    return token != null && token.isNotEmpty;
  }

  Future<bool> _refreshAccessToken() {
    final existing = _refreshInFlight;
    if (existing != null) return existing;
    final future = _performRefresh();
    _refreshInFlight = future;
    return future.whenComplete(() => _refreshInFlight = null);
  }

  Future<bool> _performRefresh() async {
    final refresh = await _storage.read(key: 'refresh_token');
    if (refresh == null || refresh.isEmpty) return false;

    final refreshDio = Dio(
      BaseOptions(
        baseUrl: dio.options.baseUrl,
        connectTimeout: dio.options.connectTimeout,
        receiveTimeout: dio.options.receiveTimeout,
      ),
    );
    try {
      final response = await refreshDio.post(
        '/auth/refresh',
        data: {'refresh_token': refresh},
      );
      final data = Map<String, dynamic>.from(response.data as Map);
      await saveTokens(
        data['access_token'] as String,
        data['refresh_token'] as String,
      );
      return true;
    } on DioException catch (error) {
      final status = error.response?.statusCode;
      if (status == 400 || status == 401 || status == 403) {
        await clearTokens();
      }
      return false;
    }
  }

  String errorMessage(Object error) {
    if (error is DioException) {
      final detail = error.response?.data;
      if (detail is Map && detail['detail'] != null) {
        final value = detail['detail'];
        if (value is String) return value;
        if (value is Map && value['message'] is String)
          return value['message'] as String;
      }
      if (error.type == DioExceptionType.connectionError ||
          error.type == DioExceptionType.connectionTimeout) {
        return 'Unable to reach DocMind. Check your connection and API URL.';
      }
    }
    return 'Something went wrong. Please try again.';
  }

  Future<void> clearTokens() async {
    await _storage.delete(key: 'access_token');
    await _storage.delete(key: 'refresh_token');
    await _storage.delete(key: 'account_id');
    await _storage.delete(key: 'session_user');
  }
}
