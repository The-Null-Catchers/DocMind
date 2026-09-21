import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api_client.dart';
import '../../core/providers.dart';
import '../../data/offline_cache.dart';

class AuthState {
  const AuthState({required this.status, this.user, this.error});

  const AuthState.loading() : this(status: AuthStatus.loading);
  const AuthState.unauthenticated() : this(status: AuthStatus.unauthenticated);
  const AuthState.authenticated(Map<String, dynamic> user)
    : this(status: AuthStatus.authenticated, user: user);

  final AuthStatus status;
  final Map<String, dynamic>? user;
  final String? error;

  AuthState copyWith({
    AuthStatus? status,
    Map<String, dynamic>? user,
    String? error,
  }) => AuthState(
    status: status ?? this.status,
    user: user ?? this.user,
    error: error,
  );
}

enum AuthStatus { loading, authenticated, unauthenticated }

bool _isOfflineAuthError(Object error) =>
    error is DioException &&
    {
      DioExceptionType.connectionError,
      DioExceptionType.connectionTimeout,
      DioExceptionType.receiveTimeout,
      DioExceptionType.sendTimeout,
    }.contains(error.type);

class AuthController extends StateNotifier<AuthState> {
  AuthController(this._api, this._cache, this._resetWorkspace)
    : super(const AuthState.loading()) {
    restoreSession();
  }

  final ApiClient _api;
  final OfflineCache _cache;
  final void Function() _resetWorkspace;

  Future<void> restoreSession() async {
    final accountId = await _api.accountId();
    if (accountId != null && accountId.isNotEmpty) {
      _cache.useAccount(accountId);
    }

    if (!await _api.hasRefreshToken()) {
      if (accountId != null && accountId.isNotEmpty) {
        await _cache.clearAccount(accountId);
      }
      _cache.clearAccountContext();
      await _api.clearTokens();
      _resetWorkspace();
      state = const AuthState.unauthenticated();
      return;
    }

    try {
      final response = await _api.dio.get('/auth/me');
      final user = Map<String, dynamic>.from(response.data as Map);
      final userId = user['id']?.toString();
      if (userId == null || userId.isEmpty) {
        throw StateError('Authenticated user is missing an id');
      }
      if (accountId == null || accountId.isEmpty) {
        // Upgrade path from the legacy unscoped cache: never reuse old files.
        await _cache.clearAll();
      } else if (accountId != userId) {
        await _cache.clearAccount(accountId);
      }
      _cache.useAccount(userId);
      await _api.cacheUser(user);
      state = AuthState.authenticated(user);
    } catch (error) {
      if (_isOfflineAuthError(error)) {
        final cached = await _api.cachedUser();
        if (cached != null && accountId != null && accountId.isNotEmpty) {
          _cache.useAccount(accountId);
          state = AuthState.authenticated(cached);
          return;
        }
      }

      final currentAccountId = accountId ?? await _api.accountId();
      if (currentAccountId != null && currentAccountId.isNotEmpty) {
        await _cache.clearAccount(currentAccountId);
      }
      _cache.clearAccountContext();
      await _api.clearTokens();
      _resetWorkspace();
      state = const AuthState.unauthenticated();
    }
  }

  Future<bool> login(String email, String password) async {
    state = const AuthState.loading();
    final previousAccountId = await _api.accountId();
    try {
      final response = await _api.dio.post(
        '/auth/login',
        data: {
          'email': email.trim(),
          'password': password,
          'device_name': 'DocMind Flutter',
        },
      );
      final data = Map<String, dynamic>.from(response.data as Map);
      final user = Map<String, dynamic>.from(data['user'] as Map);
      final userId = user['id']?.toString();
      if (userId == null || userId.isEmpty) {
        throw StateError('Authenticated user is missing an id');
      }

      if (previousAccountId == null || previousAccountId.isEmpty) {
        await _cache.clearAll();
      } else if (previousAccountId != userId) {
        await _cache.clearAccount(previousAccountId);
      }
      _cache.useAccount(userId);
      _resetWorkspace();
      await _api.saveSession(
        data['access_token'] as String,
        data['refresh_token'] as String,
        user,
      );
      state = AuthState.authenticated(user);
      return true;
    } catch (error) {
      state = AuthState(
        status: AuthStatus.unauthenticated,
        error: _api.errorMessage(error),
      );
      return false;
    }
  }

  Future<bool> register({
    required String email,
    required String password,
    required String displayName,
  }) async {
    state = const AuthState.loading();
    final previousAccountId = await _api.accountId();
    try {
      final response = await _api.dio.post(
        '/auth/register',
        data: {
          'email': email.trim(),
          'password': password,
          'display_name': displayName.trim(),
          'locale': 'en',
        },
      );
      final data = Map<String, dynamic>.from(response.data as Map);
      final user = Map<String, dynamic>.from(data['user'] as Map);
      final userId = user['id']?.toString();
      if (userId == null || userId.isEmpty) {
        throw StateError('Authenticated user is missing an id');
      }

      if (previousAccountId == null || previousAccountId.isEmpty) {
        await _cache.clearAll();
      } else if (previousAccountId != userId) {
        await _cache.clearAccount(previousAccountId);
      }
      _cache.useAccount(userId);
      _resetWorkspace();
      await _api.saveSession(
        data['access_token'] as String,
        data['refresh_token'] as String,
        user,
      );
      state = AuthState.authenticated(user);
      return true;
    } catch (error) {
      state = AuthState(
        status: AuthStatus.unauthenticated,
        error: _api.errorMessage(error),
      );
      return false;
    }
  }

  Future<void> logout() async {
    final accountId = await _api.accountId();
    try {
      await _api.dio.post('/auth/logout');
    } catch (_) {
      // Local logout must still succeed when the device is offline.
    }
    if (accountId != null && accountId.isNotEmpty) {
      await _cache.clearAccount(accountId);
    }
    _cache.clearAccountContext();
    _resetWorkspace();
    await _api.clearTokens();
    state = const AuthState.unauthenticated();
  }
}

final authControllerProvider = StateNotifierProvider<AuthController, AuthState>(
  (ref) {
    return AuthController(
      ref.watch(apiClientProvider),
      ref.watch(offlineCacheProvider),
      () => ref.read(selectedWorkspaceProvider.notifier).state = null,
    );
  },
);
