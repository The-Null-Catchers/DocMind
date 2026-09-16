import 'package:flutter/material.dart';
import 'package:flutter_markdown/flutter_markdown.dart';

class AiScreen extends StatefulWidget { const AiScreen({super.key}); @override State<AiScreen> createState()=>_AiScreenState(); }
class _AiScreenState extends State<AiScreen> {
  final controller = TextEditingController();
  @override Widget build(BuildContext context) => Scaffold(appBar: AppBar(title: const Text('Ask DocMind'), bottom: const PreferredSize(preferredSize: Size.fromHeight(32), child: Padding(padding: EdgeInsets.only(bottom: 8), child: Text('Research Lab · grounded in selected sources')))), body: Column(children: [
    Expanded(child: ListView(padding: const EdgeInsets.all(16), children: [
      Align(alignment: AlignmentDirectional.centerEnd, child: Container(padding: const EdgeInsets.all(14), decoration: BoxDecoration(color: Theme.of(context).colorScheme.primary, borderRadius: BorderRadius.circular(18)), child: Text('Explain the hybrid retrieval approach.', style: TextStyle(color: Theme.of(context).colorScheme.onPrimary)))),
      const SizedBox(height: 16), const MarkdownBody(data: 'DocMind combines **semantic** and **keyword** retrieval, then reranks the strongest candidates before generation. [C1]'),
      const SizedBox(height: 12), Card(child: ListTile(title: const Text('Source C1 · page 31'), subtitle: const Text('Neural Retrieval Systems.pdf'), trailing: const Icon(Icons.open_in_new))),
    ])),
    SafeArea(top: false, child: Padding(padding: const EdgeInsets.fromLTRB(12, 8, 12, 12), child: TextField(controller: controller, minLines: 1, maxLines: 5, decoration: InputDecoration(hintText: 'Ask across your documents…', suffixIcon: IconButton(onPressed: () {}, icon: const Icon(Icons.arrow_upward))))))
  ]));
}
