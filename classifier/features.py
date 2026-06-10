from sklearn.feature_extraction.text import TfidfVectorizer

class FeatureExtractor:
    def __init__(self, ngram_range=(2, 5), analyzer='char_wb', max_features=20000):
        self.vectorizer = TfidfVectorizer(
            analyzer=analyzer,
            ngram_range=ngram_range,
            max_features=max_features,
        )
        self._embedding_model = None  # extension point for C1
    
    def fit_transform(self, questions):
        tfidf = self.vectorizer.fit_transform(questions)
        return tfidf
    
    def transform(self, questions):
        return self.vectorizer.transform(questions)
    
    def _get_embedding_features(self, questions):
        """Override in C1 to add embedding features."""
        return None
