import joblib
from pathlib import Path

def load_model(model_path: Path | None = None):
    if model_path is None:
        model_path = Path(__file__).parents[1] / "model" / "classifier.joblib"
    return joblib.load(model_path)

def predict(questions: list[str], model_path: Path | None = None) -> list[int]:
    clf, extractor = load_model(model_path)
    X = extractor.transform(questions)
    return clf.predict(X).tolist()
