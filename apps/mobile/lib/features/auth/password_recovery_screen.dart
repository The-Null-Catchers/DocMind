import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/providers.dart';
import 'account_repository.dart';

class PasswordRecoveryScreen extends ConsumerStatefulWidget {
  const PasswordRecoveryScreen({super.key});

  @override
  ConsumerState<PasswordRecoveryScreen> createState() =>
      _PasswordRecoveryScreenState();
}

class _PasswordRecoveryScreenState
    extends ConsumerState<PasswordRecoveryScreen> {
  final _email = TextEditingController();
  final _token = TextEditingController();
  final _password = TextEditingController();
  bool _busy = false;
  bool _resetStage = false;
  String? _message;

  @override
  void dispose() {
    _email.dispose();
    _token.dispose();
    _password.dispose();
    super.dispose();
  }

  Future<void> _requestReset() async {
    if (!_email.text.contains('@')) return;
    setState(() {
      _busy = true;
      _message = null;
    });
    try {
      final result = await ref
          .read(accountRepositoryProvider)
          .forgotPassword(_email.text);
      if (!mounted) return;
      final devToken = result['dev_token']?.toString();
      setState(() {
        _resetStage = true;
        _message =
            result['message']?.toString() ??
            'Check your email for reset instructions.';
        if (devToken != null) _token.text = devToken;
      });
    } catch (error) {
      if (mounted)
        setState(
          () => _message = ref.read(apiClientProvider).errorMessage(error),
        );
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _reset() async {
    if (_token.text.trim().isEmpty || _password.text.length < 10) return;
    setState(() {
      _busy = true;
      _message = null;
    });
    try {
      await ref
          .read(accountRepositoryProvider)
          .resetPassword(_token.text, _password.text);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Password updated. Sign in with your new password.'),
        ),
      );
      context.go('/login');
    } catch (error) {
      if (mounted)
        setState(
          () => _message = ref.read(apiClientProvider).errorMessage(error),
        );
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Recover account')),
    body: SafeArea(
      child: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 440),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(
                  _resetStage ? 'Set a new password' : 'Forgot your password?',
                  style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  _resetStage
                      ? 'Enter the reset token from your email.'
                      : 'We will send reset instructions if the account exists.',
                ),
                const SizedBox(height: 24),
                if (!_resetStage)
                  TextField(
                    controller: _email,
                    keyboardType: TextInputType.emailAddress,
                    autofillHints: const [AutofillHints.email],
                    decoration: const InputDecoration(labelText: 'Email'),
                  )
                else ...[
                  TextField(
                    controller: _token,
                    decoration: const InputDecoration(labelText: 'Reset token'),
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: _password,
                    obscureText: true,
                    autofillHints: const [AutofillHints.newPassword],
                    decoration: const InputDecoration(
                      labelText: 'New password',
                      helperText: 'Use at least 10 characters',
                    ),
                  ),
                ],
                if (_message != null) ...[
                  const SizedBox(height: 12),
                  Text(_message!),
                ],
                const SizedBox(height: 20),
                FilledButton(
                  onPressed: _busy
                      ? null
                      : (_resetStage ? _reset : _requestReset),
                  child: Text(
                    _busy
                        ? 'Please wait…'
                        : (_resetStage
                              ? 'Reset password'
                              : 'Send reset instructions'),
                  ),
                ),
                TextButton(
                  onPressed: _busy ? null : () => context.go('/login'),
                  child: const Text('Back to sign in'),
                ),
              ],
            ),
          ),
        ),
      ),
    ),
  );
}
