import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api_client.dart';
import '../../core/providers.dart';

class AuthState {
  const AuthState({required this.status, this.user, this.error});

  const AuthState.loading() : this(status: AuthStatus.loading);
  const AuthState.unauthenticated() : this(status: AuthStatus.unauthenticated);
  const AuthState.authenticated(Map<String, dynamic> user)
      : this(status: AuthStatus.authenticated, user: user);

  final AuthStatus status;
  final Map<String, dynamic>? user;
  final String? error;

  AuthState copyWith({AuthStatus? status, Map<String, dynamic>? user, String? error}) =>
      AuthState(status: status ?? this.status, user: user ?? this.user, error: error);
}

enum AuthStatus { loading, authenticated, unauthenticated }

class AuthController extends StateNotifier<AuthState> {
  AuthController(this._api) : super(const AuthState.loading()) {
    restoreSession();
  }

  final ApiClient _api;

  Future<void> restoreSession() async {
    if (!await _api.hasRefreshToken()) {
      state = const AuthState.unauthenticated();
      return;
    }
    try {
      final response = await _api.dio.get('/auth/me');
      state = AuthState.authenticated(Map<String, dynamic>.from(response.data as Map));
    } catch (_) {
      await _api.clearTokens();
      state = const AuthState.unauthenticated();
    }
  }

  Future<bool> login(String email, String password) async {
    state = const AuthState.loading();
    try {
      final response = await _api.dio.post('/auth/login', data: {
        'email': email.trim(),
        'password': password,
        'device_name': 'DocMind Flutter',
      });
      final data = Map<String, dynamic>.from(response.data as Map);
      await _api.saveTokens(data['access_token'] as String, data['refresh_token'] as String);
      state = AuthState.authenticated(Map<String, dynamic>.from(data['user'] as Map));
      return true;
    } catch (error) {
      state = AuthState(status: AuthStatus.unauthenticated, error: _api.errorMessage(error));
      return false;
    }
  }

  Future<bool> register({required String email, required String password, required String displayName}) async {
    state = const AuthState.loading();
    try {
      final response = await _api.dio.post('/auth/register', data: {
        'email': email.trim(),
        'password': password,
        'display_name': displayName.trim(),
        'locale': 'en',
      });
      final data = Map<String, dynamic>.from(response.data as Map);
      await _api.saveTokens(data['access_token'] as String, data['refresh_token'] as String);
      state = AuthState.authenticated(Map<String, dynamic>.from(data['user'] as Map));
      return true;
    } catch (error) {
      state = AuthState(status: AuthStatus.unauthenticated, error: _api.errorMessage(error));
      return false;
    }
  }

  Future<void> logout() async {
    try {
      await _api.dio.post('/auth/logout');
    } catch (_) {
      // Local logout must still succeed when the device is offline.
    }
    await _api.clearTokens();
    state = const AuthState.unauthenticated();
  }
}

final authControllerProvider = StateNotifierProvider<AuthController, AuthState>((ref) {
  return AuthController(ref.watch(apiClientProvider));
});
