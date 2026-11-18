import 'package:flutter_test/flutter_test.dart';
import 'package:rh_predictor/models/feature_spec.dart';
import 'package:rh_predictor/widgets/feature_field.dart';

void main() {
  test('FeatureSpec parses the server schema entry', () {
    final f = FeatureSpec.fromJson({
      'key': 'month', 'column': 'Month', 'label': 'Month', 'unit': null, 'type': 'choice',
      'required': true, 'min': 1, 'max': 12, 'help': 'x', 'integer': true,
      'options': [{'value': 1, 'label': 'January'}],
      'training_range': {'min': 1.0, 'max': 12.0, 'median': 6.0},
    });
    expect(f.options.single.label, 'January');
    expect(f.integer, isTrue);
    expect(f.trainMedian, 6.0);
  });

  test('number parser accepts decimal comma', () {
    expect(FeatureField.parse('12,5'), 12.5);
    expect(FeatureField.parse('abc'), isNull);
  });
}
