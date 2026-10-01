import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:docmind/core/api_client.dart';
import 'package:docmind/features/auth/account_repository.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';

class _RecordingAdapter implements HttpClientAdapter {
  final List<RequestOptions> requests = [];

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    requests.add(options);
    return ResponseBody.fromString('', 204);
  }

  @override
  void close({bool force = false}) {}
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    FlutterSecureStorage.setMockInitialValues({});
  });

  test(
    'password change sends current and new password to authenticated endpoint',
    () async {
      final api = ApiClient(baseUrl: 'https://docmind.test/api/v1');
      final adapter = _RecordingAdapter();
      api.dio.httpClientAdapter = adapter;
      final repository = AccountRepository(api);

      await repository.changePassword(
        'current-secret',
        'new-secret-long-enough',
      );

      expect(adapter.requests, hasLength(1));
      expect(adapter.requests.single.method, 'POST');
      expect(adapter.requests.single.path, '/auth/password/change');
      expect(adapter.requests.single.data, {
        'current_password': 'current-secret',
        'new_password': 'new-secret-long-enough',
      });
    },
  );

  test(
    'logout all uses the explicit all-session revocation endpoint',
    () async {
      final api = ApiClient(baseUrl: 'https://docmind.test/api/v1');
      final adapter = _RecordingAdapter();
      api.dio.httpClientAdapter = adapter;
      final repository = AccountRepository(api);

      await repository.logoutAll();

      expect(adapter.requests, hasLength(1));
      expect(adapter.requests.single.method, 'POST');
      expect(adapter.requests.single.path, '/auth/logout-all');
    },
  );
}
