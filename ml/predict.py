import os
import joblib
from ml.priority import predict_priority_with_explanation

MODEL_DIR = os.path.join(os.path.dirname(__file__), "saved_model")

LOW_CONFIDENCE_THRESHOLD = 55.0  # percent scale (0-100)

_model = None
_vectorizer = None


def _load():
    global _model, _vectorizer
    if _model is None or _vectorizer is None:
        _model = joblib.load(os.path.join(MODEL_DIR, "category_model.pkl"))
        _vectorizer = joblib.load(os.path.join(MODEL_DIR, "vectorizer.pkl"))
    return _model, _vectorizer


def classify_complaint(title: str, description: str):
    """
    Returns dict: {category, confidence, priority, priority_explanation, low_confidence}
    """
    model, vectorizer = _load()
    combined = f"{title}. {description}"
    vec = vectorizer.transform([combined])
    proba = model.predict_proba(vec)[0]
    classes = model.classes_
    best_idx = proba.argmax()
    category = classes[best_idx]
    confidence = round(float(proba[best_idx]) * 100, 2)

    priority, explanation = predict_priority_with_explanation(title, description)

    return {
        "category": category,
        "confidence": confidence,
        "priority": priority,
        "priority_explanation": explanation,
        "low_confidence": confidence < LOW_CONFIDENCE_THRESHOLD,
    }
