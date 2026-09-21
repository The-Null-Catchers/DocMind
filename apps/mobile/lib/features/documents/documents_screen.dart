import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/providers.dart';
import '../../core/repositories.dart';

class DocumentsScreen extends ConsumerStatefulWidget {
  const DocumentsScreen({super.key});

  @override
  ConsumerState<DocumentsScreen> createState() => _DocumentsScreenState();
}

class _DocumentsScreenState extends ConsumerState<DocumentsScreen> {
  final _search = TextEditingController();
  List<Map<String, dynamic>> _documents = const [];
  List<Map<String, dynamic>> _workspaces = const [];
  bool _loading = true;
  bool _uploading = false;
  double _uploadProgress = 0;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
    _search.addListener(() => setState(() {}));
  }

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final workspaceRepo = ref.read(workspaceRepositoryProvider);
      final documentRepo = ref.read(documentRepositoryProvider);
      final workspaces = await workspaceRepo.list();
      var selected = ref.read(selectedWorkspaceProvider);
      if (selected == null && workspaces.isNotEmpty) {
        selected = workspaces.first['id'] as String;
        ref.read(selectedWorkspaceProvider.notifier).state = selected;
      }
      final documents = selected == null
          ? <Map<String, dynamic>>[]
          : await documentRepo.list(selected);
      if (!mounted) return;
      setState(() {
        _workspaces = workspaces;
        _documents = documents;
        _loading = false;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _error = 'Could not load documents.';
        _loading = false;
      });
    }
  }

  Future<void> _switchWorkspace(String? workspaceId) async {
    if (workspaceId == null) return;
    ref.read(selectedWorkspaceProvider.notifier).state = workspaceId;
    await _load();
  }

  Future<void> _pick() async {
    final workspaceId = ref.read(selectedWorkspaceProvider);
    if (workspaceId == null) {
      _showMessage('Create a workspace before uploading documents.');
      return;
    }
    final files = await FilePicker.pickFiles();
    if (files.isEmpty) return;

    setState(() {
      _uploading = true;
      _uploadProgress = 0;
    });
    try {
      for (var index = 0; index < files.length; index++) {
        final file = files[index];
        final bytes = await file.readAsBytes();
        await ref
            .read(documentRepositoryProvider)
            .upload(
              workspaceId: workspaceId,
              filename: file.name,
              bytes: bytes,
              onProgress: (sent, total) {
                if (!mounted || total <= 0) return;
                setState(
                  () => _uploadProgress = (index + sent / total) / files.length,
                );
              },
            );
      }
      await _load();
    } catch (error) {
      _showMessage('Upload failed. Check the file type, size, and connection.');
    } finally {
      if (mounted) setState(() => _uploading = false);
    }
  }

  Future<void> _reprocess(Map<String, dynamic> document) async {
    try {
      await ref
          .read(documentRepositoryProvider)
          .reprocess(document['id'] as String);
      await _load();
    } catch (_) {
      _showMessage('Could not restart processing.');
    }
  }

  Future<void> _delete(Map<String, dynamic> document) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete document?'),
        content: Text('Delete “${document['title']}” and its indexed content?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Delete'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    try {
      await ref
          .read(documentRepositoryProvider)
          .delete(document['id'] as String);
      await _load();
    } catch (_) {
      _showMessage('Could not delete the document.');
    }
  }

  void _showMessage(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(SnackBar(content: Text(message)));
  }

  @override
  Widget build(BuildContext context) {
    final selected = ref.watch(selectedWorkspaceProvider);
    final query = _search.text.trim().toLowerCase();
    final visible = _documents.where((doc) {
      if (query.isEmpty) return true;
      return '${doc['title']} ${doc['original_filename']}'
          .toLowerCase()
          .contains(query);
    }).toList();

    return Scaffold(
      appBar: AppBar(
        title: const Text('Documents'),
        actions: [
          IconButton(
            onPressed: _loading ? null : _load,
            tooltip: 'Refresh',
            icon: const Icon(Icons.refresh),
          ),
          IconButton(
            onPressed: _uploading ? null : _pick,
            tooltip: 'Upload documents',
            icon: const Icon(Icons.upload_file),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _load,
        child: ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.all(16),
          children: [
            if (_workspaces.isNotEmpty)
              DropdownButtonFormField<String>(
                initialValue: selected,
                decoration: const InputDecoration(labelText: 'Workspace'),
                items: _workspaces
                    .map(
                      (workspace) => DropdownMenuItem(
                        value: workspace['id'] as String,
                        child: Text(workspace['name'] as String),
                      ),
                    )
                    .toList(),
                onChanged: _switchWorkspace,
              ),
            const SizedBox(height: 12),
            SearchBar(
              controller: _search,
              leading: const Icon(Icons.search),
              hintText: 'Search documents',
            ),
            if (_uploading) ...[
              const SizedBox(height: 14),
              LinearProgressIndicator(value: _uploadProgress),
              const SizedBox(height: 6),
              Text('Uploading ${(_uploadProgress * 100).round()}%'),
            ],
            const SizedBox(height: 14),
            if (_loading)
              const Center(
                child: Padding(
                  padding: EdgeInsets.all(32),
                  child: CircularProgressIndicator(),
                ),
              )
            else if (_error != null)
              _EmptyState(
                icon: Icons.cloud_off_outlined,
                title: _error!,
                action: TextButton(
                  onPressed: _load,
                  child: const Text('Retry'),
                ),
              )
            else if (selected == null)
              const _EmptyState(
                icon: Icons.workspaces_outline,
                title: 'No workspace yet',
              )
            else if (visible.isEmpty)
              _EmptyState(
                icon: Icons.description_outlined,
                title: query.isEmpty
                    ? 'No documents yet'
                    : 'No matching documents',
                action: query.isEmpty
                    ? FilledButton.icon(
                        onPressed: _pick,
                        icon: const Icon(Icons.add),
                        label: const Text('Upload'),
                      )
                    : null,
              )
            else
              ...visible.map(
                (document) => _DocumentCard(
                  document: document,
                  onReprocess: () => _reprocess(document),
                  onDelete: () => _delete(document),
                ),
              ),
          ],
        ),
      ),
      floatingActionButton: selected == null
          ? null
          : FloatingActionButton.extended(
              onPressed: _uploading ? null : _pick,
              icon: const Icon(Icons.add),
              label: const Text('Upload'),
            ),
    );
  }
}

class _DocumentCard extends StatelessWidget {
  const _DocumentCard({
    required this.document,
    required this.onReprocess,
    required this.onDelete,
  });
  final Map<String, dynamic> document;
  final VoidCallback onReprocess;
  final VoidCallback onDelete;

  @override
  Widget build(BuildContext context) {
    final status = (document['status'] ?? 'pending').toString();
    final progress = (document['processing_progress'] as num?)?.toInt() ?? 0;
    final pages = document['page_count'];
    final ready = status == 'ready';
    final failed = status == 'failed';
    return Card(
      child: ListTile(
        onTap: ready
            ? () => context.push('/documents/${document['id']}')
            : null,
        leading: Icon(
          ready
              ? Icons.description
              : failed
              ? Icons.error_outline
              : Icons.sync,
        ),
        title: Text(
          document['title']?.toString() ??
              document['original_filename']?.toString() ??
              'Document',
        ),
        subtitle: Text(
          ready
              ? 'Ready${pages == null ? '' : ' · $pages pages'}'
              : failed
              ? 'Processing failed'
              : '${status.toUpperCase()} · $progress%',
        ),
        trailing: PopupMenuButton<String>(
          onSelected: (value) {
            if (value == 'reprocess') onReprocess();
            if (value == 'delete') onDelete();
          },
          itemBuilder: (_) => [
            if (!ready)
              const PopupMenuItem(value: 'reprocess', child: Text('Reprocess')),
            const PopupMenuItem(value: 'delete', child: Text('Delete')),
          ],
        ),
      ),
    );
  }
}

class _EmptyState extends StatelessWidget {
  const _EmptyState({required this.icon, required this.title, this.action});
  final IconData icon;
  final String title;
  final Widget? action;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 36),
    child: Column(
      children: [
        Icon(icon, size: 42),
        const SizedBox(height: 12),
        Text(title),
        if (action != null) ...[const SizedBox(height: 12), action!],
      ],
    ),
  );
}
