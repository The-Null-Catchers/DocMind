import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../data/offline_cache.dart';
import 'api_client.dart';
import 'providers.dart';

bool _isOfflineError(Object error) {
  return error is DioException &&
      {
        DioExceptionType.connectionError,
        DioExceptionType.connectionTimeout,
        DioExceptionType.receiveTimeout,
        DioExceptionType.sendTimeout,
      }.contains(error.type);
}

class WorkspaceRepository {
  WorkspaceRepository(this._api, this._cache);
  final ApiClient _api;
  final OfflineCache _cache;

  Future<List<Map<String, dynamic>>> list() async {
    try {
      final response = await _api.dio.get('/workspaces');
      final rows = (response.data as List).map((e) => Map<String, dynamic>.from(e as Map)).toList();
      await _cache.writeJson('workspaces', rows);
      return rows;
    } catch (error) {
      if (_isOfflineError(error)) return _cache.readList('workspaces');
      rethrow;
    }
  }

  Future<Map<String, dynamic>> create(String name) async {
    final response = await _api.dio.post('/workspaces', data: {'name': name, 'kind': 'personal'});
    return Map<String, dynamic>.from(response.data as Map);
  }
}

class DocumentRepository {
  DocumentRepository(this._api, this._cache);
  final ApiClient _api;
  final OfflineCache _cache;

  String _key(String workspaceId) => 'documents_$workspaceId';

  Future<List<Map<String, dynamic>>> list(String workspaceId) async {
    try {
      final response = await _api.dio.get('/documents', queryParameters: {'workspace_id': workspaceId});
      final rows = (response.data as List).map((e) => Map<String, dynamic>.from(e as Map)).toList();
      await _cache.writeJson(_key(workspaceId), rows);
      return rows;
    } catch (error) {
      if (_isOfflineError(error)) return _cache.readList(_key(workspaceId));
      rethrow;
    }
  }

  Future<Map<String, dynamic>> get(String documentId) async {
    final response = await _api.dio.get('/documents/$documentId');
    return Map<String, dynamic>.from(response.data as Map);
  }

  Future<Map<String, dynamic>> page(String documentId, int pageNumber) async {
    final response = await _api.dio.get('/documents/$documentId/pages/$pageNumber');
    return Map<String, dynamic>.from(response.data as Map);
  }

  Future<Map<String, dynamic>> downloadSource(String documentId) async {
    final response = await _api.dio.get('/documents/$documentId/download-url');
    final raw = (response.data as Map)['url'] as String;
    if (raw.startsWith('http://') || raw.startsWith('https://')) {
      return {'url': raw, 'headers': <String, String>{}};
    }
    final base = Uri.parse(_api.dio.options.baseUrl);
    final url = base.replace(path: raw).toString();
    final token = await _api.accessToken();
    return {
      'url': url,
      'headers': token == null || token.isEmpty ? <String, String>{} : <String, String>{'Authorization': 'Bearer $token'},
    };
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

  Future<void> reprocess(String documentId) async {
    await _api.dio.post('/documents/$documentId/reprocess');
  }

  Future<void> delete(String documentId) async {
    await _api.dio.delete('/documents/$documentId');
  }

  Future<String> downloadUrl(String documentId) async {
    final response = await _api.dio.get('/documents/$documentId/download-url');
    final raw = (response.data as Map)['url'] as String;
    if (raw.startsWith('http://') || raw.startsWith('https://')) return raw;
    final base = Uri.parse(_api.dio.options.baseUrl);
    return base.replace(path: raw).toString();
  }
}

class ConversationRepository {
  ConversationRepository(this._api, this._cache);
  final ApiClient _api;
  final OfflineCache _cache;

  Future<List<Map<String, dynamic>>> list(String workspaceId) async {
    final key = 'conversations_$workspaceId';
    try {
      final response = await _api.dio.get('/conversations', queryParameters: {'workspace_id': workspaceId});
      final rows = (response.data as List).map((e) => Map<String, dynamic>.from(e as Map)).toList();
      await _cache.writeJson(key, rows);
      return rows;
    } catch (error) {
      if (_isOfflineError(error)) return _cache.readList(key);
      rethrow;
    }
  }

  Future<Map<String, dynamic>> create(String workspaceId, {List<String> documentIds = const []}) async {
    final response = await _api.dio.post('/conversations', data: {
      'workspace_id': workspaceId,
      'title': 'New conversation',
      'document_ids': documentIds,
    });
    return Map<String, dynamic>.from(response.data as Map);
  }

  Future<List<Map<String, dynamic>>> messages(String conversationId) async {
    final key = 'conversation_messages_$conversationId';
    try {
      final response = await _api.dio.get('/conversations/$conversationId/messages');
      final rows = (response.data as List).map((e) => Map<String, dynamic>.from(e as Map)).toList();
      await _cache.writeJson(key, rows);
      return rows;
    } catch (error) {
      if (_isOfflineError(error)) return _cache.readList(key);
      rethrow;
    }
  }

  Future<void> rename(String conversationId, String title) async {
    await _api.dio.patch('/conversations/$conversationId', data: {'title': title});
  }

  Future<Map<String, dynamic>> updateDocuments(String conversationId, List<String> documentIds) async {
    final response = await _api.dio.patch('/conversations/$conversationId', data: {'document_ids': documentIds});
    return Map<String, dynamic>.from(response.data as Map);
  }

  Future<void> delete(String conversationId) async {
    await _api.dio.delete('/conversations/$conversationId');
    await _cache.clear('conversation_messages_$conversationId');
  }

  Stream<Map<String, dynamic>> streamMessage(String conversationId, String message, {List<String> documentIds = const []}) async* {
    final response = await _api.dio.post<ResponseBody>(
      '/conversations/$conversationId/messages/stream',
      data: {'message': message, 'document_ids': documentIds, 'language': 'auto'},
      options: Options(responseType: ResponseType.stream, headers: {'Accept': 'text/event-stream'}),
    );
    final body = response.data;
    if (body == null) throw StateError('Empty streaming response');

    var event = 'message';
    await for (final line in body.stream.cast<List<int>>().transform(utf8.decoder).transform(const LineSplitter())) {
      if (line.startsWith('event:')) {
        event = line.substring(6).trim();
      } else if (line.startsWith('data:')) {
        final raw = line.substring(5).trim();
        if (raw.isEmpty) continue;
        yield {'event': event, 'data': jsonDecode(raw)};
      }
    }
  }
}

class StudyRepository {
  StudyRepository(this._api, this._cache);
  final ApiClient _api;
  final OfflineCache _cache;

  String _cardsKey(String workspaceId) => 'flashcards_due_$workspaceId';
  String _quizzesKey(String workspaceId) => 'quizzes_$workspaceId';
  String _notesKey(String workspaceId) => 'notes_$workspaceId';
  String _reviewsKey(String workspaceId) => 'pending_reviews_$workspaceId';

  Future<int> pendingReviewCount(String workspaceId) async => (await _cache.readList(_reviewsKey(workspaceId))).length;

  Future<void> syncPendingReviews(String workspaceId) async {
    final key = _reviewsKey(workspaceId);
    final pending = await _cache.readList(key);
    if (pending.isEmpty) return;
    final remaining = <Map<String, dynamic>>[];
    for (final review in pending) {
      try {
        await _api.dio.post('/flashcards/${review['card_id']}/review', data: {'rating': review['rating']});
      } catch (error) {
        remaining.add(review);
        if (_isOfflineError(error)) {
          final index = pending.indexOf(review);
          if (index + 1 < pending.length) remaining.addAll(pending.sublist(index + 1));
          break;
        }
      }
    }
    if (remaining.isEmpty) {
      await _cache.clear(key);
    } else {
      await _cache.writeJson(key, remaining);
    }
  }

  Future<List<Map<String, dynamic>>> dueCards(String workspaceId) async {
    try {
      await syncPendingReviews(workspaceId);
      final response = await _api.dio.get('/flashcards/due', queryParameters: {'workspace_id': workspaceId});
      final rows = (response.data as List).map((e) => Map<String, dynamic>.from(e as Map)).toList();
      await _cache.writeJson(_cardsKey(workspaceId), rows);
      return rows;
    } catch (error) {
      if (_isOfflineError(error)) return _cache.readList(_cardsKey(workspaceId));
      rethrow;
    }
  }

  Future<bool> reviewCard(String workspaceId, String cardId, String rating) async {
    try {
      await _api.dio.post('/flashcards/$cardId/review', data: {'rating': rating});
      return true;
    } catch (error) {
      if (!_isOfflineError(error)) rethrow;
      await _cache.append(_reviewsKey(workspaceId), {
        'card_id': cardId,
        'rating': rating,
        'created_at': DateTime.now().toUtc().toIso8601String(),
      });
      final cached = await _cache.readList(_cardsKey(workspaceId));
      cached.removeWhere((card) => card['id'] == cardId);
      await _cache.writeJson(_cardsKey(workspaceId), cached);
      return false;
    }
  }

  Future<List<Map<String, dynamic>>> quizzes(String workspaceId) async {
    try {
      final response = await _api.dio.get('/quizzes', queryParameters: {'workspace_id': workspaceId});
      final rows = (response.data as List).map((e) => Map<String, dynamic>.from(e as Map)).toList();
      await _cache.writeJson(_quizzesKey(workspaceId), rows);
      return rows;
    } catch (error) {
      if (_isOfflineError(error)) return _cache.readList(_quizzesKey(workspaceId));
      rethrow;
    }
  }

  Future<Map<String, dynamic>> quiz(String quizId) async {
    final key = 'quiz_$quizId';
    try {
      final response = await _api.dio.get('/quizzes/$quizId');
      final row = Map<String, dynamic>.from(response.data as Map);
      await _cache.writeJson(key, row);
      return row;
    } catch (error) {
      if (_isOfflineError(error)) {
        final cached = await _cache.readJson(key);
        if (cached is Map) return Map<String, dynamic>.from(cached);
      }
      rethrow;
    }
  }

  Future<Map<String, dynamic>> submitQuiz(String quizId, Map<String, String> answers) async {
    final response = await _api.dio.post('/quizzes/$quizId/attempts', data: {'answers': answers});
    return Map<String, dynamic>.from(response.data as Map);
  }

  Future<List<Map<String, dynamic>>> notes(String workspaceId) async {
    try {
      final response = await _api.dio.get('/notes', queryParameters: {'workspace_id': workspaceId});
      final rows = (response.data as List).map((e) => Map<String, dynamic>.from(e as Map)).toList();
      await _cache.writeJson(_notesKey(workspaceId), rows);
      return rows;
    } catch (error) {
      if (_isOfflineError(error)) return _cache.readList(_notesKey(workspaceId));
      rethrow;
    }
  }

  Future<Map<String, dynamic>> createNote(String workspaceId, String title, String content) async {
    final response = await _api.dio.post('/notes', data: {
      'workspace_id': workspaceId,
      'title': title,
      'content_markdown': content,
      'source_links': <Map<String, dynamic>>[],
    });
    return Map<String, dynamic>.from(response.data as Map);
  }
}

final workspaceRepositoryProvider = Provider((ref) => WorkspaceRepository(ref.watch(apiClientProvider), ref.watch(offlineCacheProvider)));
final documentRepositoryProvider = Provider((ref) => DocumentRepository(ref.watch(apiClientProvider), ref.watch(offlineCacheProvider)));
final conversationRepositoryProvider = Provider((ref) => ConversationRepository(ref.watch(apiClientProvider), ref.watch(offlineCacheProvider)));
final studyRepositoryProvider = Provider((ref) => StudyRepository(ref.watch(apiClientProvider), ref.watch(offlineCacheProvider)));
