import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/providers.dart';
import '../../core/repositories.dart';
import '../auth/auth_controller.dart';

class HomeScreen extends ConsumerStatefulWidget {
  const HomeScreen({super.key});

  @override
  ConsumerState<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends ConsumerState<HomeScreen> {
  List<Map<String, dynamic>> _workspaces = const [];
  List<Map<String, dynamic>> _documents = const [];
  List<Map<String, dynamic>> _dueCards = const [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final workspaces = await ref.read(workspaceRepositoryProvider).list();
      var workspaceId = ref.read(selectedWorkspaceProvider);
      if (workspaceId == null && workspaces.isNotEmpty) {
        workspaceId = workspaces.first['id'] as String;
        ref.read(selectedWorkspaceProvider.notifier).state = workspaceId;
      }
      List<Map<String, dynamic>> documents = const [];
      List<Map<String, dynamic>> cards = const [];
      if (workspaceId != null) {
        final results = await Future.wait([
          ref.read(documentRepositoryProvider).list(workspaceId),
          ref.read(studyRepositoryProvider).dueCards(workspaceId),
        ]);
        documents = results[0];
        cards = results[1];
      }
      if (!mounted) return;
      setState(() {
        _workspaces = workspaces;
        _documents = documents;
        _dueCards = cards;
        _loading = false;
      });
    } catch (_) {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _createWorkspace() async {
    final controller = TextEditingController();
    final create = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Create workspace'),
        content: TextField(controller: controller, autofocus: true, decoration: const InputDecoration(labelText: 'Workspace name')),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Create')),
        ],
      ),
    );
    if (create == true && controller.text.trim().isNotEmpty) {
      try {
        final workspace = await ref.read(workspaceRepositoryProvider).create(controller.text.trim());
        ref.read(selectedWorkspaceProvider.notifier).state = workspace['id'] as String;
        await _load();
      } catch (_) {
        if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Could not create workspace.')));
      }
    }
    controller.dispose();
  }

  Future<void> _switchWorkspace(String? id) async {
    if (id == null) return;
    ref.read(selectedWorkspaceProvider.notifier).state = id;
    setState(() => _loading = true);
    await _load();
  }

  @override
  Widget build(BuildContext context) {
    final user = ref.watch(authControllerProvider).user;
    final selected = ref.watch(selectedWorkspaceProvider);
    final displayName = (user?['display_name']?.toString().trim().isNotEmpty ?? false)
        ? user!['display_name'].toString()
        : user?['email']?.toString().split('@').first ?? 'there';

    return RefreshIndicator(
      onRefresh: _load,
      child: CustomScrollView(slivers: [
        SliverAppBar.large(
          title: const Text('DocMind'),
          actions: [
            IconButton(onPressed: _createWorkspace, tooltip: 'Create workspace', icon: const Icon(Icons.add_business_outlined)),
            PopupMenuButton<String>(
              onSelected: (value) async {
                if (value == 'logout') await ref.read(authControllerProvider.notifier).logout();
              },
              itemBuilder: (_) => const [PopupMenuItem(value: 'logout', child: Text('Sign out'))],
              icon: const Icon(Icons.account_circle_outlined),
            ),
          ],
        ),
        SliverPadding(
          padding: const EdgeInsets.all(16),
          sliver: SliverList.list(children: [
            Text('Welcome, $displayName', style: Theme.of(context).textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.w700)),
            const SizedBox(height: 6),
            const Text('Turn your documents into searchable, cited knowledge.'),
            const SizedBox(height: 20),
            if (_workspaces.isEmpty && !_loading)
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(20),
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text('Create your first workspace', style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w700)),
                    const SizedBox(height: 8),
                    const Text('A workspace keeps documents, chats, notes, quizzes, and study cards isolated together.'),
                    const SizedBox(height: 16),
                    FilledButton.icon(onPressed: _createWorkspace, icon: const Icon(Icons.add), label: const Text('Create workspace')),
                  ]),
                ),
              )
            else if (_workspaces.isNotEmpty)
              DropdownButtonFormField<String>(
                initialValue: selected,
                decoration: const InputDecoration(labelText: 'Active workspace'),
                items: _workspaces.map((workspace) => DropdownMenuItem(value: workspace['id'] as String, child: Text(workspace['name'] as String))).toList(),
                onChanged: _switchWorkspace,
              ),
            const SizedBox(height: 16),
            if (_loading)
              const LinearProgressIndicator()
            else ...[
              Row(children: [
                Expanded(child: _Metric(title: 'Due now', value: '${_dueCards.length} cards', icon: Icons.psychology_alt_outlined, onTap: () => context.go('/study'))),
                const SizedBox(width: 12),
                Expanded(child: _Metric(title: 'Documents', value: '${_documents.length}', icon: Icons.description_outlined, onTap: () => context.go('/documents'))),
              ]),
              const SizedBox(height: 24),
              Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
                Text('Recent documents', style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700)),
                TextButton(onPressed: () => context.go('/documents'), child: const Text('View all')),
              ]),
              if (_documents.isEmpty)
                const Card(child: Padding(padding: EdgeInsets.all(20), child: Text('No documents yet. Upload your first file from the Documents tab.')))
              else
                ..._documents.take(5).map((document) => Card(
                      child: ListTile(
                        leading: const CircleAvatar(child: Icon(Icons.description_outlined)),
                        title: Text(document['title']?.toString() ?? document['original_filename']?.toString() ?? 'Document'),
                        subtitle: Text('${document['status'] ?? 'pending'} · ${document['processing_progress'] ?? 0}%'),
                        trailing: const Icon(Icons.chevron_right),
                        onTap: () => context.go('/documents'),
                      ),
                    )),
            ],
          ]),
        ),
      ]),
    );
  }
}

class _Metric extends StatelessWidget {
  const _Metric({required this.title, required this.value, required this.icon, required this.onTap});
  final String title;
  final String value;
  final IconData icon;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) => Card(
        child: InkWell(
          borderRadius: BorderRadius.circular(12),
          onTap: onTap,
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Icon(icon),
              const SizedBox(height: 24),
              Text(title, style: Theme.of(context).textTheme.labelMedium),
              const SizedBox(height: 4),
              Text(value, style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700)),
            ]),
          ),
        ),
      );
}
