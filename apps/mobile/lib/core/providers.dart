import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../data/offline_cache.dart';
import 'api_client.dart';

final apiClientProvider = Provider<ApiClient>((ref) => ApiClient());
final offlineCacheProvider = Provider<OfflineCache>((ref) => OfflineCache());
final selectedWorkspaceProvider = StateProvider<String?>((ref) => null);
