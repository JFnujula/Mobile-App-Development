import 'package:flutter/material.dart';

import '../models/prediction_result.dart';

class ResultScreen extends StatelessWidget {
  const ResultScreen({super.key, required this.result});
  final PredictionResult result;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final tt = Theme.of(context).textTheme;
    return Scaffold(
      appBar: AppBar(title: const Text('Prediction')),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Card(
              color: cs.primaryContainer,
              child: Padding(
                padding: const EdgeInsets.symmetric(vertical: 28, horizontal: 16),
                child: Column(children: [
                  Row(mainAxisAlignment: MainAxisAlignment.center, children: [
                    Icon(Icons.check_circle, color: cs.primary),
                    const SizedBox(width: 8),
                    Text('Prediction successful', style: TextStyle(color: cs.onPrimaryContainer)),
                  ]),
                  const SizedBox(height: 12),
                  Text('Predicted ${result.targetLabel.toLowerCase()}',
                      style: tt.titleMedium?.copyWith(color: cs.onPrimaryContainer)),
                  Text('${result.prediction.toStringAsFixed(1)} ${result.unit}',
                      style: tt.displayMedium?.copyWith(fontWeight: FontWeight.bold, color: cs.onPrimaryContainer)),
                ]),
              ),
            ),
            const SizedBox(height: 16),
            _section(context, 'About this prediction', Text(result.explanation)),
            _section(
              context,
              'Model accuracy (notebook test set)',
              Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                _row('Mean absolute error', '${result.testMae.toStringAsFixed(2)} pp'),
                _row('RMSE', '${result.testRmse.toStringAsFixed(2)} pp'),
                _row('R²', result.testR2.toStringAsFixed(4)),
                const SizedBox(height: 6),
                Text('Averages over held-out test data; not a confidence interval for this single result.',
                    style: tt.bodySmall?.copyWith(color: cs.outline)),
              ]),
            ),
            if (result.imputed.isNotEmpty)
              _section(
                context,
                'Optional inputs left empty',
                Text('${result.imputed.join(', ')} - the training median was used for these, exactly as in the notebook.'),
              ),
            if (result.warnings.isNotEmpty)
              Card(
                color: cs.errorContainer,
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Row(children: [
                      Icon(Icons.warning_amber, color: cs.onErrorContainer),
                      const SizedBox(width: 8),
                      Text('Please note', style: tt.titleSmall?.copyWith(color: cs.onErrorContainer)),
                    ]),
                    const SizedBox(height: 8),
                    for (final w in result.warnings)
                      Padding(
                        padding: const EdgeInsets.only(bottom: 6),
                        child: Text('• $w', style: TextStyle(color: cs.onErrorContainer)),
                      ),
                  ]),
                ),
              ),
            const SizedBox(height: 16),
            OutlinedButton.icon(
              onPressed: () => Navigator.of(context).pop(),
              icon: const Icon(Icons.edit_outlined),
              label: const Padding(padding: EdgeInsets.symmetric(vertical: 12), child: Text('Change inputs')),
            ),
          ],
        ),
      ),
    );
  }

  Widget _section(BuildContext context, String title, Widget child) => Card(
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(title, style: Theme.of(context).textTheme.titleSmall),
            const SizedBox(height: 8),
            child,
          ]),
        ),
      );

  Widget _row(String k, String v) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 2),
        child: Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [Text(k), Text(v, style: const TextStyle(fontWeight: FontWeight.w600))]),
      );
}
