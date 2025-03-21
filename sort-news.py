from lib.equation import RankingEquation

weights = {'uniqueness': 0.3, 'engagement': 0.25, 'recency': 0.1, 'verified': 0.1, 'content': 0.15, 'legitimacy': 0.2, 'downvote': 0.3}
trusted_sources = ['BBC', 'Reuters', 'NYT']
domain_scores = {'bbc.com': 90, 'reuters.com': 85, 'randomblog.com': 40}

df = pd.read_csv("store/news_articles.csv")

article_objects = []
for _, row in df.iterrows():
    article = RankingEquation(
        full_text=row['full_text'],
        title=row['title'],
        source=row['source'],
        published_at=row['published_at'],
        upvotes=row['upvote'],
        downvotes=row['downvote'],
        shares=row['share_count'],
        comments=row['comment_count']
    )
    article_objects.append(article)

sorted_articles = RankingEquation.rank_articles(article_objects, weights, trusted_sources, domain_scores)

for article in sorted_articles:
    print(f"Title: {article.title}, Score: {article.final_score}")