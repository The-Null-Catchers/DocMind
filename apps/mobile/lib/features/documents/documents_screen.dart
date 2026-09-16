import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';

class DocumentsScreen extends StatelessWidget {
  const DocumentsScreen({super.key});
  Future<void> _pick() async { await FilePicker.platform.pickFiles(allowMultiple: true); }
  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Documents'), actions: [IconButton(onPressed: _pick, icon: const Icon(Icons.upload_file))]),
    body: ListView(padding: const EdgeInsets.all(16), children: [
      const SearchBar(leading: Icon(Icons.search), hintText: 'Search documents'), const SizedBox(height: 14),
      ...List.generate(6, (i) => Card(child: ListTile(leading: const Icon(Icons.picture_as_pdf_outlined), title: Text('Research document ${i+1}.pdf'), subtitle: const Text('Ready · 18 pages'), trailing: const Icon(Icons.more_horiz)))),
    ]),
    floatingActionButton: FloatingActionButton.extended(onPressed: _pick, icon: const Icon(Icons.add), label: const Text('Upload')),
  );
}
