import os
import io
import pandas as pd
import psycopg2

def get_connection():
    return psycopg2.connect(
    dbname="instacart_db",
    user="postgres",
    password="postgres",
    host="localhost",
    port="5434"
)

def bulk_insert_csv(csv_path, table_name, conn):
    cursor = conn.cursor()
    print(f"🚀 Processing bulk ingestion for table: {table_name}...")
    
    # Read CSV in chunks to minimize memory profile
    chunks = pd.read_csv(csv_path, chunksize=100000)
    
    for i, chunk in enumerate(chunks):
        buffer = io.StringIO()
        chunk.to_csv(buffer, index=False, header=False, sep='\t')
        buffer.seek(0)
        
        try:
            cursor.copy_from(buffer, table_name, sep='\t', null="")
            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"❌ Error during chunk batch ingestion: {e}")
            raise e
    print(f"✅ Table {table_name} populated successfully.")

def combine_and_clean_order_products(prior_path, train_path, out_path):
    print("🧹 Merging transactional data streams...")
    df_prior = pd.read_csv(prior_path)
    df_train = pd.read_csv(train_path)
    combined = pd.concat([df_prior, df_train], axis=0)
    combined.to_csv(out_path, index=False)
    print("✅ Transaction files cleanly normalized.")

if __name__ == "__main__":
    conn = get_connection()
    
    # Step 1: Pre-merge transactional logs
    combine_and_clean_order_products('data/raw/order_products__prior.csv', 'data/raw/order_products__train.csv', 'data/raw/order_products.csv')
    
    # Step 2: Ingest into Data Warehouse
    bulk_insert_csv('data/raw/departments.csv', 'departments', conn)
    bulk_insert_csv('data/raw/aisles.csv', 'aisles', conn)
    bulk_insert_csv('data/raw/products.csv', 'products', conn)
    bulk_insert_csv('data/raw/orders.csv', 'orders', conn)
    bulk_insert_csv('data/raw/order_products.csv', 'order_products', conn)
    
    conn.close()
    print("🎉 ETL pipeline stage complete.")