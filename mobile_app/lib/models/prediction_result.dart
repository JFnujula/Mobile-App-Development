class PredictionResult {
  final double prediction;
  final String targetLabel;
  final String unit;
  final String modelName;
  final double testMae, testRmse, testR2;
  final String explanation;
  final List<String> warnings;
  final List<String> imputed;

  const PredictionResult({
    required this.prediction,
    required this.targetLabel,
    required this.unit,
    required this.modelName,
    required this.testMae,
    required this.testRmse,
    required this.testR2,
    required this.explanation,
    required this.warnings,
    required this.imputed,
  });

  factory PredictionResult.fromJson(Map<String, dynamic> j) => PredictionResult(
        prediction: (j['prediction'] as num).toDouble(),
        targetLabel: j['target_label'] as String,
        unit: j['unit'] as String,
        modelName: j['model_name'] as String,
        testMae: (j['notebook_test_mae'] as num).toDouble(),
        testRmse: (j['notebook_test_rmse'] as num).toDouble(),
        testR2: (j['notebook_test_r2'] as num).toDouble(),
        explanation: j['explanation'] as String,
        warnings: ((j['warnings'] ?? []) as List)
            .map((w) => '${w['feature']}: ${w['message']}')
            .toList(),
        imputed: ((j['imputed_features'] ?? []) as List).map((e) => e.toString()).toList(),
      );
}
