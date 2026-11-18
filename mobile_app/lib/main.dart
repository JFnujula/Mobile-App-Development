import 'package:flutter/material.dart';

import 'screens/login_screen.dart';
import 'screens/predict_screen.dart';
import 'services/api_client.dart';
import 'services/token_store.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final api = ApiClient(TokenStore());
  await api.restoreSession();
  runApp(RhApp(api: api));
}

class RhApp extends StatelessWidget {
  const RhApp({super.key, required this.api});
  final ApiClient api;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'RH Predictor',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF0B6E99)),
        inputDecorationTheme: const InputDecorationTheme(border: OutlineInputBorder()),
      ),
      home: ValueListenableBuilder<bool>(
        valueListenable: api.signedIn,
        builder: (_, signedIn, __) =>
            signedIn ? PredictScreen(api: api) : LoginScreen(api: api),
      ),
    );
  }
}
