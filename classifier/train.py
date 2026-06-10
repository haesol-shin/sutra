import json
import joblib
from pathlib import Path
from collections import Counter, defaultdict
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, f1_score
from sklearn.model_selection import StratifiedShuffleSplit

from classifier.features import FeatureExtractor

def main():
    data_path = Path(__file__).parents[1] / "data" / "cls_train_seed.json"
    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    questions = [item["question"] for item in data]
    labels = [item["label"] for item in data]
    source_ids = [data[i].get("source_doc_id", str(i)) for i in range(len(data))]
    
    # Group by source, determine majority label per source
    src_groups = defaultdict(list)
    for i, sid in enumerate(source_ids):
        src_groups[sid].append(i)
    
    src_ids = list(src_groups.keys())
    # Majority label for each source
    src_labels = []
    for sid in src_ids:
        indices = src_groups[sid]
        lbl_counts = Counter(labels[i] for i in indices)
        src_labels.append(lbl_counts.most_common(1)[0][0])
    
    # Stratified split at source level
    sss = StratifiedShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
    train_src_idx, test_src_idx = next(sss.split(src_ids, src_labels))
    
    train_sources = {src_ids[i] for i in train_src_idx}
    test_sources = {src_ids[i] for i in test_src_idx}
    
    train_idx = [i for i, sid in enumerate(source_ids) if sid in train_sources]
    test_idx = [i for i, sid in enumerate(source_ids) if sid in test_sources]
    
    X_train_q = [questions[i] for i in train_idx]
    y_train = [labels[i] for i in train_idx]
    X_test_q = [questions[i] for i in test_idx]
    y_test = [labels[i] for i in test_idx]
    
    # Verify all labels present in both splits
    train_labels = set(y_train)
    test_labels = set(y_test)
    print(f"Train labels present: {sorted(train_labels)}")
    print(f"Test labels present: {sorted(test_labels)}")
    print(f"Label coverage: {'OK' if train_labels == test_labels == {0,1,2,3,4} else 'WARNING'}")
    
    extractor = FeatureExtractor(ngram_range=(2, 5), analyzer='char_wb', max_features=20000)
    X_train = extractor.fit_transform(X_train_q)
    X_test = extractor.transform(X_test_q)
    
    clf = LogisticRegression(max_iter=1000, random_state=42)
    clf.fit(X_train, y_train)
    
    y_pred = clf.predict(X_test)
    
    macro_f1 = f1_score(y_test, y_pred, average='macro')
    weighted_f1 = f1_score(y_test, y_pred, average='weighted')
    
    print(f"Train size: {len(train_idx)}, Test size: {len(test_idx)}")
    print(f"Train sources: {len(train_sources)}, Test sources: {len(test_sources)}")
    print(f"Macro-F1: {macro_f1:.4f}")
    print(f"Weighted-F1: {weighted_f1:.4f}")
    print()
    print(classification_report(y_test, y_pred, target_names=[
        "graduation", "notices", "academic_calendar", "dining", "shuttle"
    ]))
    
    model_dir = Path(__file__).parents[1] / "model"
    model_dir.mkdir(exist_ok=True)
    joblib.dump((clf, extractor), model_dir / "classifier.joblib")
    print(f"\nModel saved to {model_dir / 'classifier.joblib'}")

if __name__ == "__main__":
    main()
