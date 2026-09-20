import 'dart:convert';
import 'dart:io';

import 'package:path_provider/path_provider.dart';

typedef CacheDirectoryProvider = Future<Directory> Function();

class OfflineCache {
  OfflineCache({CacheDirectoryProvider? directoryProvider})
      : _directoryProvider = directoryProvider ?? getApplicationDocumentsDirectory;

  final CacheDirectoryProvider _directoryProvider;
  String? _accountId;

  void useAccount(String accountId) {
    final value = accountId.trim();
    _accountId = value.isEmpty ? null : value;
  }

  void clearAccountContext() {
    _accountId = null;
  }

  String _safe(String value) => value.replaceAll(RegExp(r'[^a-zA-Z0-9_-]'), '_');

  Future<File?> _file(String key) async {
    final accountId = _accountId;
    if (accountId == null || accountId.isEmpty) return null;
    final dir = await _directoryProvider();
    await dir.create(recursive: true);
    return File('${dir.path}/docmind_${_safe(accountId)}_${_safe(key)}.json');
  }

  Future<void> writeJson(String key, Object value) async {
    final file = await _file(key);
    if (file == null) return;
    final temp = File('${file.path}.tmp');
    await temp.writeAsString(jsonEncode(value), flush: true);
    if (await file.exists()) await file.delete();
    await temp.rename(file.path);
  }

  Future<dynamic> readJson(String key) async {
    final file = await _file(key);
    if (file == null || !await file.exists()) return null;
    try {
      return jsonDecode(await file.readAsString());
    } on FormatException {
      return null;
    }
  }

  Future<List<Map<String, dynamic>>> readList(String key) async {
    final value = await readJson(key);
    if (value is! List) return [];
    return value.whereType<Map>().map((item) => Map<String, dynamic>.from(item)).toList();
  }

  Future<void> append(String key, Map<String, dynamic> item) async {
    final items = await readList(key);
    items.add(item);
    await writeJson(key, items);
  }

  Future<void> clear(String key) async {
    final file = await _file(key);
    if (file != null && await file.exists()) await file.delete();
  }

  Future<void> clearAccount(String accountId) async {
    final dir = await _directoryProvider();
    if (!await dir.exists()) return;
    final prefix = 'docmind_${_safe(accountId)}_';
    await for (final entity in dir.list()) {
      if (entity is! File) continue;
      final name = entity.path.split(Platform.pathSeparator).last;
      if (name.startsWith(prefix) && (name.endsWith('.json') || name.endsWith('.json.tmp'))) {
        await entity.delete();
      }
    }
  }

  Future<void> clearAll() async {
    final dir = await _directoryProvider();
    if (!await dir.exists()) return;
    await for (final entity in dir.list()) {
      if (entity is! File) continue;
      final name = entity.path.split(Platform.pathSeparator).last;
      if (name.startsWith('docmind_') && (name.endsWith('.json') || name.endsWith('.json.tmp'))) {
        await entity.delete();
      }
    }
  }
}
