import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../features/ai/ai_screen.dart';
import '../features/auth/account_screen.dart';
import '../features/auth/auth_controller.dart';
import '../features/auth/login_screen.dart';
import '../features/auth/password_recovery_screen.dart';
import '../features/documents/document_reader_screen.dart';
import '../features/documents/documents_screen.dart';
import '../features/home/home_screen.dart';
import '../features/library/library_screen.dart';
import '../features/study/study_screen.dart';

final routerProvider = Provider<GoRouter>((ref) {
  final auth = ref.watch(authControllerProvider);
  return GoRouter(
    initialLocation: '/splash',
    redirect: (context, state) {
      final location = state.matchedLocation;
      if (auth.status == AuthStatus.loading) {
        return location == '/splash' ? null : '/splash';
      }
      final isAuthRoute = location == '/login' || location == '/register' || location == '/forgot-password';
      if (auth.status == AuthStatus.unauthenticated) {
        return isAuthRoute ? null : '/login';
      }
      if (isAuthRoute || location == '/splash') return '/home';
      return null;
    },
    routes: [
      GoRoute(
        path: '/splash',
        builder: (_, __) => const Scaffold(body: Center(child: CircularProgressIndicator())),
      ),
      GoRoute(path: '/login', builder: (_, __) => const LoginScreen()),
      GoRoute(path: '/register', builder: (_, __) => const LoginScreen(register: true)),
      GoRoute(path: '/forgot-password', builder: (_, __) => const PasswordRecoveryScreen()),
      GoRoute(path: '/account', builder: (_, __) => const AccountScreen()),
      GoRoute(
        path: '/documents/:id',
        builder: (_, state) => DocumentReaderScreen(
          documentId: state.pathParameters['id']!,
          initialPage: int.tryParse(state.uri.queryParameters['page'] ?? '') ?? 1,
        ),
      ),
      StatefulShellRoute.indexedStack(
        builder: (context, state, shell) => _Shell(shell: shell),
        branches: [
          StatefulShellBranch(routes: [GoRoute(path: '/home', builder: (_, __) => const HomeScreen())]),
          StatefulShellBranch(routes: [GoRoute(path: '/documents', builder: (_, __) => const DocumentsScreen())]),
          StatefulShellBranch(routes: [GoRoute(path: '/ai', builder: (_, __) => const AiScreen())]),
          StatefulShellBranch(routes: [GoRoute(path: '/study', builder: (_, __) => const StudyScreen())]),
          StatefulShellBranch(routes: [GoRoute(path: '/library', builder: (_, __) => const LibraryScreen())]),
        ],
      ),
    ],
  );
});

class _Shell extends StatelessWidget {
  const _Shell({required this.shell});
  final StatefulNavigationShell shell;

  @override
  Widget build(BuildContext context) => Scaffold(
        body: SafeArea(child: shell),
        bottomNavigationBar: NavigationBar(
          selectedIndex: shell.currentIndex,
          onDestinationSelected: (index) => shell.goBranch(index, initialLocation: index == shell.currentIndex),
          destinations: const [
            NavigationDestination(icon: Icon(Icons.home_outlined), selectedIcon: Icon(Icons.home), label: 'Home'),
            NavigationDestination(icon: Icon(Icons.description_outlined), selectedIcon: Icon(Icons.description), label: 'Documents'),
            NavigationDestination(icon: Icon(Icons.auto_awesome_outlined), selectedIcon: Icon(Icons.auto_awesome), label: 'AI'),
            NavigationDestination(icon: Icon(Icons.school_outlined), selectedIcon: Icon(Icons.school), label: 'Study'),
            NavigationDestination(icon: Icon(Icons.bookmarks_outlined), selectedIcon: Icon(Icons.bookmarks), label: 'Library'),
          ],
        ),
      );
}
