import pandas as pd
from mlxtend.frequent_patterns import apriori, association_rules
import psycopg2

def fetch_transaction_baskets():
    conn = psycopg2.connect(
    dbname="instacart_db",
    user="postgres",
    password="postgres",
    host="localhost",
    port="5434"
)
    # Sample down to top 15,000 orders to avoid memory overflow during cross-tabulation
    query = """
        SELECT op.order_id, p.product_name 
        FROM order_products op
        JOIN products p ON op.product_id = p.product_id
        WHERE op.order_id IN (SELECT order_id FROM orders LIMIT 15000);
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df

def run_market_basket_analytics():
    df = fetch_transaction_baskets()
    
    print("⚡ Building transactional pivot matrix...")
    basket = (df.groupby(['order_id', 'product_name'])['product_name']
              .count().unstack().reset_index().fillna(0)
              .set_index('order_id'))
    
    # Binary encoding matrix transformation
    basket_encoded = basket.applymap(lambda x: 1 if x > 0 else 0)
    
    print("📈 Running Apriori Pipeline Optimization...")
    frequent_itemsets = apriori(basket_encoded, min_support=0.01, use_colnames=True)
    
    print("⚖️ Extracting Strong Association Rules...")
    rules = association_rules(frequent_itemsets, metric="lift", min_threshold=1.2)
    rules = rules.sort_values(by="lift", ascending=False).head(100)
    
    # Save to csv for clear Power BI visualization integration
    rules.to_csv('data/processed/market_basket_rules.csv', index=False)
    print("🎉 Market Basket Rules saved to data/processed/market_basket_rules.csv")

if __name__ == "__main__":
    run_market_basket_analytics()