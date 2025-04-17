from supabase import create_client, Client
from dotenv import load_dotenv
import os

load_dotenv()

class SupabaseClient:
    def __init__(self):
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        if not url or not key:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in .env")
        self.client: Client = create_client(url, key)

    def insert_retailer(self, name: str, url: str):
        data = {"name": name, "url": url}
        return self.client.table("retailers").insert(data).execute()

    def insert_product(self, retailer_id: int, name: str, price: float, sku: str = None, category: str = None):
        product = {"retailer_id": retailer_id, "name": name, "sku": sku, "category": category}
        product_res = self.client.table("products").insert(product).execute()
        product_id = product_res.data[0]["id"]
        price_entry = {"product_id": product_id, "price": price}
        self.client.table("price_history").insert(price_entry).execute()
        return product_res

    def get_products(self):
        return self.client.table("products").select("*").execute().data

    def test_connection(self):
        try:
            response = self.client.table("retailers").select("*").execute()
            return response.data
        except Exception as e:
            raise Exception(f"Connection failed: {str(e)}")

if __name__ == "__main__":
    supabase = SupabaseClient()
    retailers = supabase.test_connection()
    print("Connection successful:", retailers)