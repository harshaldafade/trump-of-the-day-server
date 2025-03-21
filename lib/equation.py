from datetime import datetime, UTC
import numpy as np
import pandas as pd
import textstat
from sklearn.feature_extraction.text import TfidfVectorizer
from textblob import TextBlob
from rake_nltk import Rake
import language_tool_python
import nltk
nltk.download('stopwords')
nltk.download('punkt_tab')

class RankingEquation:
    def __init__(self, full_text, title, source, published_at, upvotes, downvotes, shares, comments):
        self.full_text = full_text
        self.title = title
        self.source = source
        self.published_at = published_at
        self.upvotes = upvotes
        self.downvotes = downvotes
        self.shares = shares
        self.comments = comments

        self.sentiment = self.analyze_sentiment()
        self.keywords = self.extract_keywords()
        self.grammar_errors = self.check_grammar()

        self.readability = textstat.flesch_reading_ease(self.full_text)
        self.grammar_quality = max(0, 10 - self.grammar_errors)
        self.headings_count = self.full_text.count('<h')
        self.keyword_density = len(self.keywords.split()) / max(1, len(self.full_text.split()))
        self.citations_count = self.full_text.count('http')

        self.uniqueness_score = 0
        self.engagement_score = 0
        self.recency_score = 0
        self.verified_score = 0
        self.content_score = 0
        self.legitimacy_score = 0
        self.downvote_penalty = 0
        self.final_score = 0

    def analyze_sentiment(self):
        blob = TextBlob(self.full_text)
        return blob.sentiment.polarity

    def extract_keywords(self):
        rake = Rake()
        rake.extract_keywords_from_text(self.full_text)
        keywords = rake.get_ranked_phrases()[:10]
        return ' '.join(keywords)

    def check_grammar(self):
        tool = language_tool_python.LanguageTool('en-US')
        matches = tool.check(self.full_text)
        tool.close()
        return len(matches)

    def compute_uniqueness(self, all_texts, vectorizer=None, tfidf_matrix=None):
        index = all_texts.index(self.full_text)

        if vectorizer is None or tfidf_matrix is None:
            vectorizer = TfidfVectorizer(stop_words='english', min_df=1, max_df=0.9)
            tfidf_matrix = vectorizer.fit_transform(all_texts)

        article_vector = tfidf_matrix[index]

        similarities = []
        for i in range(len(all_texts)):
            if i != index:
                other_vector = tfidf_matrix[i]

                dot_product = article_vector.dot(other_vector.transpose())[0, 0]
                norm_product = np.sqrt(article_vector.dot(article_vector.transpose())[0, 0] *
                                      other_vector.dot(other_vector.transpose())[0, 0])
                similarity = dot_product / norm_product if norm_product > 0 else 0
                similarities.append(similarity)

        max_sim = max(similarities) if similarities else 0
        self.uniqueness_score = 1 - max_sim

    def compute_engagement_score(self):
        total_votes = max(1, self.upvotes + self.downvotes)

        self.engagement_score = (0.4 * (self.upvotes / total_votes) +
                                0.3 * (min(1, self.shares / 100)) +
                                0.2 * (min(1, self.comments / 50)))

    def compute_recency_score(self):
        decay_factor = 0.001
        current_time = datetime.now(UTC).timestamp()
        if isinstance(self.published_at, str):
            self.published_at = datetime.fromisoformat(self.published_at).replace(tzinfo=UTC).timestamp()
        self.recency_score = np.exp(-decay_factor * (current_time - self.published_at))

    def compute_verified_source_score(self, trusted_sources):
        self.verified_score = 1 if self.source in trusted_sources else 0.5

    def compute_content_score(self):
        normalized_headings = min(1, self.headings_count / 10)

        self.content_score = (0.4 * (self.readability / 100) +
                            0.3 * (self.grammar_quality / 10) +
                            0.2 * normalized_headings +
                            0.1 * min(1, self.keyword_density * 100))

    def compute_legitimacy_score(self, domain_scores):
        domain_authority = domain_scores.get(self.source, 50) / 100
        bias_score = 1 - abs(self.sentiment)
        normalized_citations = min(1, self.citations_count / 20)

        self.legitimacy_score = (0.4 * normalized_citations +
                                0.3 * domain_authority +
                                0.3 * bias_score)

    def compute_downvote_penalty(self):
        total_votes = max(1, self.upvotes + self.downvotes)
        self.downvote_penalty = self.downvotes / total_votes

    def compute_final_score(self, weights):
        self.final_score = (weights['uniqueness'] * self.uniqueness_score +
                            weights['engagement'] * self.engagement_score +
                            weights['recency'] * self.recency_score +
                            weights['verified'] * self.verified_score +
                            weights['content'] * self.content_score +
                            weights['legitimacy'] * self.legitimacy_score -
                            weights['downvote'] * self.downvote_penalty)

    @staticmethod
    def rank_articles(articles, weights, trusted_sources, domain_scores):
        all_texts = [article.full_text for article in articles]

        vectorizer = TfidfVectorizer(stop_words='english', min_df=1, max_df=0.9)
        tfidf_matrix = vectorizer.fit_transform(all_texts)

        for article in articles:
            article.compute_uniqueness(all_texts, vectorizer, tfidf_matrix)
            article.compute_engagement_score()
            article.compute_recency_score()
            article.compute_verified_source_score(trusted_sources)
            article.compute_content_score()
            article.compute_legitimacy_score(domain_scores)
            article.compute_downvote_penalty()
            article.compute_final_score(weights)

        return sorted(articles, key=lambda x: x.final_score, reverse=True)