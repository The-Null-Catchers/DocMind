import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'core/router.dart';
import 'core/theme.dart';

class DocMindApp extends ConsumerWidget {
  const DocMindApp({super.key});
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final router = ref.watch(routerProvider);
    return MaterialApp.router(
      title: 'DocMind',
      debugShowCheckedModeBanner: false,
      theme: DocMindTheme.light,
      darkTheme: DocMindTheme.dark,
      themeMode: ThemeMode.system,
      routerConfig: router,
    );
  }
}
