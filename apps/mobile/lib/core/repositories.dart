import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'api_client.dart';
import 'providers.dart';

class WorkspaceRepository {
  WorkspaceRepository(this._api);
  final ApiClient _api;

  Future<List<Map<String, dynamic>>> list() async {
    final response = await _api.dio.get('/workspaces');
    return (response.data as List).map((e) => Map<String, dynamic>.from(e as Map)).toList();
  }

  Future<Map<String, dynamic>> create(String name) async {
    final response = await _api.dio.post('/workspaces', data: {'name': name, 'kind': 'personal'});
    return Map<String, dynamic>.from(response.data as Map);
  }
}

class DocumentRepository {
  DocumentRepository(this._api);
  final ApiClient _api;

  Future<List<Map<String, dynamic>>> list(String workspaceId) async {
    final response = await _api.dio.get('/documents', queryParameters: {'workspace_id': workspaceId});
    return (response.data as List).map((e) => Map<String, dynamic>.from(e as Map)).toList();
  }

  Future<Map<String, dynamic>> upload({
    required String workspaceId,
    required String filename,
    required Uint8List bytes,
    required void Function(int sent, int total) onProgress,
  }) async {
    final form = FormData.fromMap({
      'workspace_id': workspaceId,
      'file': MultipartFile.fromBytes(bytes, filename: filename),
    });
    final response = await _api.dio.post('/documents/upload', data: form, onSendProgress: onProgress);
    return Map<String, dynamic>.from(response.data as Map);
  }

  Future<void> reprocess(String documentId) => _api.dio.post('/documents/$documentId/reprocess');
  Future<void> delete(String documentId) => _api.dio.delete('/documents/$documentId');

  Future<String> downloadUrl(String documentId) async {
    final response = await _api.dio.get('/documents/$documentId/download-url');
    final raw = (response.data as Map)['url'] as String;
    if (raw.startsWith('http://') || raw.startsWith('https://')) return raw;
    final base = Uri.parse(_api.dio.options.baseUrl);
    return base.replace(path: raw).toString();
  }
}

final workspaceRepositoryProvider = Provider((ref) => WorkspaceRepository(ref.watch(apiClientProvider)));
final documentRepositoryProvider = Provider((ref) => DocumentRepository(ref.watch(apiClientProvider)));
