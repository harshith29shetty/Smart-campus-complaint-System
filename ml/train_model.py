"""
Trains a TF-IDF + Logistic Regression classifier on the labeled complaint
dataset and saves the model + vectorizer to disk using joblib.

Run this once before starting the Flask app:
    python ml/train_model.py
"""

import os
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

from dataset import get_dataset

MODEL_DIR = os.path.join(os.path.dirname(__file__), "saved_model")
os.makedirs(MODEL_DIR, exist_ok=True)


def train():
    data = get_dataset()
    texts = [t for t, _ in data]
    labels = [l for _, l in data]

    X_train, X_test, y_train, y_test = train_test_split(
        texts, labels, test_size=0.2, random_state=42, stratify=labels
    )

    vectorizer = TfidfVectorizer(
        lowercase=True,
        stop_words="english",
        ngram_range=(1, 2),
        max_features=3000,
    )
    X_train_vec = vectorizer.fit_transform(X_train)
    X_test_vec = vectorizer.transform(X_test)

    model = LogisticRegression(max_iter=1000)
    model.fit(X_train_vec, y_train)

    y_pred = model.predict(X_test_vec)
    acc = accuracy_score(y_test, y_pred)

    print(f"Test Accuracy: {acc * 100:.2f}%\n")
    print("Classification Report:")
    print(classification_report(y_test, y_pred))
    print("Confusion Matrix:")
    print(confusion_matrix(y_test, y_pred, labels=sorted(set(labels))))
    print("Labels order:", sorted(set(labels)))

    joblib.dump(model, os.path.join(MODEL_DIR, "category_model.pkl"))
    joblib.dump(vectorizer, os.path.join(MODEL_DIR, "vectorizer.pkl"))
    print(f"\nModel and vectorizer saved to {MODEL_DIR}")


if __name__ == "__main__":
    train()
