/// One model input feature, exactly as described by GET /api/v1/model/schema.
class ChoiceOption {
  final int value;
  final String label;
  const ChoiceOption(this.value, this.label);
}

class FeatureSpec {
  final String key; // JSON field name sent to /predict
  final String column; // original notebook column name
  final String label;
  final String? unit;
  final String type; // "number" | "choice"
  final bool required;
  final double min;
  final double max;
  final String help;
  final bool integer;
  final List<ChoiceOption> options;
  final double? trainMin, trainMax, trainMedian;

  const FeatureSpec({
    required this.key,
    required this.column,
    required this.label,
    required this.unit,
    required this.type,
    required this.required,
    required this.min,
    required this.max,
    required this.help,
    required this.integer,
    required this.options,
    this.trainMin,
    this.trainMax,
    this.trainMedian,
  });

  factory FeatureSpec.fromJson(Map<String, dynamic> j) {
    final tr = j['training_range'] as Map<String, dynamic>?;
    return FeatureSpec(
      key: j['key'] as String,
      column: j['column'] as String,
      label: j['label'] as String,
      unit: j['unit'] as String?,
      type: j['type'] as String,
      required: j['required'] as bool,
      min: (j['min'] as num).toDouble(),
      max: (j['max'] as num).toDouble(),
      help: (j['help'] ?? '') as String,
      integer: (j['integer'] ?? false) as bool,
      options: ((j['options'] ?? []) as List)
          .map((o) => ChoiceOption((o['value'] as num).toInt(), o['label'] as String))
          .toList(),
      trainMin: (tr?['min'] as num?)?.toDouble(),
      trainMax: (tr?['max'] as num?)?.toDouble(),
      trainMedian: (tr?['median'] as num?)?.toDouble(),
    );
  }
}

class ModelSchema {
  final String modelName;
  final String targetLabel;
  final String targetUnit;
  final double testMae, testRmse, testR2;
  final List<FeatureSpec> features;

  const ModelSchema({
    required this.modelName,
    required this.targetLabel,
    required this.targetUnit,
    required this.testMae,
    required this.testRmse,
    required this.testR2,
    required this.features,
  });

  factory ModelSchema.fromJson(Map<String, dynamic> j) {
    final m = j['notebook_metrics_test'] as Map<String, dynamic>;
    final t = j['target'] as Map<String, dynamic>;
    return ModelSchema(
      modelName: j['model_name'] as String,
      targetLabel: t['label'] as String,
      targetUnit: t['unit'] as String,
      testMae: (m['mae'] as num).toDouble(),
      testRmse: (m['rmse'] as num).toDouble(),
      testR2: (m['r2_test'] as num).toDouble(),
      features: (j['features'] as List)
          .map((f) => FeatureSpec.fromJson(f as Map<String, dynamic>))
          .toList(),
    );
  }
}
