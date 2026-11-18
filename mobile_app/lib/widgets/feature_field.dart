import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../models/feature_spec.dart';

String _fmt(double v) => v == v.roundToDouble() ? v.toStringAsFixed(0) : v.toStringAsFixed(2);

/// Builds the right input control for one feature described by the server schema.
class FeatureField extends StatelessWidget {
  const FeatureField({
    super.key,
    required this.spec,
    required this.controller,
    required this.choice,
    required this.onChoice,
    this.serverError,
    this.onEdited,
  });

  final FeatureSpec spec;
  final TextEditingController controller; // used for "number" fields
  final int? choice; // used for "choice" fields
  final ValueChanged<int?> onChoice;
  final String? serverError;
  final VoidCallback? onEdited;

  String get _title => spec.unit == null || spec.type == 'choice' ? spec.label : '${spec.label} (${spec.unit})';

  String? _helper() {
    if (spec.type != 'number' || spec.trainMin == null) return spec.help;
    return '${spec.help}\nTypical range in training data: ${_fmt(spec.trainMin!)} - ${_fmt(spec.trainMax!)}';
  }

  /// Accepts "12.5" and "12,5" (decimal comma keyboards).
  static double? parse(String s) => double.tryParse(s.trim().replaceAll(',', '.'));

  @override
  Widget build(BuildContext context) {
    if (spec.type == 'choice') {
      return DropdownButtonFormField<int>(
        initialValue: choice,
        isExpanded: true,
        decoration: InputDecoration(
            labelText: spec.required ? '${spec.label} *' : spec.label,
            helperText: spec.help,
            helperMaxLines: 2,
            errorText: serverError),
        items: [for (final o in spec.options) DropdownMenuItem(value: o.value, child: Text(o.label))],
        onChanged: (v) {
          onChoice(v);
          onEdited?.call();
        },
        validator: (v) => (spec.required && v == null) ? 'Please select ${spec.label.toLowerCase()}' : null,
      );
    }
    return TextFormField(
      controller: controller,
      keyboardType: const TextInputType.numberWithOptions(decimal: true, signed: true),
      inputFormatters: [FilteringTextInputFormatter.allow(RegExp(r'[0-9.,\-]'))],
      onChanged: (_) => onEdited?.call(),
      decoration: InputDecoration(
        labelText: spec.required ? '$_title *' : '$_title (optional)',
        helperText: _helper(),
        helperMaxLines: 3,
        errorText: serverError,
        errorMaxLines: 3,
      ),
      validator: (text) {
        final t = (text ?? '').trim();
        if (t.isEmpty) return spec.required ? '${spec.label} is required' : null;
        final v = parse(t);
        if (v == null) return 'Enter a valid number';
        if (v < spec.min || v > spec.max) {
          return 'Must be between ${_fmt(spec.min)} and ${_fmt(spec.max)}${spec.unit != null ? ' ${spec.unit}' : ''}';
        }
        return null;
      },
    );
  }
}
