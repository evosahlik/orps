from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import re
from database.supabase_client import SupabaseClient
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class Scraper:
    def __init__(self):
        self.supabase = SupabaseClient()

    def clean_price(self, price_str):
        match = re.search(r'[\d,]+\.\d{2}', price_str.replace('$', ''))
        return float(match.group().replace(',', '')) if match else None

    def scrape_academy(self, url):
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(url, wait_until="domcontentloaded", extra_http_headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"
                })
                page.wait_for_timeout(2000)
                html = page.content()
                browser.close()

            soup = BeautifulSoup(html, 'html.parser')
            name_elem = soup.select_one('span.productTitle--FWmyK')
            name = name_elem.text.strip() if name_elem else "Unknown Product"
            price_elem = soup.select_one('span.discountPrice.pricing.nowPrice.lg')
            price = self.clean_price(price_elem.text) if price_elem else 0.0
            sku_elem = soup.select_one('span')
            sku = sku_elem.text.strip() if sku_elem else None

            return {
                "name": name,
                "price": price,
                "sku": sku,
                "category": "Shoes"
            }
        except Exception as e:
            logging.error(f"Error scraping {url}: {str(e)}")
            return None

    def store_data(self, retailer_name, retailer_url, product_data):
        try:
            retailer = self.supabase.client.table("retailers").select("*").eq("name", retailer_name).execute()
            if not retailer.data:
                retailer = self.supabase.insert_retailer(retailer_name, retailer_url)
            retailer_id = retailer.data[0]["id"]
            self.supabase.insert_product(
                retailer_id=retailer_id,
                name=product_data["name"],
                price=product_data["price"],
                sku=product_data["sku"],
                category=product_data["category"]
            )
            logging.info(f"Stored product: {product_data['name']}")
        except Exception as e:
            logging.error(f"Error storing data: {str(e)}")

if __name__ == "__main__":
    scraper = Scraper()
    url = "https://www.academy.com/p/nike-mens-free-metcon-6-athletic-shoes?sku=white-light-blue-9-d"
    data = scraper.scrape_academy(url)
    if data:
        scraper.store_data("Academy Sports", "https://www.academy.com/", data)