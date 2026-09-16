import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
void main(){testWidgets('basic Material app renders', (tester) async {await tester.pumpWidget(const MaterialApp(home: Scaffold(body: Text('DocMind'))));expect(find.text('DocMind'), findsOneWidget);});}
