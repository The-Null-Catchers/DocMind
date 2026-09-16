import 'package:flutter/material.dart';

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});
  @override
  Widget build(BuildContext context) => CustomScrollView(slivers: [
    SliverAppBar.large(title: const Text('DocMind'), actions: [IconButton(onPressed: () {}, icon: const Icon(Icons.search))]),
    SliverPadding(padding: const EdgeInsets.all(16), sliver: SliverList.list(children: [
      Text('Good afternoon.', style: Theme.of(context).textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.w700)),
      const SizedBox(height: 6), const Text('Continue reading or turn a new document into knowledge.'), const SizedBox(height: 20),
      Card(child: Padding(padding: const EdgeInsets.all(20), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text('CONTINUE READING', style: TextStyle(fontSize: 11, letterSpacing: 1.5)), const SizedBox(height: 24),
        Text('Neural Retrieval Systems', style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w700)),
        const SizedBox(height: 8), const Text('Page 31 · Hybrid ranking and reranking'), const SizedBox(height: 16),
        const LinearProgressIndicator(value: .72), const SizedBox(height: 16), FilledButton(onPressed: () {}, child: const Text('Continue reading')),
      ]))), const SizedBox(height: 16),
      Row(children: [Expanded(child: _Metric(title: 'Due today', value: '24 cards', icon: Icons.psychology_alt_outlined)), const SizedBox(width: 12), Expanded(child: _Metric(title: 'Storage', value: '428 MB', icon: Icons.cloud_outlined))]),
      const SizedBox(height: 24), Text('Recent documents', style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700)), const SizedBox(height: 8),
      ...['Arabic OCR Benchmark.pdf','Q3 Market Analysis.pptx','Contract Review Notes.docx'].map((name) => Card(child: ListTile(leading: const CircleAvatar(child: Icon(Icons.description_outlined)), title: Text(name), subtitle: const Text('Ready · Updated today'), trailing: const Icon(Icons.chevron_right)))),
    ]))
  ]);
}

class _Metric extends StatelessWidget {
  const _Metric({required this.title, required this.value, required this.icon}); final String title,value; final IconData icon;
  @override Widget build(BuildContext context) => Card(child: Padding(padding: const EdgeInsets.all(16), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Icon(icon), const SizedBox(height: 24), Text(title, style: Theme.of(context).textTheme.labelMedium), const SizedBox(height: 4), Text(value, style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700))])));
}
