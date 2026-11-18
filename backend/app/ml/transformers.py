"""Custom transformer used by the notebook's preprocessing pipeline.

This is a verbatim copy of the `IQRCapper` class from Section 10 of the notebook.
It MUST live in an importable module (not `__main__`) so the pickled pipeline can be
loaded later by the FastAPI server. Do not change its logic: the pickled model refers
to it by name (`app.ml.transformers.IQRCapper`).
"""
import numpy as np
from sklearn.base import BaseEstimator, TransformerMixin


class IQRCapper(BaseEstimator, TransformerMixin):
    """Caps values to [Q1 - k*IQR, Q3 + k*IQR]. Limits are learned in fit() (training data only)."""

    def __init__(self, factor=1.5):
        self.factor = factor

    def fit(self, X, y=None):
        X = np.asarray(X, dtype=float)
        q1, q3 = np.nanpercentile(X, 25, axis=0), np.nanpercentile(X, 75, axis=0)
        iqr = q3 - q1
        self.lower_ = q1 - self.factor * iqr
        self.upper_ = q3 + self.factor * iqr
        return self

    def transform(self, X):
        return np.clip(np.asarray(X, dtype=float), self.lower_, self.upper_)

    def get_feature_names_out(self, input_features=None):
        return np.asarray(input_features, dtype=object)
