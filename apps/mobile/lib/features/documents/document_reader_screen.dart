import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:pdfrx/pdfrx.dart';

import '../../core/repositories.dart';

class DocumentReaderScreen extends ConsumerStatefulWidget {
  const DocumentReaderScreen({super.key, required this.documentId, this.initialPage = 1});

  final String documentId;
  final int initialPage;

  @override
  ConsumerState<DocumentReaderScreen> createState() => _DocumentReaderScreenState();
}

class _DocumentReaderScreenState extends ConsumerState<DocumentReaderScreen> {
  final PdfViewerController _pdfController = PdfViewerController();
  Map<String, dynamic>? _document;
  Map<String, dynamic>? _source;
  Map<String, dynamic>? _page;
  bool _loading = true;
  String? _error;
  late int _currentPage;

  @override
  void initState() {
    super.initState();
    _currentPage = widget.initialPage < 1 ? 1 : widget.initialPage;
    _pdfController.addListener(_onPdfChanged);
    _load();
  }

  @override
  void dispose() {
    _pdfController.removeListener(_onPdfChanged);
    _pdfController.dispose();
    super.dispose();
  }

  void _onPdfChanged() {
    final page = _pdfController.pageNumber;
    if (page == null || page == _currentPage || !mounted) return;
    setState(() => _currentPage = page);
  }

  Future<void> _load() async {
    try {
      final repo = ref.read(documentRepositoryProvider);
      final document = await repo.get(widget.documentId);
      final source = await repo.downloadSource(widget.documentId);
      if (!mounted) return;
      setState(() {
        _document = document;
        _source = source;
        _loading = false;
      });
      await _loadPage(_currentPage, quiet: true);
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = 'Could not open this document.';
      });
    }
  }

  Future<void> _loadPage(int pageNumber, {bool quiet = false}) async {
    final pageCount = (_document?['page_count'] as num?)?.toInt();
    final target = pageCount == null ? pageNumber.clamp(1, 100000) : pageNumber.clamp(1, pageCount);
    if (!quiet && mounted) setState(() => _currentPage = target);
    try {
      final page = await ref.read(documentRepositoryProvider).page(widget.documentId, target);
      if (!mounted || target != _currentPage) return;
      setState(() => _page = page);
    } catch (_) {
      if (!mounted || target != _currentPage) return;
      setState(() => _page = null);
    }
  }

  Future<void> _goToPage(int page) async {
    final pageCount = (_document?['page_count'] as num?)?.toInt() ?? _pdfController.pageCount;
    final target = page.clamp(1, pageCount > 0 ? pageCount : 1);
    setState(() => _currentPage = target);
    await _loadPage(target, quiet: true);
    if (_pdfController.isReady) {
      await _pdfController.goToPage(pageNumber: target, anchor: PdfPageAnchor.topCenter);
    }
  }

  Future<void> _zoom(bool increase) async {
    if (!_pdfController.isReady) return;
    final current = _pdfController.value.getMaxScaleOnAxis();
    final next = (current + (increase ? 0.25 : -0.25)).clamp(_pdfController.minScale, _pdfController.maxScale);
    await _pdfController.setZoom(_pdfController.viewSize.center(Offset.zero), next);
  }

  Future<void> _showExtractedText() async {
    await _loadPage(_currentPage);
    if (!mounted) return;
    final text = _page?['text']?.toString().trim() ?? '';
    final confidence = _page?['ocr_confidence'];
    final ocr = _page?['ocr_used'] == true;
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (context) => DraggableScrollableSheet(
        expand: false,
        initialChildSize: .65,
        maxChildSize: .92,
        minChildSize: .35,
        builder: (context, controller) => ListView(
          controller: controller,
          padding: const EdgeInsets.fromLTRB(20, 4, 20, 24),
          children: [
            Text('Page $_currentPage extracted text', style: Theme.of(context).textTheme.titleMedium),
            if (ocr) ...[
              const SizedBox(height: 4),
              Text(
                confidence == null ? 'OCR used' : 'OCR used · confidence ' + (confidence as num).toStringAsFixed(2),
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
            const SizedBox(height: 16),
            SelectableText(text.isEmpty ? 'No extracted text is available for this page.' : text),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) return const Scaffold(body: Center(child: CircularProgressIndicator()));
    if (_error != null || _document == null) {
      return Scaffold(appBar: AppBar(), body: Center(child: Text(_error ?? 'Document unavailable')));
    }

    final title = _document!['title']?.toString() ?? 'Document';
    final mime = _document!['mime_type']?.toString() ?? '';
    final pageCount = (_document!['page_count'] as num?)?.toInt();
    final isPdf = mime == 'application/pdf';
    final sourceUrl = _source?['url']?.toString();
    final headers = Map<String, String>.from((_source?['headers'] as Map?) ?? const {});

    return Scaffold(
      appBar: AppBar(
        title: Text(title, maxLines: 1, overflow: TextOverflow.ellipsis),
        actions: [
          IconButton(onPressed: _showExtractedText, tooltip: 'Extracted text', icon: const Icon(Icons.text_snippet_outlined)),
        ],
      ),
      body: Column(
        children: [
          Material(
            color: Theme.of(context).colorScheme.surfaceContainer,
            child: SizedBox(
              height: 48,
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  IconButton(onPressed: _currentPage <= 1 ? null : () => _goToPage(_currentPage - 1), icon: const Icon(Icons.chevron_left)),
                  Text('Page $_currentPage' + (pageCount == null ? '' : ' / $pageCount')),
                  IconButton(onPressed: pageCount != null && _currentPage >= pageCount ? null : () => _goToPage(_currentPage + 1), icon: const Icon(Icons.chevron_right)),
                  if (isPdf) ...[
                    const VerticalDivider(indent: 10, endIndent: 10),
                    IconButton(onPressed: () => _zoom(false), tooltip: 'Zoom out', icon: const Icon(Icons.remove)),
                    IconButton(onPressed: () => _zoom(true), tooltip: 'Zoom in', icon: const Icon(Icons.add)),
                  ],
                ],
              ),
            ),
          ),
          Expanded(
            child: isPdf && sourceUrl != null
                ? PdfViewer.uri(
                    Uri.parse(sourceUrl),
                    headers: headers,
                    controller: _pdfController,
                    initialPageNumber: _currentPage,
                    params: const PdfViewerParams(enableTextSelection: true, margin: 8),
                  )
                : _ExtractedDocumentView(
                    documentId: widget.documentId,
                    initialPage: _currentPage,
                    pageCount: pageCount,
                    onPageChanged: (page) {
                      _currentPage = page;
                      _loadPage(page);
                    },
                  ),
          ),
        ],
      ),
    );
  }
}

class _ExtractedDocumentView extends ConsumerStatefulWidget {
  const _ExtractedDocumentView({
    required this.documentId,
    required this.initialPage,
    required this.pageCount,
    required this.onPageChanged,
  });

  final String documentId;
  final int initialPage;
  final int? pageCount;
  final ValueChanged<int> onPageChanged;

  @override
  ConsumerState<_ExtractedDocumentView> createState() => _ExtractedDocumentViewState();
}

class _ExtractedDocumentViewState extends ConsumerState<_ExtractedDocumentView> {
  late final PageController _controller;
  final Map<int, Map<String, dynamic>> _pages = {};

  @override
  void initState() {
    super.initState();
    _controller = PageController(initialPage: widget.initialPage - 1);
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  Future<Map<String, dynamic>?> _page(int number) async {
    if (_pages.containsKey(number)) return _pages[number];
    try {
      final value = await ref.read(documentRepositoryProvider).page(widget.documentId, number);
      _pages[number] = value;
      return value;
    } catch (_) {
      return null;
    }
  }

  @override
  Widget build(BuildContext context) {
    final count = widget.pageCount ?? 1;
    return PageView.builder(
      controller: _controller,
      itemCount: count,
      onPageChanged: (index) => widget.onPageChanged(index + 1),
      itemBuilder: (context, index) {
        final pageNumber = index + 1;
        return FutureBuilder<Map<String, dynamic>?>(
          future: _page(pageNumber),
          builder: (context, snapshot) {
            if (snapshot.connectionState != ConnectionState.done) {
              return const Center(child: CircularProgressIndicator());
            }
            final text = snapshot.data?['text']?.toString().trim() ?? '';
            return SelectionArea(
              child: SingleChildScrollView(
                padding: const EdgeInsets.all(24),
                child: Text(text.isEmpty ? 'No readable text was extracted from this page.' : text),
              ),
            );
          },
        );
      },
    );
  }
}
