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

    def test_connection(self):
        """Test connectivity by querying the retailers table."""
        try:
            response = self.client.table("retailers").select("*").execute()
            return response.data
        except Exception as e:
            raise Exception(f"Connection failed: {str(e)}")

if __name__ == "__main__":
    try:
        supabase = SupabaseClient()
        # Insert test retailer
        supabase.client.table("retailers").insert(
            {"name": "Test Retailer", "url": "https://example.com"}
        ).execute()
        # Test connection
        retailers = supabase.test_connection()
        print("Connection successful! Retailers:", retailers)
    except Exception as e:
        print("Error:", str(e))