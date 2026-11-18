"""Single source of truth for the model's input features.

The 13 features, their ORDER and their types come from the notebook (Section 8 output):

    ['CO(GT)', 'PT08.S1(CO)', 'C6H6(GT)', 'PT08.S2(NMHC)', 'NOx(GT)', 'PT08.S3(NOx)',
     'NO2(GT)', 'PT08.S4(NO2)', 'PT08.S5(O3)', 'T', 'Month', 'DayOfWeek', 'Hour']

The same list is used to
  * build the Pydantic request model (server-side validation),
  * build the DataFrame in the exact training column order,
  * generate the form in the mobile app (GET /api/v1/model/schema) - the app hard-codes no fields.

`required=False` mirrors the notebook: CO(GT), NOx(GT) and NO2(GT) had ~18 % missing values in the
training data and the pipeline's median imputer handles them. All other features had no missing
values in the rows used for training, so they are required.

The min/max below are generous *sanity* bounds that reject typos/garbage. The actual range seen in
training is returned separately (model_metadata.json) and used to warn about extrapolation.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, create_model

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December"]


def _f(key, column, label, unit, kind, required, lo, hi, help_, **extra) -> Dict[str, Any]:
    d = dict(key=key, column=column, label=label, unit=unit, type=kind, required=required,
             min=lo, max=hi, help=help_)
    d.update(extra)
    return d


FEATURE_SPECS: List[Dict[str, Any]] = [
    _f("co_gt", "CO(GT)", "CO concentration (reference analyzer)", "mg/m³", "number", False, 0, 50,
       "Hourly averaged CO. Optional - leave empty if unknown (the model then uses the training median)."),
    _f("pt08_s1_co", "PT08.S1(CO)", "Sensor S1 response (tin oxide, CO)", "sensor units", "number", True, 0, 5000,
       "Hourly averaged response of the PT08.S1 sensor."),
    _f("c6h6_gt", "C6H6(GT)", "Benzene concentration (reference analyzer)", "µg/m³", "number", True, 0, 200,
       "Hourly averaged benzene."),
    _f("pt08_s2_nmhc", "PT08.S2(NMHC)", "Sensor S2 response (titania, NMHC)", "sensor units", "number", True, 0, 5000,
       "Hourly averaged response of the PT08.S2 sensor."),
    _f("nox_gt", "NOx(GT)", "NOx concentration (reference analyzer)", "ppb", "number", False, 0, 5000,
       "Hourly averaged NOx. Optional."),
    _f("pt08_s3_nox", "PT08.S3(NOx)", "Sensor S3 response (tungsten oxide, NOx)", "sensor units", "number", True, 0, 5000,
       "Hourly averaged response of the PT08.S3 sensor."),
    _f("no2_gt", "NO2(GT)", "NO₂ concentration (reference analyzer)", "µg/m³", "number", False, 0, 1000,
       "Hourly averaged NO₂. Optional."),
    _f("pt08_s4_no2", "PT08.S4(NO2)", "Sensor S4 response (tungsten oxide, NO₂)", "sensor units", "number", True, 0, 5000,
       "Hourly averaged response of the PT08.S4 sensor."),
    _f("pt08_s5_o3", "PT08.S5(O3)", "Sensor S5 response (indium oxide, O₃)", "sensor units", "number", True, 0, 5000,
       "Hourly averaged response of the PT08.S5 sensor."),
    _f("temperature", "T", "Temperature", "°C", "number", True, -50, 60,
       "Air temperature in degrees Celsius."),
    _f("month", "Month", "Month", None, "choice", True, 1, 12,
       "Month of the measurement.", integer=True,
       options=[{"value": i + 1, "label": m} for i, m in enumerate(MONTHS)]),
    _f("day_of_week", "DayOfWeek", "Day of week", None, "choice", True, 0, 6,
       "Day of the measurement (the model uses 0 = Monday ... 6 = Sunday).", integer=True,
       options=[{"value": i, "label": d} for i, d in enumerate(DAYS)]),
    _f("hour", "Hour", "Hour of day", "h", "choice", True, 0, 23,
       "Hour of the measurement, 0-23 (24-hour clock).", integer=True,
       options=[{"value": h, "label": f"{h:02d}:00"} for h in range(24)]),
]

FEATURE_COLUMNS: List[str] = [s["column"] for s in FEATURE_SPECS]          # training order
KEY_TO_COLUMN: Dict[str, str] = {s["key"]: s["column"] for s in FEATURE_SPECS}


def _build_input_model() -> type[BaseModel]:
    fields: Dict[str, Any] = {}
    for s in FEATURE_SPECS:
        py_type = int if s.get("integer") else float
        kwargs = dict(ge=s["min"], le=s["max"], description=f'{s["label"]}' + (f' ({s["unit"]})' if s["unit"] else ""))
        if not s.get("integer"):
            kwargs["allow_inf_nan"] = False
        if s["required"]:
            fields[s["key"]] = (py_type, Field(..., **kwargs))
        else:
            fields[s["key"]] = (Optional[py_type], Field(None, **kwargs))
    return create_model("PredictionInput", __config__=ConfigDict(extra="forbid"), **fields)


PredictionInput = _build_input_model()
