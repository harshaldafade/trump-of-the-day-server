import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

class NewsSorter:
    def __init__(self, file_path, similarity_threshold=0.7):
        self.file_path = file_path
        self.similarity_threshold = similarity_threshold
        self.df = pd.read_csv(file_path)
        self.vectorizer = TfidfVectorizer(stop_words="english")
        self.tfidf_matrix = None
        self.cosine_sim = None
        self.zeroed_out = set()
    
    def compute_tfidf(self):
        """Compute the TF-IDF matrix for the articles."""
        self.tfidf_matrix = self.vectorizer.fit_transform(self.df["full_text"])
    
    def compute_cosine_similarity(self):
        """Compute cosine similarity between articles."""
        self.cosine_sim = cosine_similarity(self.tfidf_matrix, self.tfidf_matrix)
    
    def score_and_rank(self):
        """Compute similarity scores and rank the articles."""
        scores = []
        for i in range(len(self.df)):
            max_sim = max(self.cosine_sim[i, :i].tolist() + self.cosine_sim[i, i+1:].tolist()) if len(self.df) > 1 else 0
            score = 1 - max_sim  # Higher similarity means lower score

            # Zero out duplicates
            if any(self.cosine_sim[i, j] > self.similarity_threshold for j in range(i)):
                scores.append(0)
                self.zeroed_out.add(i)
            else:
                scores.append(score)

        self.df["score"] = scores
    
    def sort_articles(self):
        """Sort articles based on their scores in descending order."""
        sorted_indices = np.argsort(self.df["score"])[::-1]
        self.df = self.df.iloc[sorted_indices].reset_index(drop=True)
    
    def process(self):
        """Run all processing steps."""
        self.compute_tfidf()
        self.compute_cosine_similarity()
        self.score_and_rank()
        self.sort_articles()
        return self.df, self.zeroed_out

if __name__ == "__main__":
    sorter = NewsSorter("news_articles_rows.csv")
    sorted_data, zeroed_out = sorter.process()
    print(sorted_data)
    print("###########")
    print(zeroed_out)