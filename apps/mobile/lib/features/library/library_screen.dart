import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/providers.dart';
import '../../core/repositories.dart';
import 'library_repository.dart';

class LibraryScreen extends ConsumerStatefulWidget {
  const LibraryScreen({super.key});

  @override
  ConsumerState<LibraryScreen> createState() => _LibraryScreenState();
}

class _LibraryScreenState extends ConsumerState<LibraryScreen> {
  List<Map<String, dynamic>> _collections = const [];
  List<Map<String, dynamic>> _folders = const [];
  List<Map<String, dynamic>> _tags = const [];
  List<Map<String, dynamic>> _prompts = const [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<String?> _workspace() async {
    var workspaceId = ref.read(selectedWorkspaceProvider);
    if (workspaceId != null) return workspaceId;
    final workspaces = await ref.read(workspaceRepositoryProvider).list();
    if (workspaces.isEmpty) return null;
    workspaceId = workspaces.first['id'] as String;
    ref.read(selectedWorkspaceProvider.notifier).state = workspaceId;
    return workspaceId;
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final workspaceId = await _workspace();
      if (workspaceId == null) {
        if (mounted) setState(() => _loading = false);
        return;
      }
      final repo = ref.read(libraryRepositoryProvider);
      final values = await Future.wait([
        repo.collections(workspaceId),
        repo.folders(workspaceId),
        repo.tags(workspaceId),
        repo.prompts(workspaceId),
      ]);
      if (!mounted) return;
      setState(() {
        _collections = values[0];
        _folders = values[1];
        _tags = values[2];
        _prompts = values[3];
        _loading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = 'Could not load library resources.';
      });
    }
  }

  Future<String?> _askName(String title, {String label = 'Name'}) async {
    final controller = TextEditingController();
    final value = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(title),
        content: TextField(
          controller: controller,
          autofocus: true,
          decoration: InputDecoration(labelText: label),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, controller.text.trim()),
            child: const Text('Create'),
          ),
        ],
      ),
    );
    controller.dispose();
    return value == null || value.isEmpty ? null : value;
  }

  Future<void> _create(String type) async {
    final workspaceId = await _workspace();
    if (!mounted || workspaceId == null) return;
    final repo = ref.read(libraryRepositoryProvider);
    try {
      if (type == 'collection') {
        final name = await _askName('New collection');
        if (name == null) return;
        await repo.createCollection(workspaceId, name);
      } else if (type == 'folder') {
        final name = await _askName('New folder');
        if (name == null) return;
        await repo.createFolder(workspaceId, name);
      } else if (type == 'tag') {
        final name = await _askName('New tag');
        if (name == null) return;
        await repo.createTag(workspaceId, name);
      } else if (type == 'prompt') {
        final nameController = TextEditingController();
        final promptController = TextEditingController();
        final create = await showDialog<bool>(
          context: context,
          builder: (context) => AlertDialog(
            title: const Text('New saved prompt'),
            content: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextField(
                  controller: nameController,
                  decoration: const InputDecoration(labelText: 'Name'),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: promptController,
                  minLines: 3,
                  maxLines: 8,
                  decoration: const InputDecoration(labelText: 'Prompt'),
                ),
              ],
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(context, false),
                child: const Text('Cancel'),
              ),
              FilledButton(
                onPressed: () => Navigator.pop(context, true),
                child: const Text('Save'),
              ),
            ],
          ),
        );
        if (create == true &&
            nameController.text.trim().isNotEmpty &&
            promptController.text.trim().isNotEmpty) {
          await repo.createPrompt(
            workspaceId,
            nameController.text,
            promptController.text,
          );
        }
        nameController.dispose();
        promptController.dispose();
      }
      await _load();
    } catch (_) {
      if (mounted)
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Could not save library item.')),
        );
    }
  }

  @override
  Widget build(BuildContext context) {
    return DefaultTabController(
      length: 4,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Library'),
          actions: [
            IconButton(
              onPressed: _load,
              tooltip: 'Refresh',
              icon: const Icon(Icons.refresh),
            ),
          ],
          bottom: const TabBar(
            isScrollable: true,
            tabs: [
              Tab(text: 'Collections'),
              Tab(text: 'Folders'),
              Tab(text: 'Tags'),
              Tab(text: 'Prompts'),
            ],
          ),
        ),
        body: _loading
            ? const Center(child: CircularProgressIndicator())
            : _error != null
            ? Center(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(_error!),
                    TextButton(onPressed: _load, child: const Text('Retry')),
                  ],
                ),
              )
            : TabBarView(
                children: [
                  _ResourceList(
                    items: _collections,
                    icon: Icons.collections_bookmark_outlined,
                    empty: 'No collections yet.',
                    onCreate: () => _create('collection'),
                  ),
                  _ResourceList(
                    items: _folders,
                    icon: Icons.folder_outlined,
                    empty: 'No folders yet.',
                    onCreate: () => _create('folder'),
                  ),
                  _ResourceList(
                    items: _tags,
                    icon: Icons.sell_outlined,
                    empty: 'No tags yet.',
                    onCreate: () => _create('tag'),
                  ),
                  _ResourceList(
                    items: _prompts,
                    icon: Icons.bolt_outlined,
                    empty: 'No saved prompts yet.',
                    onCreate: () => _create('prompt'),
                    subtitleKey: 'prompt',
                  ),
                ],
              ),
      ),
    );
  }
}

class _ResourceList extends StatelessWidget {
  const _ResourceList({
    required this.items,
    required this.icon,
    required this.empty,
    required this.onCreate,
    this.subtitleKey,
  });

  final List<Map<String, dynamic>> items;
  final IconData icon;
  final String empty;
  final VoidCallback onCreate;
  final String? subtitleKey;

  @override
  Widget build(BuildContext context) {
    return Stack(
      children: [
        if (items.isEmpty)
          Center(child: Text(empty))
        else
          ListView.builder(
            padding: const EdgeInsets.fromLTRB(12, 12, 12, 88),
            itemCount: items.length,
            itemBuilder: (context, index) {
              final item = items[index];
              final subtitle = subtitleKey == null
                  ? item['description']?.toString()
                  : item[subtitleKey]?.toString();
              return Card(
                child: ListTile(
                  leading: Icon(icon),
                  title: Text(item['name']?.toString() ?? 'Untitled'),
                  subtitle: subtitle == null || subtitle.isEmpty
                      ? null
                      : Text(
                          subtitle,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                        ),
                ),
              );
            },
          ),
        PositionedDirectional(
          end: 18,
          bottom: 18,
          child: FloatingActionButton.extended(
            onPressed: onCreate,
            icon: const Icon(Icons.add),
            label: const Text('New'),
          ),
        ),
      ],
    );
  }
}
