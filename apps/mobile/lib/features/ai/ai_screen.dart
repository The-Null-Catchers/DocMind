import 'package:flutter/material.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/providers.dart';
import '../../core/repositories.dart';

class AiScreen extends ConsumerStatefulWidget {
  const AiScreen({super.key});

  @override
  ConsumerState<AiScreen> createState() => _AiScreenState();
}

class _AiScreenState extends ConsumerState<AiScreen> {
  final _controller = TextEditingController();
  final _scrollController = ScrollController();
  List<Map<String, dynamic>> _workspaces = const [];
  List<Map<String, dynamic>> _conversations = const [];
  List<Map<String, dynamic>> _messages = const [];
  String? _conversationId;
  bool _loading = true;
  bool _sending = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _bootstrap();
  }

  @override
  void dispose() {
    _controller.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  Future<void> _bootstrap() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final workspaces = await ref.read(workspaceRepositoryProvider).list();
      var workspaceId = ref.read(selectedWorkspaceProvider);
      if (workspaceId == null && workspaces.isNotEmpty) {
        workspaceId = workspaces.first['id'] as String;
        ref.read(selectedWorkspaceProvider.notifier).state = workspaceId;
      }
      List<Map<String, dynamic>> conversations = const [];
      if (workspaceId != null) {
        conversations = await ref.read(conversationRepositoryProvider).list(workspaceId);
      }
      if (!mounted) return;
      setState(() {
        _workspaces = workspaces;
        _conversations = conversations;
        _loading = false;
      });
      if (conversations.isNotEmpty) {
        await _selectConversation(conversations.first['id'] as String);
      }
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = 'Could not load conversations.';
      });
    }
  }

  Future<void> _switchWorkspace(String? workspaceId) async {
    if (workspaceId == null) return;
    ref.read(selectedWorkspaceProvider.notifier).state = workspaceId;
    setState(() {
      _conversationId = null;
      _messages = const [];
      _conversations = const [];
    });
    try {
      final conversations = await ref.read(conversationRepositoryProvider).list(workspaceId);
      if (!mounted) return;
      setState(() => _conversations = conversations);
      if (conversations.isNotEmpty) await _selectConversation(conversations.first['id'] as String);
    } catch (_) {
      _showMessage('Could not switch workspace.');
    }
  }

  Future<void> _newConversation() async {
    final workspaceId = ref.read(selectedWorkspaceProvider);
    if (workspaceId == null) {
      _showMessage('Create a workspace before starting a chat.');
      return;
    }
    try {
      final created = await ref.read(conversationRepositoryProvider).create(workspaceId);
      if (!mounted) return;
      setState(() {
        _conversations = [created, ..._conversations];
        _conversationId = created['id'] as String;
        _messages = const [];
      });
    } catch (_) {
      _showMessage('Could not start a conversation.');
    }
  }

  Future<void> _selectConversation(String id) async {
    setState(() {
      _conversationId = id;
      _loading = true;
    });
    try {
      final messages = await ref.read(conversationRepositoryProvider).messages(id);
      if (!mounted || _conversationId != id) return;
      setState(() {
        _messages = messages;
        _loading = false;
      });
      _scrollToBottom();
    } catch (_) {
      if (!mounted) return;
      setState(() => _loading = false);
      _showMessage('Could not load conversation history.');
    }
  }

  Future<void> _send() async {
    final text = _controller.text.trim();
    if (text.isEmpty || _sending) return;
    if (_conversationId == null) await _newConversation();
    final conversationId = _conversationId;
    if (conversationId == null) return;

    _controller.clear();
    final userMessage = <String, dynamic>{'role': 'user', 'content': text, 'citations': const []};
    final assistantMessage = <String, dynamic>{'role': 'assistant', 'content': '', 'citations': <dynamic>[], 'status': 'streaming'};
    setState(() {
      _sending = true;
      _messages = [..._messages, userMessage, assistantMessage];
    });
    _scrollToBottom();

    try {
      await for (final event in ref.read(conversationRepositoryProvider).streamMessage(conversationId, text)) {
        if (!mounted) return;
        final type = event['event'];
        final data = event['data'];
        if (type == 'token' && data is Map) {
          assistantMessage['content'] = '${assistantMessage['content']}${data['text'] ?? ''}';
        } else if (type == 'citations' && data is List) {
          assistantMessage['citations'] = data;
        } else if (type == 'status' && data is Map) {
          assistantMessage['status'] = data['status']?.toString();
        } else if (type == 'done' && data is Map) {
          assistantMessage['id'] = data['message_id'];
          assistantMessage['status'] = 'complete';
        } else if (type == 'error') {
          throw StateError('Generation failed');
        }
        setState(() => _messages = [..._messages]);
        _scrollToBottom();
      }
    } catch (_) {
      assistantMessage['status'] = 'failed';
      assistantMessage['content'] = (assistantMessage['content'] as String).isEmpty
          ? 'The answer could not be generated. Your question is saved; please try again.'
          : assistantMessage['content'];
      if (mounted) setState(() => _messages = [..._messages]);
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!_scrollController.hasClients) return;
      _scrollController.animateTo(
        _scrollController.position.maxScrollExtent,
        duration: const Duration(milliseconds: 220),
        curve: Curves.easeOut,
      );
    });
  }

  void _showMessage(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message)));
  }

  @override
  Widget build(BuildContext context) {
    final workspaceId = ref.watch(selectedWorkspaceProvider);
    return Scaffold(
      appBar: AppBar(
        title: const Text('Ask DocMind'),
        actions: [
          IconButton(onPressed: _newConversation, tooltip: 'New conversation', icon: const Icon(Icons.add_comment_outlined)),
        ],
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(56),
          child: Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
            child: DropdownButtonFormField<String>(
              initialValue: workspaceId,
              decoration: const InputDecoration(labelText: 'Workspace', isDense: true),
              items: _workspaces.map((workspace) => DropdownMenuItem(value: workspace['id'] as String, child: Text(workspace['name'] as String))).toList(),
              onChanged: _sending ? null : _switchWorkspace,
            ),
          ),
        ),
      ),
      body: Column(children: [
        if (_conversations.isNotEmpty)
          SizedBox(
            height: 48,
            child: ListView.separated(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
              scrollDirection: Axis.horizontal,
              itemCount: _conversations.length,
              separatorBuilder: (_, __) => const SizedBox(width: 8),
              itemBuilder: (context, index) {
                final conversation = _conversations[index];
                final id = conversation['id'] as String;
                return ChoiceChip(
                  selected: id == _conversationId,
                  label: Text(conversation['title']?.toString() ?? 'Conversation'),
                  onSelected: (_) => _selectConversation(id),
                );
              },
            ),
          ),
        Expanded(
          child: _loading
              ? const Center(child: CircularProgressIndicator())
              : _error != null
                  ? Center(child: Text(_error!))
                  : _messages.isEmpty
                      ? _EmptyChat(onStart: _newConversation)
                      : ListView.builder(
                          controller: _scrollController,
                          padding: const EdgeInsets.all(16),
                          itemCount: _messages.length,
                          itemBuilder: (context, index) => _MessageBubble(message: _messages[index]),
                        ),
        ),
        SafeArea(
          top: false,
          child: Padding(
            padding: const EdgeInsets.fromLTRB(12, 8, 12, 12),
            child: TextField(
              controller: _controller,
              minLines: 1,
              maxLines: 5,
              textInputAction: TextInputAction.newline,
              decoration: InputDecoration(
                hintText: workspaceId == null ? 'Select a workspace first' : 'Ask across your documents…',
                suffixIcon: IconButton(onPressed: _sending || workspaceId == null ? null : _send, icon: Icon(_sending ? Icons.hourglass_top : Icons.arrow_upward)),
              ),
            ),
          ),
        ),
      ]),
    );
  }
}

class _MessageBubble extends StatelessWidget {
  const _MessageBubble({required this.message});
  final Map<String, dynamic> message;

  @override
  Widget build(BuildContext context) {
    final isUser = message['role'] == 'user';
    final content = message['content']?.toString() ?? '';
    final citations = (message['citations'] as List?) ?? const [];
    final failed = message['status'] == 'failed';
    return Align(
      alignment: isUser ? AlignmentDirectional.centerEnd : AlignmentDirectional.centerStart,
      child: Container(
        constraints: const BoxConstraints(maxWidth: 720),
        margin: const EdgeInsets.only(bottom: 14),
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: isUser ? Theme.of(context).colorScheme.primary : Theme.of(context).colorScheme.surfaceContainerHighest,
          borderRadius: BorderRadius.circular(18),
        ),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          if (isUser)
            Text(content, style: TextStyle(color: Theme.of(context).colorScheme.onPrimary))
          else if (content.isEmpty)
            const Padding(padding: EdgeInsets.symmetric(vertical: 4), child: LinearProgressIndicator())
          else
            MarkdownBody(data: content),
          if (failed) ...[
            const SizedBox(height: 8),
            Text('Generation interrupted', style: TextStyle(color: Theme.of(context).colorScheme.error, fontSize: 12)),
          ],
          if (!isUser && citations.isNotEmpty) ...[
            const Divider(height: 24),
            ...citations.map((raw) {
              final citation = Map<String, dynamic>.from(raw as Map);
              final page = citation['page_number'];
              final documentId = citation['document_id']?.toString();
              return ListTile(
                dense: true,
                onTap: documentId == null ? null : () => context.push('/documents/$documentId?page=${page ?? 1}'),
                contentPadding: EdgeInsets.zero,
                leading: CircleAvatar(radius: 13, child: Text('${citation['ordinal'] ?? ''}')),
                title: Text(page == null ? 'Source' : 'Source · page $page'),
                subtitle: Text(citation['source_excerpt']?.toString() ?? '', maxLines: 3, overflow: TextOverflow.ellipsis),
              );
            }),
          ],
        ]),
      ),
    );
  }
}

class _EmptyChat extends StatelessWidget {
  const _EmptyChat({required this.onStart});
  final VoidCallback onStart;

  @override
  Widget build(BuildContext context) => Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            const Icon(Icons.auto_awesome_outlined, size: 46),
            const SizedBox(height: 12),
            Text('Ask questions grounded in your documents', textAlign: TextAlign.center, style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 12),
            FilledButton.icon(onPressed: onStart, icon: const Icon(Icons.add), label: const Text('New conversation')),
          ]),
        ),
      );
}
