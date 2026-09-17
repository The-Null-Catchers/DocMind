import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'auth_controller.dart';

class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key, this.register = false});
  final bool register;

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  final _formKey = GlobalKey<FormState>();
  final _email = TextEditingController();
  final _password = TextEditingController();
  final _name = TextEditingController();

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    _name.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    final controller = ref.read(authControllerProvider.notifier);
    if (widget.register) {
      await controller.register(email: _email.text, password: _password.text, displayName: _name.text);
    } else {
      await controller.login(_email.text, _password.text);
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(authControllerProvider);
    final loading = state.status == AuthStatus.loading;
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 440),
              child: Form(
                key: _formKey,
                child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                  Icon(Icons.auto_stories_outlined, size: 48, color: Theme.of(context).colorScheme.primary),
                  const SizedBox(height: 20),
                  Text(widget.register ? 'Create your DocMind account' : 'Welcome back', textAlign: TextAlign.center, style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w700)),
                  const SizedBox(height: 24),
                  if (widget.register) ...[
                    TextFormField(controller: _name, decoration: const InputDecoration(labelText: 'Display name'), validator: (v) => (v == null || v.trim().isEmpty) ? 'Enter your name' : null),
                    const SizedBox(height: 12),
                  ],
                  TextFormField(controller: _email, keyboardType: TextInputType.emailAddress, autofillHints: const [AutofillHints.email], decoration: const InputDecoration(labelText: 'Email'), validator: (v) => (v == null || !v.contains('@')) ? 'Enter a valid email' : null),
                  const SizedBox(height: 12),
                  TextFormField(controller: _password, obscureText: true, autofillHints: widget.register ? const [AutofillHints.newPassword] : const [AutofillHints.password], decoration: const InputDecoration(labelText: 'Password'), validator: (v) => (v == null || v.length < 10) ? 'Use at least 10 characters' : null),
                  if (state.error != null) ...[
                    const SizedBox(height: 12),
                    Text(state.error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
                  ],
                  const SizedBox(height: 20),
                  FilledButton(onPressed: loading ? null : _submit, child: Text(loading ? 'Please wait…' : (widget.register ? 'Create account' : 'Sign in'))),
                  TextButton(onPressed: loading ? null : () => context.go(widget.register ? '/login' : '/register'), child: Text(widget.register ? 'Already have an account? Sign in' : 'New to DocMind? Create account')),
                ]),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
