import 'package:flutter/material.dart';

import '../models/feature_spec.dart';
import '../services/api_client.dart';
import '../widgets/feature_field.dart';
import 'result_screen.dart';

/// Input form generated from the server's model schema (GET /model/schema).
/// No feature is hard-coded in the app: labels, units, ranges, required flags and dropdown options
/// all come from the same specification the server uses to validate and to build the model input.
class PredictScreen extends StatefulWidget {
  const PredictScreen({super.key, required this.api});
  final ApiClient api;

  @override
  State<PredictScreen> createState() => _PredictScreenState();
}

class _PredictScreenState extends State<PredictScreen> {
  final _form = GlobalKey<FormState>();
  ModelSchema? _schema;
  String? _loadError;
  bool _loading = true, _submitting = false;
  final Map<String, TextEditingController> _ctrl = {};
  final Map<String, int?> _choice = {};
  Map<String, String> _serverErrors = {};

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _loadError = null;
    });
    try {
      final s = await widget.api.fetchSchema();
      for (final f in s.features) {
        _ctrl.putIfAbsent(f.key, () => TextEditingController());
        _choice.putIfAbsent(f.key, () => null);
      }
      if (mounted) setState(() => _schema = s);
    } on ApiException catch (e) {
      if (mounted && e.kind != ApiErrorKind.unauthorized) setState(() => _loadError = e.message);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  void dispose() {
    for (final c in _ctrl.values) {
      c.dispose();
    }
    super.dispose();
  }

  void _clear() {
    for (final c in _ctrl.values) {
      c.clear();
    }
    setState(() {
      _choice.updateAll((_, __) => null);
      _serverErrors = {};
    });
    _form.currentState?.reset();
  }

  void _snack(String m) => ScaffoldMessenger.of(context)
    ..hideCurrentSnackBar()
    ..showSnackBar(SnackBar(content: Text(m)));

  Future<void> _check() async {
    setState(() => _serverErrors = {});
    // 1) validate every field, 2) completeness is enforced by the validators ("required")
    if (!_form.currentState!.validate()) {
      _snack('Please correct the highlighted fields.');
      return;
    }
    final values = <String, num>{};
    for (final f in _schema!.features) {
      if (f.type == 'choice') {
        final c = _choice[f.key];
        if (c != null) values[f.key] = c;
      } else {
        final t = _ctrl[f.key]!.text.trim();
        if (t.isNotEmpty) {
          final v = FeatureField.parse(t)!;
          values[f.key] = f.integer ? v.round() : v;
        }
      }
    }
    setState(() => _submitting = true); // 3) loading indicator while the request is processed
    try {
      final result = await widget.api.predict(values); // 4) authenticated request -> real model prediction
      if (!mounted) return;
      await Navigator.of(context).push(MaterialPageRoute(builder: (_) => ResultScreen(result: result)));
    } on ApiException catch (e) {
      if (!mounted) return;
      if (e.kind == ApiErrorKind.validation) {
        setState(() => _serverErrors = e.fieldErrors);
        _form.currentState!.validate();
      }
      _snack(e.message);
    } catch (_) {
      if (mounted) _snack('Unexpected error. Please try again.');
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Relative Humidity'),
        actions: [
          IconButton(tooltip: 'Clear form', icon: const Icon(Icons.restart_alt), onPressed: _schema == null ? null : _clear),
          IconButton(tooltip: 'Log out', icon: const Icon(Icons.logout), onPressed: widget.api.logout),
        ],
      ),
      body: SafeArea(child: _body(context)),
    );
  }

  Widget _body(BuildContext context) {
    if (_loading) return const Center(child: CircularProgressIndicator());
    if (_loadError != null || _schema == null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            const Icon(Icons.cloud_off, size: 48),
            const SizedBox(height: 12),
            Text(_loadError ?? 'Could not load the model description.', textAlign: TextAlign.center),
            const SizedBox(height: 16),
            FilledButton.icon(onPressed: _load, icon: const Icon(Icons.refresh), label: const Text('Retry')),
          ]),
        ),
      );
    }
    final s = _schema!;
    return Form(
      key: _form,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Card(
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Text(
                'Model: ${s.modelName}\n'
                'Predicts ${s.targetLabel.toLowerCase()} (${s.targetUnit}) from air-quality sensor readings, '
                'temperature and time. Fields marked * are required.',
              ),
            ),
          ),
          const SizedBox(height: 16),
          for (final f in s.features) ...[
            FeatureField(
              spec: f,
              controller: _ctrl[f.key]!,
              choice: _choice[f.key],
              onChoice: (v) => setState(() => _choice[f.key] = v),
              serverError: _serverErrors[f.key],
              onEdited: _serverErrors.containsKey(f.key) ? () => setState(() => _serverErrors.remove(f.key)) : null,
            ),
            const SizedBox(height: 16),
          ],
          FilledButton.icon(
            onPressed: _submitting ? null : _check,
            icon: _submitting
                ? const SizedBox(height: 18, width: 18, child: CircularProgressIndicator(strokeWidth: 2))
                : const Icon(Icons.fact_check_outlined),
            label: Padding(
              padding: const EdgeInsets.symmetric(vertical: 14),
              child: Text(_submitting ? 'Checking...' : 'Check Prediction'),
            ),
          ),
          const SizedBox(height: 24),
        ],
      ),
    );
  }
}
