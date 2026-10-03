import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:docmind/core/api_client.dart';
import 'package:docmind/core/repositories.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';

class _ActivityAdapter implements HttpClientAdapter {
  final List<RequestOptions> requests = [];

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    requests.add(options);
    final path = options.path;
    if (path == '/notifications') {
      return _json({
        'items': [
          {
            'id': 'notification-1',
            'title': 'Ready',
            'body': 'Document ready',
            'read': false,
          },
        ],
        'unread': 1,
      });
    }
    if (path == '/workspace-invitations' && options.method == 'GET') {
      return _json([
        {'id': 'invite-1', 'workspace_name': 'Shared', 'role': 'viewer'},
      ]);
    }
    if (path == '/workspace-invitations/invite-1/accept') {
      return _json({
        'workspace': {'id': 'workspace-2', 'name': 'Shared'},
      });
    }
    if (path == '/exports') {
      return _json([
        {'id': 'export-1', 'status': 'ready', 'filename': 'notes.md'},
      ]);
    }
    return ResponseBody.fromString('', 204);
  }

  ResponseBody _json(Object value) => ResponseBody.fromString(
    jsonEncode(value),
    200,
    headers: {
      Headers.contentTypeHeader: ['application/json'],
    },
  );

  @override
  void close({bool force = false}) {}
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    FlutterSecureStorage.setMockInitialValues({});
  });

  test(
    'activity repository loads notifications invitations and exports',
    () async {
      final api = ApiClient(baseUrl: 'https://docmind.test/api/v1');
      final adapter = _ActivityAdapter();
      api.dio.httpClientAdapter = adapter;
      final repository = ActivityRepository(api);

      final notifications = await repository.notifications();
      final invitations = await repository.invitations();
      final exports = await repository.exports('workspace-1');

      expect(notifications['unread'], 1);
      expect((notifications['items'] as List).single['id'], 'notification-1');
      expect(invitations.single['id'], 'invite-1');
      expect(exports.single['id'], 'export-1');
      expect(
        adapter.requests.last.queryParameters['workspace_id'],
        'workspace-1',
      );
    },
  );

  test(
    'activity repository accepts and rejects invitations explicitly',
    () async {
      final api = ApiClient(baseUrl: 'https://docmind.test/api/v1');
      final adapter = _ActivityAdapter();
      api.dio.httpClientAdapter = adapter;
      final repository = ActivityRepository(api);

      final accepted = await repository.acceptInvitation('invite-1');
      await repository.rejectInvitation('invite-1');

      expect((accepted['workspace'] as Map)['id'], 'workspace-2');
      expect(
        adapter.requests.map((request) => request.path),
        containsAll([
          '/workspace-invitations/invite-1/accept',
          '/workspace-invitations/invite-1/reject',
        ]),
      );
    },
  );
}
