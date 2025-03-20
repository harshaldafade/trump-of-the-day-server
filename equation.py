import time
import numpy as np
import pandas as pd
import textstat  # For readability score
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

class NewsArticle:
    def __init__(self, full_text, title, author, source, published_at, upvotes, downvotes, shares, comments, sentiment, keywords, grammar_errors):
        self.full_text = full_text
        self.title = title
        self.author = author
        self.source = source
        self.published_at = published_at
        self.upvotes = upvotes
        self.downvotes = downvotes
        self.shares = shares
        self.comments = comments
        self.sentiment = sentiment
        self.keywords = keywords
        self.grammar_errors = grammar_errors
        
        # Compute textual and content-based attributes
        self.readability = textstat.flesch_reading_ease(self.full_text)
        self.grammar_quality = max(0, 10 - self.grammar_errors)  # Assume 10 is the best score
        self.headings_count = self.full_text.count('<h')
        self.keyword_density = len(self.keywords.split()) / max(1, len(self.full_text.split()))
        self.citations_count = self.full_text.count('http')
        
        # Placeholder for computed scores
        self.uniqueness_score = 0
        self.engagement_score = 0
        self.recency_score = 0
        self.verified_score = 0
        self.content_score = 0
        self.legitimacy_score = 0
        self.downvote_penalty = 0
        self.final_score = 0

    def compute_uniqueness(self, all_texts):
        """Computes how unique this article is compared to other articles."""
        vectorizer = TfidfVectorizer(stop_words='english')
        tfidf_matrix = vectorizer.fit_transform(all_texts)
        cosine_sim = cosine_similarity(tfidf_matrix)
        self.uniqueness_score = 1 - cosine_sim.max(axis=1)[0]  # Assuming self is the first element

    def compute_engagement_score(self):
        """Computes how engaging the article is based on interactions."""
        total_votes = max(1, self.upvotes + self.downvotes)  # Avoid division by zero
        self.engagement_score = (0.4 * (self.upvotes / total_votes) +
                                 0.3 * (self.shares / max(1, self.shares)) +
                                 0.2 * (self.comments / max(1, self.comments)))

    def compute_recency_score(self):
        """Computes how recent the article is."""
        decay_factor = 0.001
        current_time = time.time()
        self.recency_score = np.exp(-decay_factor * (current_time - self.published_at))

    def compute_verified_source_score(self, trusted_sources):
        """Assigns a score based on whether the source is trusted."""
        self.verified_score = 1 if self.source in trusted_sources else 0.5

    def compute_content_score(self):
        """Computes a score based on content quality and structure."""
        self.content_score = (0.4 * self.readability / 100 +
                              0.3 * self.grammar_quality / 10 +
                              0.2 * self.headings_count / max(1, self.headings_count) +
                              0.1 * self.keyword_density)
    
    def compute_legitimacy_score(self, verified_journalists, domain_scores):
        """Computes how legitimate the article is based on author, citations, and bias."""
        author_trust = 10 if self.author in verified_journalists else 5
        domain_authority = domain_scores.get(self.source, 50) / 100  # Normalize to [0,1]
        bias_score = 1 - abs(self.sentiment)  # Neutral sentiment is better

        self.legitimacy_score = (0.3 * author_trust / 10 +
                                 0.3 * self.citations_count / max(1, self.citations_count) +
                                 0.2 * domain_authority +
                                 0.2 * bias_score)
    
    def compute_downvote_penalty(self):
        """Computes the penalty based on downvotes."""
        total_votes = max(1, self.upvotes + self.downvotes)
        self.downvote_penalty = self.downvotes / total_votes
    
    def compute_final_score(self, weights):
        """Computes the final ranking score based on all metrics."""
        self.final_score = (weights['uniqueness'] * self.uniqueness_score +
                            weights['engagement'] * self.engagement_score +
                            weights['recency'] * self.recency_score +
                            weights['verified'] * self.verified_score +
                            weights['content'] * self.content_score +
                            weights['legitimacy'] * self.legitimacy_score -
                            weights['downvote'] * self.downvote_penalty)

    def rank_articles(articles, weights, trusted_sources, verified_journalists, domain_scores):
        """Ranks multiple articles and returns them in sorted order."""
        all_texts = [article.full_text for article in articles]
        
        for article in articles:
            article.compute_uniqueness(all_texts)
            article.compute_engagement_score()
            article.compute_recency_score()
            article.compute_verified_source_score(trusted_sources)
            article.compute_content_score()
            article.compute_legitimacy_score(verified_journalists, domain_scores)
            article.compute_downvote_penalty()
            article.compute_final_score(weights)
        
        return sorted(articles, key=lambda x: x.final_score, reverse=True)

# Example usage
weights = {'uniqueness': 0.3, 'engagement': 0.25, 'recency': 0.1, 'verified': 0.1, 'content': 0.15, 'legitimacy': 0.2, 'downvote': 0.3}
trusted_sources = ['BBC', 'Reuters', 'NYT']
verified_journalists = ['John Doe', 'Jane Smith']
domain_scores = {'bbc.com': 90, 'reuters.com': 85, 'randomblog.com': 40}

articles = [
    NewsArticle("Some article text", "Title 1", "John Doe", "BBC", time.time() - 1000, 50, 10, 20, 5, 0.1, "keyword1 keyword2", 2),
    NewsArticle("Another article text", "Title 2", "Unknown Author", "randomblog.com", time.time() - 5000, 30, 20, 10, 2, -0.3, "keyword3 keyword4", 5)
]

sorted_articles = NewsArticle.rank_articles(articles, weights, trusted_sources, verified_journalists, domain_scores)
for article in sorted_articles:
    print(f"Title: {article.title}, Score: {article.final_score}")
