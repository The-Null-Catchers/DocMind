import 'dart:convert';
import 'package:path_provider/path_provider.dart';
import 'dart:io';

/// Lightweight cache boundary used until generated Drift tables are introduced.
/// AI queries and uploads always require connectivity; study content can be read offline.
class OfflineCache {
  Future<File> _file(String key) async {
    final dir = await getApplicationDocumentsDirectory();
    final safe = key.replaceAll(RegExp(r'[^a-zA-Z0-9_-]'), '_');
    return File('${dir.path}/docmind_$safe.json');
  }
  Future<void> writeJson(String key, Object value) async => (await _file(key)).writeAsString(jsonEncode(value));
  Future<dynamic> readJson(String key) async {
    final file = await _file(key);
    if (!await file.exists()) return null;
    return jsonDecode(await file.readAsString());
  }
}
