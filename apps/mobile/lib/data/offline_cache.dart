import 'dart:convert';
import 'dart:io';

import 'package:path_provider/path_provider.dart';

class OfflineCache {
  Future<File> _file(String key) async {
    final dir = await getApplicationDocumentsDirectory();
    final safe = key.replaceAll(RegExp(r'[^a-zA-Z0-9_-]'), '_');
    return File('${dir.path}/docmind_$safe.json');
  }

  Future<void> writeJson(String key, Object value) async {
    final file = await _file(key);
    final temp = File('${file.path}.tmp');
    await temp.writeAsString(jsonEncode(value), flush: true);
    if (await file.exists()) await file.delete();
    await temp.rename(file.path);
  }

  Future<dynamic> readJson(String key) async {
    final file = await _file(key);
    if (!await file.exists()) return null;
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
    if (await file.exists()) await file.delete();
  }
}
