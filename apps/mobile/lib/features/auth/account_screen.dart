import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/providers.dart';
import 'account_repository.dart';
import 'auth_controller.dart';

class AccountScreen extends ConsumerStatefulWidget {
  const AccountScreen({super.key});

  @override
  ConsumerState<AccountScreen> createState() => _AccountScreenState();
}

class _AccountScreenState extends ConsumerState<AccountScreen> {
  List<Map<String, dynamic>> _sessions = const [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadSessions();
  }

  Future<void> _loadSessions() async {
    try {
      final sessions = await ref.read(accountRepositoryProvider).sessions();
      if (!mounted) return;
      setState(() {
        _sessions = sessions;
        _loading = false;
        _error = null;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = ref.read(apiClientProvider).errorMessage(error);
      });
    }
  }

  Future<void> _requestVerification() async {
    try {
      final result = await ref.read(accountRepositoryProvider).requestVerification();
      if (!mounted) return;
      final devToken = result['dev_token']?.toString();
      if (devToken == null) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(result['message']?.toString() ?? 'Verification instructions sent.')));
        return;
      }
      final controller = TextEditingController(text: devToken);
      final token = await showDialog<String>(
        context: context,
        builder: (context) => AlertDialog(
          title: const Text('Verify email'),
          content: TextField(controller: controller, decoration: const InputDecoration(labelText: 'Verification token')),
          actions: [
            TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
            FilledButton(onPressed: () => Navigator.pop(context, controller.text.trim()), child: const Text('Verify')),
          ],
        ),
      );
      controller.dispose();
      if (token == null || token.isEmpty) return;
      await ref.read(accountRepositoryProvider).confirmVerification(token);
      await ref.read(authControllerProvider.notifier).restoreSession();
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Email verified.')));
    } catch (error) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(ref.read(apiClientProvider).errorMessage(error))));
    }
  }

  Future<void> _revoke(String id) async {
    try {
      await ref.read(accountRepositoryProvider).revokeSession(id);
      await _loadSessions();
    } catch (error) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(ref.read(apiClientProvider).errorMessage(error))));
    }
  }

  Future<void> _deleteAccount() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete account permanently?'),
        content: const Text('Owned workspace data and private account data will be deleted. This cannot be undone.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Delete account')),
        ],
      ),
    );
    if (confirmed != true) return;
    try {
      await ref.read(accountRepositoryProvider).deleteAccount();
      await ref.read(authControllerProvider.notifier).logout();
    } catch (error) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(ref.read(apiClientProvider).errorMessage(error))));
    }
  }

  @override
  Widget build(BuildContext context) {
    final user = ref.watch(authControllerProvider).user;
    final verified = user?['is_email_verified'] == true;
    return Scaffold(
      appBar: AppBar(title: const Text('Account')),
      body: RefreshIndicator(
        onRefresh: _loadSessions,
        child: ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.all(16),
          children: [
            Card(
              child: ListTile(
                leading: CircleAvatar(child: Text((user?['display_name']?.toString().trim().isNotEmpty ?? false) ? user!['display_name'].toString()[0].toUpperCase() : '?')),
                title: Text(user?['display_name']?.toString() ?? 'DocMind user'),
                subtitle: Text(user?['email']?.toString() ?? ''),
                trailing: Icon(verified ? Icons.verified_outlined : Icons.mark_email_unread_outlined),
              ),
            ),
            if (!verified) ...[
              const SizedBox(height: 8),
              Card(
                child: ListTile(
                  title: const Text('Verify your email'),
                  subtitle: const Text('Verification protects account recovery and collaboration invitations.'),
                  trailing: FilledButton(onPressed: _requestVerification, child: const Text('Verify')),
                ),
              ),
            ],
            const SizedBox(height: 20),
            Text('Sessions & devices', style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700)),
            const SizedBox(height: 8),
            if (_loading)
              const LinearProgressIndicator()
            else if (_error != null)
              ListTile(title: Text(_error!), trailing: TextButton(onPressed: _loadSessions, child: const Text('Retry')))
            else if (_sessions.isEmpty)
              const ListTile(title: Text('No active sessions found.'))
            else
              ..._sessions.map((session) {
                final revoked = session['revoked'] == true;
                return Card(
                  child: ListTile(
                    leading: Icon(revoked ? Icons.phonelink_off_outlined : Icons.devices_outlined),
                    title: Text(session['device_name']?.toString() ?? 'Unknown device'),
                    subtitle: Text(revoked ? 'Revoked' : 'Active until ${session['expires_at'] ?? ''}'),
                    trailing: revoked ? null : TextButton(onPressed: () => _revoke(session['id'] as String), child: const Text('Revoke')),
                  ),
                );
              }),
            const SizedBox(height: 24),
            OutlinedButton.icon(onPressed: () => ref.read(authControllerProvider.notifier).logout(), icon: const Icon(Icons.logout), label: const Text('Sign out')),
            const SizedBox(height: 12),
            TextButton.icon(onPressed: _deleteAccount, icon: const Icon(Icons.delete_forever_outlined), label: const Text('Delete account permanently')),
          ],
        ),
      ),
    );
  }
}
