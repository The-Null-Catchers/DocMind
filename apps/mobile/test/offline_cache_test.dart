import 'dart:io';

import 'package:docmind/data/offline_cache.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  late Directory directory;
  late OfflineCache cache;

  setUp(() async {
    directory = await Directory.systemTemp.createTemp('docmind-cache-test-');
    cache = OfflineCache(directoryProvider: () async => directory);
  });

  tearDown(() async {
    if (await directory.exists()) {
      await directory.delete(recursive: true);
    }
  });

  test('cached data is isolated between accounts', () async {
    cache.useAccount('user-a');
    await cache.writeJson('workspaces', [
      {'id': 'workspace-a'},
    ]);

    cache.useAccount('user-b');
    expect(await cache.readList('workspaces'), isEmpty);
    await cache.writeJson('workspaces', [
      {'id': 'workspace-b'},
    ]);

    cache.useAccount('user-a');
    expect((await cache.readList('workspaces')).single['id'], 'workspace-a');

    cache.useAccount('user-b');
    expect((await cache.readList('workspaces')).single['id'], 'workspace-b');
  });

  test(
    'clearing one account does not expose or delete another account cache',
    () async {
      cache.useAccount('user-a');
      await cache.writeJson('documents_workspace', [
        {'id': 'document-a'},
      ]);

      cache.useAccount('user-b');
      await cache.writeJson('documents_workspace', [
        {'id': 'document-b'},
      ]);

      await cache.clearAccount('user-a');

      cache.useAccount('user-a');
      expect(await cache.readList('documents_workspace'), isEmpty);

      cache.useAccount('user-b');
      expect(
        (await cache.readList('documents_workspace')).single['id'],
        'document-b',
      );
    },
  );

  test(
    'cache does not persist without an authenticated account namespace',
    () async {
      await cache.writeJson('workspaces', [
        {'id': 'should-not-persist'},
      ]);
      expect(await cache.readList('workspaces'), isEmpty);
      expect(await directory.list().toList(), isEmpty);
    },
  );
}
