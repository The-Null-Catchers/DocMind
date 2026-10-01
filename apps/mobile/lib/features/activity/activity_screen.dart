import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/providers.dart';
import '../../core/repositories.dart';

class ActivityScreen extends ConsumerStatefulWidget {
  const ActivityScreen({super.key});

  @override
  ConsumerState<ActivityScreen> createState() => _ActivityScreenState();
}

class _ActivityScreenState extends ConsumerState<ActivityScreen> {
  List<Map<String, dynamic>> _notifications = const [];
  List<Map<String, dynamic>> _invitations = const [];
  List<Map<String, dynamic>> _exports = const [];
  int _unread = 0;
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final repository = ref.read(activityRepositoryProvider);
      final workspaceId = ref.read(selectedWorkspaceProvider);
      final results = await Future.wait<dynamic>([
        repository.notifications(),
        repository.invitations(),
        if (workspaceId != null)
          repository.exports(workspaceId)
        else
          Future.value(<Map<String, dynamic>>[]),
      ]);
      final notificationPayload = Map<String, dynamic>.from(results[0] as Map);
      if (!mounted) return;
      setState(() {
        _notifications = (notificationPayload['items'] as List? ?? const [])
            .map((e) => Map<String, dynamic>.from(e as Map))
            .toList();
        _unread = (notificationPayload['unread'] as num?)?.toInt() ?? 0;
        _invitations = (results[1] as List)
            .map((e) => Map<String, dynamic>.from(e as Map))
            .toList();
        _exports = (results[2] as List)
            .map((e) => Map<String, dynamic>.from(e as Map))
            .toList();
        _loading = false;
        _error = null;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = ref.read(apiClientProvider).errorMessage(error);
      });
    }
  }

  Future<void> _markRead(String id) async {
    try {
      await ref.read(activityRepositoryProvider).markNotificationRead(id);
      await _load();
    } catch (error) {
      _showError(error);
    }
  }

  Future<void> _markAllRead() async {
    try {
      await ref.read(activityRepositoryProvider).markAllNotificationsRead();
      await _load();
    } catch (error) {
      _showError(error);
    }
  }

  Future<void> _acceptInvitation(String id) async {
    try {
      final result = await ref
          .read(activityRepositoryProvider)
          .acceptInvitation(id);
      final workspace = result['workspace'];
      if (workspace is Map && workspace['id'] is String) {
        ref.read(selectedWorkspaceProvider.notifier).state =
            workspace['id'] as String;
      }
      await _load();
    } catch (error) {
      _showError(error);
    }
  }

  Future<void> _rejectInvitation(String id) async {
    try {
      await ref.read(activityRepositoryProvider).rejectInvitation(id);
      await _load();
    } catch (error) {
      _showError(error);
    }
  }

  Future<void> _saveExport(Map<String, dynamic> job) async {
    try {
      final path = await ref
          .read(activityRepositoryProvider)
          .saveExport(
            job['id'] as String,
            job['filename']?.toString() ?? 'docmind-export',
          );
      if (!mounted) return;
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text('Export saved to $path')));
    } catch (error) {
      _showError(error);
    }
  }

  void _showError(Object error) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(ref.read(apiClientProvider).errorMessage(error))),
    );
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }
    if (_error != null) {
      return Scaffold(
        appBar: AppBar(title: const Text('Activity')),
        body: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(_error!),
              TextButton(onPressed: _load, child: const Text('Retry')),
            ],
          ),
        ),
      );
    }

    return DefaultTabController(
      length: 3,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Activity'),
          actions: [
            IconButton(
              onPressed: _load,
              tooltip: 'Refresh',
              icon: const Icon(Icons.refresh),
            ),
          ],
          bottom: const TabBar(
            tabs: [
              Tab(text: 'Notifications'),
              Tab(text: 'Invitations'),
              Tab(text: 'Exports'),
            ],
          ),
        ),
        body: TabBarView(
          children: [
            _NotificationsTab(
              items: _notifications,
              unread: _unread,
              onRead: _markRead,
              onReadAll: _markAllRead,
            ),
            _InvitationsTab(
              items: _invitations,
              onAccept: _acceptInvitation,
              onReject: _rejectInvitation,
            ),
            _ExportsTab(items: _exports, onSave: _saveExport),
          ],
        ),
      ),
    );
  }
}

class _NotificationsTab extends StatelessWidget {
  const _NotificationsTab({
    required this.items,
    required this.unread,
    required this.onRead,
    required this.onReadAll,
  });

  final List<Map<String, dynamic>> items;
  final int unread;
  final Future<void> Function(String id) onRead;
  final Future<void> Function() onReadAll;

  @override
  Widget build(BuildContext context) => RefreshIndicator(
    onRefresh: onReadAll,
    child: ListView(
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.all(16),
      children: [
        Row(
          children: [
            Expanded(
              child: Text(
                '$unread unread',
                style: Theme.of(context).textTheme.titleMedium,
              ),
            ),
            TextButton(
              onPressed: unread == 0 ? null : onReadAll,
              child: const Text('Mark all read'),
            ),
          ],
        ),
        const SizedBox(height: 8),
        if (items.isEmpty)
          const Card(
            child: Padding(
              padding: EdgeInsets.all(20),
              child: Text('No notifications yet.'),
            ),
          )
        else
          ...items.map((item) {
            final read = item['read'] == true;
            return Card(
              child: ListTile(
                leading: Icon(
                  read
                      ? Icons.notifications_none
                      : Icons.notifications_active_outlined,
                ),
                title: Text(item['title']?.toString() ?? 'Notification'),
                subtitle: Text(item['body']?.toString() ?? ''),
                trailing: read
                    ? null
                    : TextButton(
                        onPressed: () => onRead(item['id'] as String),
                        child: const Text('Read'),
                      ),
              ),
            );
          }),
      ],
    ),
  );
}

class _InvitationsTab extends StatelessWidget {
  const _InvitationsTab({
    required this.items,
    required this.onAccept,
    required this.onReject,
  });

  final List<Map<String, dynamic>> items;
  final Future<void> Function(String id) onAccept;
  final Future<void> Function(String id) onReject;

  @override
  Widget build(BuildContext context) {
    if (items.isEmpty) {
      return const Center(child: Text('No pending workspace invitations.'));
    }
    return ListView(
      padding: const EdgeInsets.all(16),
      children: items
          .map(
            (item) => Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      item['workspace_name']?.toString() ?? 'Shared workspace',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    const SizedBox(height: 4),
                    Text(
                      (item['role']?.toString() ?? 'viewer') +
                          ' · expires ' +
                          (item['expires_at']?.toString() ?? ''),
                    ),
                    const SizedBox(height: 12),
                    Wrap(
                      spacing: 8,
                      children: [
                        OutlinedButton(
                          onPressed: () => onReject(item['id'] as String),
                          child: const Text('Decline'),
                        ),
                        FilledButton(
                          onPressed: () => onAccept(item['id'] as String),
                          child: const Text('Accept'),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
          )
          .toList(),
    );
  }
}

class _ExportsTab extends StatelessWidget {
  const _ExportsTab({required this.items, required this.onSave});

  final List<Map<String, dynamic>> items;
  final Future<void> Function(Map<String, dynamic> item) onSave;

  @override
  Widget build(BuildContext context) {
    if (items.isEmpty) {
      return const Center(
        child: Padding(
          padding: EdgeInsets.all(24),
          child: Text('No exports for the active workspace yet.'),
        ),
      );
    }
    return ListView(
      padding: const EdgeInsets.all(16),
      children: items
          .map(
            (item) => Card(
              child: ListTile(
                leading: const Icon(Icons.file_download_outlined),
                title: Text(
                  item['filename']?.toString() ??
                      item['kind']?.toString() ??
                      'Export',
                ),
                subtitle: Text(
                  item['status'] == 'failed'
                      ? 'Failed · ' +
                            (item['error_message']?.toString() ??
                                'Unknown error')
                      : item['status']?.toString() ?? 'pending',
                ),
                trailing: item['status'] == 'ready'
                    ? FilledButton.tonalIcon(
                        onPressed: () => onSave(item),
                        icon: const Icon(Icons.download, size: 18),
                        label: const Text('Save'),
                      )
                    : null,
              ),
            ),
          )
          .toList(),
    );
  }
}
