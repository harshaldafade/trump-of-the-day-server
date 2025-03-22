from lib.equation import RankingEquation
from lib.utils import DatabaseConnection
import pandas as pd

weights = {'uniqueness': 0.3, 'engagement': 0.25, 'recency': 0.1, 'verified': 0.1, 'content': 0.15, 'legitimacy': 0.2, 'downvote': 0.3}
trusted_sources = ['BBC', 'Reuters', 'NYT']
domain_scores = {'bbc.com': 90, 'reuters.com': 85, 'randomblog.com': 40}

def fetch_articles_from_database():
    """
    Fetches all articles from the news_articles table in the database
    
    Returns:
        list: List of article data dictionaries
    """
    try:
        # Initialize database connection
        db = DatabaseConnection("news_articles")
        
        # Fetch all records - you may want to limit this if you have many records
        articles = db.fetch_records(limit=1000)
        print(f"📋 Fetched {len(articles)} articles from database")
        return articles
        
    except Exception as e:
        print(f"❌ Error fetching articles: {e}")
        return []

def update_article_scores_in_database(sorted_articles):
    """
    Updates the article_score column in the news_articles table with calculated scores.
    
    Args:
        sorted_articles: List of RankingEquation objects with calculated scores
        
    Returns:
        int: Number of articles updated
    """
    try:
        # Initialize database connection
        db = DatabaseConnection("news_articles")
        
        update_count = 0
        for article in sorted_articles:
            # Update the article_score column for each article
            response = db.update_record(article.id, {"article_score": article.final_score})
            update_count += 1
            print(f"Updated article ID {article.id} with score {article.final_score:.4f}")
        
        print(f"✅ Successfully updated scores for {update_count} articles")
        return update_count
        
    except Exception as e:
        print(f"❌ Error updating article scores: {e}")
        return 0

def main():
    # Fetch articles from database instead of reading CSV
    articles_data = fetch_articles_from_database()
    
    if not articles_data:
        print("No articles found. Exiting.")
        return

    article_objects = []
    for row in articles_data:
        try:
            article = RankingEquation(
                id=row['id'],
                full_text=row['full_text'],
                title=row['title'],
                source=row['source'],
                published_at=row['published_at'],
                upvotes=row.get('upvote', 0),
                downvotes=row.get('downvote', 0),
                shares=row.get('share_count', 0),
                comments=row.get('comment_count', 0)
            )
            article_objects.append(article)
        except Exception as e:
            print(f"Error processing article ID {row.get('id', 'unknown')}: {e}")
            continue

    print(f"Processing {len(article_objects)} valid articles for ranking")
    
    sorted_articles = RankingEquation.rank_articles(article_objects, weights, trusted_sources, domain_scores)

    # Display sorted articles
    # print("\nRanked Articles:")
    # for i, article in enumerate(sorted_articles[:10], 1):
    #     print(f"{i}. Title: {article.title}, Score: {article.final_score:.4f}")
    
    # Update scores in Supabase database
    update_article_scores_in_database(sorted_articles)

if __name__ == "__main__":
    main()