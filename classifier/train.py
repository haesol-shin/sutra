import json
import joblib
from pathlib import Path
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, f1_score

from classifier.features import FeatureExtractor

def main():
    # Load data
    data_path = Path(__file__).parents[1] / "data" / "cls_train_seed.json"
    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    questions = [item["question"] for item in data]
    labels = [item["label"] for item in data]
    source_ids = [data[i].get("source_doc_id", str(i)) for i in range(len(data))]
    
    # Source-disjoint split (group by source_doc_id)
    from collections import defaultdict
    groups = defaultdict(list)
    for i, sid in enumerate(source_ids):
        groups[sid].append(i)
    
    unique_sources = list(groups.keys())
    split_idx = int(len(unique_sources) * 0.8)
    train_sources = set(unique_sources[:split_idx])
    
    train_idx = []
    test_idx = []
    for i, sid in enumerate(source_ids):
        if sid in train_sources:
            train_idx.append(i)
        else:
            test_idx.append(i)
    
    X_train_q = [questions[i] for i in train_idx]
    y_train = [labels[i] for i in train_idx]
    X_test_q = [questions[i] for i in test_idx]
    y_test = [labels[i] for i in test_idx]
    
    # Fit
    extractor = FeatureExtractor(ngram_range=(2, 5), analyzer='char_wb', max_features=20000)
    X_train = extractor.fit_transform(X_train_q)
    X_test = extractor.transform(X_test_q)
    
    clf = LogisticRegression(max_iter=1000, random_state=42)
    clf.fit(X_train, y_train)
    
    y_pred = clf.predict(X_test)
    
    macro_f1 = f1_score(y_test, y_pred, average='macro')
    weighted_f1 = f1_score(y_test, y_pred, average='weighted')
    
    print(f"Train size: {len(train_idx)}, Test size: {len(test_idx)}")
    print(f"Train sources: {len(train_sources)}, Test sources: {len(unique_sources) - len(train_sources)}")
    print(f"Macro-F1: {macro_f1:.4f}")
    print(f"Weighted-F1: {weighted_f1:.4f}")
    print()
    print(classification_report(y_test, y_pred, target_names=[
        "graduation", "notices", "academic_calendar", "dining", "shuttle"
    ]))
    
    # Save
    model_dir = Path(__file__).parents[1] / "model"
    model_dir.mkdir(exist_ok=True)
    joblib.dump((clf, extractor), model_dir / "classifier.joblib")
    print(f"\nModel saved to {model_dir / 'classifier.joblib'}")

if __name__ == "__main__":
    main()
