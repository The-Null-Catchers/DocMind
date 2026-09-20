import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api_client.dart';
import '../../core/providers.dart';
import '../../data/offline_cache.dart';

class LibraryRepository {
  LibraryRepository(this._api, this._cache);

  final ApiClient _api;
  final OfflineCache _cache;

  Future<List<Map<String, dynamic>>> _list(String path, String workspaceId, String cacheKey) async {
    try {
      final response = await _api.dio.get(path, queryParameters: {'workspace_id': workspaceId});
      final rows = (response.data as List).map((item) => Map<String, dynamic>.from(item as Map)).toList();
      await _cache.writeJson('${cacheKey}_$workspaceId', rows);
      return rows;
    } catch (_) {
      final cached = await _cache.readList('${cacheKey}_$workspaceId');
      if (cached.isNotEmpty) return cached;
      rethrow;
    }
  }

  Future<List<Map<String, dynamic>>> collections(String workspaceId) => _list('/collections', workspaceId, 'collections');
  Future<List<Map<String, dynamic>>> folders(String workspaceId) => _list('/folders', workspaceId, 'folders');
  Future<List<Map<String, dynamic>>> tags(String workspaceId) => _list('/tags', workspaceId, 'tags');
  Future<List<Map<String, dynamic>>> prompts(String workspaceId) => _list('/saved-prompts', workspaceId, 'saved_prompts');

  Future<void> createCollection(String workspaceId, String name, {String? description}) async {
    await _api.dio.post('/collections', data: {
      'workspace_id': workspaceId,
      'name': name.trim(),
      'description': description?.trim(),
      'document_ids': <String>[],
    });
  }

  Future<void> createFolder(String workspaceId, String name) async {
    await _api.dio.post('/folders', data: {'workspace_id': workspaceId, 'name': name.trim()});
  }

  Future<void> createTag(String workspaceId, String name) async {
    await _api.dio.post('/tags', data: {'workspace_id': workspaceId, 'name': name.trim()});
  }

  Future<void> createPrompt(String workspaceId, String name, String prompt) async {
    await _api.dio.post('/saved-prompts', data: {
      'workspace_id': workspaceId,
      'name': name.trim(),
      'prompt': prompt.trim(),
    });
  }
}

final libraryRepositoryProvider = Provider((ref) => LibraryRepository(
      ref.watch(apiClientProvider),
      ref.watch(offlineCacheProvider),
    ));
