import 'package:flutter/material.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/providers.dart';
import '../../core/repositories.dart';

class StudyScreen extends ConsumerStatefulWidget {
  const StudyScreen({super.key});

  @override
  ConsumerState<StudyScreen> createState() => _StudyScreenState();
}

class _StudyScreenState extends ConsumerState<StudyScreen> {
  List<Map<String, dynamic>> _cards = const [];
  List<Map<String, dynamic>> _quizzes = const [];
  List<Map<String, dynamic>> _notes = const [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    var workspaceId = ref.read(selectedWorkspaceProvider);
    try {
      if (workspaceId == null) {
        final workspaces = await ref.read(workspaceRepositoryProvider).list();
        if (workspaces.isNotEmpty) {
          workspaceId = workspaces.first['id'] as String;
          ref.read(selectedWorkspaceProvider.notifier).state = workspaceId;
        }
      }
      if (workspaceId == null) {
        if (mounted) setState(() => _loading = false);
        return;
      }
      final repo = ref.read(studyRepositoryProvider);
      final results = await Future.wait([
        repo.dueCards(workspaceId),
        repo.quizzes(workspaceId),
        repo.notes(workspaceId),
      ]);
      if (!mounted) return;
      setState(() {
        _cards = results[0];
        _quizzes = results[1];
        _notes = results[2];
        _loading = false;
        _error = null;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = 'Could not load study data.';
      });
    }
  }

  Future<void> _reviewCard(Map<String, dynamic> card) async {
    var revealed = false;
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      builder: (context) => StatefulBuilder(builder: (context, setSheetState) {
        return SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              Text(card['front']?.toString() ?? '', style: Theme.of(context).textTheme.titleLarge),
              const SizedBox(height: 24),
              if (!revealed)
                FilledButton(onPressed: () => setSheetState(() => revealed = true), child: const Text('Show answer'))
              else ...[
                MarkdownBody(data: card['back']?.toString() ?? ''),
                const SizedBox(height: 20),
                Wrap(
                  alignment: WrapAlignment.spaceBetween,
                  spacing: 8,
                  runSpacing: 8,
                  children: ['again', 'hard', 'good', 'easy'].map((rating) => OutlinedButton(
                    onPressed: () async {
                      await ref.read(studyRepositoryProvider).reviewCard(card['id'] as String, rating);
                      if (context.mounted) Navigator.pop(context);
                    },
                    child: Text(rating[0].toUpperCase() + rating.substring(1)),
                  )).toList(),
                ),
              ],
            ]),
          ),
        );
      }),
    );
    await _load();
  }

  Future<void> _openQuiz(Map<String, dynamic> quizSummary) async {
    try {
      final quiz = await ref.read(studyRepositoryProvider).quiz(quizSummary['id'] as String);
      if (!mounted) return;
      await Navigator.of(context).push(MaterialPageRoute(builder: (_) => _QuizScreen(quiz: quiz)));
    } catch (_) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Could not load quiz.')));
    }
  }

  Future<void> _createNote() async {
    final workspaceId = ref.read(selectedWorkspaceProvider);
    if (workspaceId == null) return;
    final title = TextEditingController();
    final content = TextEditingController();
    final created = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('New note'),
        content: SizedBox(
          width: 460,
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            TextField(controller: title, decoration: const InputDecoration(labelText: 'Title')),
            const SizedBox(height: 12),
            TextField(controller: content, minLines: 4, maxLines: 10, decoration: const InputDecoration(labelText: 'Markdown note')),
          ]),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Save')),
        ],
      ),
    );
    if (created == true && title.text.trim().isNotEmpty) {
      await ref.read(studyRepositoryProvider).createNote(workspaceId, title.text.trim(), content.text);
      await _load();
    }
    title.dispose();
    content.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) return const Scaffold(body: Center(child: CircularProgressIndicator()));
    if (_error != null) return Scaffold(appBar: AppBar(title: const Text('Study')), body: Center(child: Column(mainAxisSize: MainAxisSize.min, children: [Text(_error!), TextButton(onPressed: _load, child: const Text('Retry'))])));

    return DefaultTabController(
      length: 3,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Study'),
          actions: [IconButton(onPressed: _load, tooltip: 'Refresh', icon: const Icon(Icons.refresh))],
          bottom: const TabBar(tabs: [Tab(text: 'Flashcards'), Tab(text: 'Quizzes'), Tab(text: 'Notes')]),
        ),
        body: TabBarView(children: [
          _CardsTab(cards: _cards, onReview: _reviewCard),
          _QuizzesTab(quizzes: _quizzes, onOpen: _openQuiz),
          _NotesTab(notes: _notes, onCreate: _createNote),
        ]),
      ),
    );
  }
}

class _CardsTab extends StatelessWidget {
  const _CardsTab({required this.cards, required this.onReview});
  final List<Map<String, dynamic>> cards;
  final Future<void> Function(Map<String, dynamic>) onReview;

  @override
  Widget build(BuildContext context) => ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Card(
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                const Text('DUE NOW'),
                const SizedBox(height: 12),
                Text('${cards.length} cards', style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.bold)),
                const SizedBox(height: 16),
                FilledButton(onPressed: cards.isEmpty ? null : () => onReview(cards.first), child: const Text('Start review')),
              ]),
            ),
          ),
          const SizedBox(height: 12),
          ...cards.take(20).map((card) => Card(child: ListTile(title: Text(card['front']?.toString() ?? ''), trailing: const Icon(Icons.chevron_right), onTap: () => onReview(card)))),
        ],
      );
}

class _QuizzesTab extends StatelessWidget {
  const _QuizzesTab({required this.quizzes, required this.onOpen});
  final List<Map<String, dynamic>> quizzes;
  final Future<void> Function(Map<String, dynamic>) onOpen;

  @override
  Widget build(BuildContext context) {
    if (quizzes.isEmpty) return const Center(child: Padding(padding: EdgeInsets.all(24), child: Text('No quizzes yet. Generate one from selected documents on the web or API.')));
    return ListView(padding: const EdgeInsets.all(16), children: quizzes.map((quiz) => Card(child: ListTile(title: Text(quiz['title']?.toString() ?? 'Quiz'), subtitle: Text('${quiz['difficulty'] ?? 'medium'} · ${quiz['language'] ?? 'en'}'), trailing: const Icon(Icons.chevron_right), onTap: () => onOpen(quiz)))).toList());
  }
}

class _NotesTab extends StatelessWidget {
  const _NotesTab({required this.notes, required this.onCreate});
  final List<Map<String, dynamic>> notes;
  final VoidCallback onCreate;

  @override
  Widget build(BuildContext context) => Scaffold(
        body: notes.isEmpty
            ? const Center(child: Text('No notes yet.'))
            : ListView(padding: const EdgeInsets.all(16), children: notes.map((note) => Card(child: ExpansionTile(title: Text(note['title']?.toString() ?? 'Note'), childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 16), children: [Align(alignment: AlignmentDirectional.centerStart, child: MarkdownBody(data: note['content_markdown']?.toString() ?? ''))]))).toList()),
        floatingActionButton: FloatingActionButton.extended(onPressed: onCreate, icon: const Icon(Icons.note_add_outlined), label: const Text('Note')),
      );
}

class _QuizScreen extends ConsumerStatefulWidget {
  const _QuizScreen({required this.quiz});
  final Map<String, dynamic> quiz;

  @override
  ConsumerState<_QuizScreen> createState() => _QuizScreenState();
}

class _QuizScreenState extends ConsumerState<_QuizScreen> {
  final Map<String, TextEditingController> _answers = {};
  Map<String, dynamic>? _result;
  bool _submitting = false;

  @override
  void dispose() {
    for (final controller in _answers.values) {
      controller.dispose();
    }
    super.dispose();
  }

  Future<void> _submit() async {
    setState(() => _submitting = true);
    try {
      final result = await ref.read(studyRepositoryProvider).submitQuiz(
        widget.quiz['id'] as String,
        _answers.map((key, value) => MapEntry(key, value.text.trim())),
      );
      if (mounted) setState(() => _result = result);
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final questions = (widget.quiz['questions'] as List? ?? const []).map((e) => Map<String, dynamic>.from(e as Map)).toList();
    return Scaffold(
      appBar: AppBar(title: Text(widget.quiz['title']?.toString() ?? 'Quiz')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          for (var i = 0; i < questions.length; i++) ...[
            Text('${i + 1}. ${questions[i]['question']}', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            TextField(
              controller: _answers.putIfAbsent(questions[i]['id'] as String, TextEditingController.new),
              enabled: _result == null,
              decoration: const InputDecoration(hintText: 'Your answer'),
            ),
            const SizedBox(height: 20),
          ],
          if (_result == null)
            FilledButton(onPressed: _submitting || questions.isEmpty ? null : _submit, child: Text(_submitting ? 'Submitting…' : 'Submit quiz'))
          else ...[
            Text('Score: ${(_result!['score'] as num).toStringAsFixed(0)}%', style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.bold)),
            const SizedBox(height: 12),
            ...((_result!['results'] as List).map((raw) {
              final item = Map<String, dynamic>.from(raw as Map);
              return Card(child: ListTile(leading: Icon(item['correct'] == true ? Icons.check_circle_outline : Icons.cancel_outlined), title: Text(item['correct'] == true ? 'Correct' : 'Review'), subtitle: Text('${item['answer']}\n${item['explanation']}')));
            })),
          ],
        ],
      ),
    );
  }
}
