import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api_client.dart';
import '../../core/providers.dart';

class AccountRepository {
  AccountRepository(this._api);
  final ApiClient _api;

  Future<Map<String, dynamic>> forgotPassword(String email) async {
    final response = await _api.dio.post('/auth/password/forgot', data: {'email': email.trim()});
    return Map<String, dynamic>.from(response.data as Map);
  }

  Future<void> resetPassword(String token, String password) async {
    await _api.dio.post('/auth/password/reset', data: {'token': token.trim(), 'password': password});
  }

  Future<Map<String, dynamic>> requestVerification() async {
    final response = await _api.dio.post('/auth/email-verification/request');
    return Map<String, dynamic>.from(response.data as Map);
  }

  Future<void> confirmVerification(String token) async {
    await _api.dio.post('/auth/email-verification/confirm', data: {'token': token.trim()});
  }

  Future<List<Map<String, dynamic>>> sessions() async {
    final response = await _api.dio.get('/auth/sessions');
    return (response.data as List).map((e) => Map<String, dynamic>.from(e as Map)).toList();
  }

  Future<void> revokeSession(String sessionId) async {
    await _api.dio.delete('/auth/sessions/$sessionId');
  }

  Future<void> deleteAccount() async {
    await _api.dio.delete('/auth/account');
  }
}

final accountRepositoryProvider = Provider((ref) => AccountRepository(ref.watch(apiClientProvider)));
