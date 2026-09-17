import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class ApiClient {
  ApiClient({String baseUrl = const String.fromEnvironment('API_URL', defaultValue: 'http://10.0.2.2:8000/api/v1')})
      : _storage = const FlutterSecureStorage(),
        dio = Dio(BaseOptions(
          baseUrl: baseUrl,
          connectTimeout: const Duration(seconds: 15),
          receiveTimeout: const Duration(seconds: 60),
        )) {
    dio.interceptors.add(InterceptorsWrapper(
      onRequest: (options, handler) async {
        final token = await _storage.read(key: 'access_token');
        if (token != null && token.isNotEmpty) {
          options.headers['Authorization'] = 'Bearer $token';
        }
        handler.next(options);
      },
      onError: (error, handler) async {
        final request = error.requestOptions;
        final isAuthRoute = request.path.contains('/auth/login') ||
            request.path.contains('/auth/register') ||
            request.path.contains('/auth/refresh');
        if (error.response?.statusCode != 401 || isAuthRoute || request.extra['retried'] == true) {
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
          await clearTokens();
          handler.next(error);
        }
      },
    ));
  }

  final Dio dio;
  final FlutterSecureStorage _storage;
  Future<bool>? _refreshInFlight;

  Future<String?> accessToken() => _storage.read(key: 'access_token');

  Future<void> saveTokens(String access, String refresh) async {
    await _storage.write(key: 'access_token', value: access);
    await _storage.write(key: 'refresh_token', value: refresh);
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

    final refreshDio = Dio(BaseOptions(
      baseUrl: dio.options.baseUrl,
      connectTimeout: dio.options.connectTimeout,
      receiveTimeout: dio.options.receiveTimeout,
    ));
    try {
      final response = await refreshDio.post('/auth/refresh', data: {'refresh_token': refresh});
      final data = Map<String, dynamic>.from(response.data as Map);
      await saveTokens(data['access_token'] as String, data['refresh_token'] as String);
      return true;
    } on DioException {
      await clearTokens();
      return false;
    }
  }

  String errorMessage(Object error) {
    if (error is DioException) {
      final detail = error.response?.data;
      if (detail is Map && detail['detail'] != null) {
        final value = detail['detail'];
        if (value is String) return value;
        if (value is Map && value['message'] is String) return value['message'] as String;
      }
      if (error.type == DioExceptionType.connectionError || error.type == DioExceptionType.connectionTimeout) {
        return 'Unable to reach DocMind. Check your connection and API URL.';
      }
    }
    return 'Something went wrong. Please try again.';
  }

  Future<void> clearTokens() async {
    await _storage.delete(key: 'access_token');
    await _storage.delete(key: 'refresh_token');
  }
}
