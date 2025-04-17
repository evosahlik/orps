import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
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

    def scrape_academy(self, url, max_retries=3):
        for attempt in range(max_retries):
            try:
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=False)
                    context = browser.new_context(
                        viewport={"width": 1280, "height": 720},
                        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    )
                    context.set_extra_http_headers({
                        "Accept-Language": "en-US,en;q=0.9",
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
                    })
                    page = context.new_page()
                    page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    page.wait_for_timeout(2000)
                    html = page.content()
                    browser.close()

                soup = BeautifulSoup(html, 'html.parser')
                name_elem = soup.select_one('span.productTitle--FWmyK')
                name = name_elem.text.strip() if name_elem else "Unknown Product"
                price_elem = soup.select_one('span.discountPrice.pricing.nowPrice.lg')
                price = self.clean_price(price_elem.text) if price_elem else 0.0
                sku_elem = soup.select_one('div.sku-container span:nth-child(2)')
                sku = sku_elem.text.strip() if sku_elem else None

                return {
                    "name": name,
                    "price": price,
                    "sku": sku,
                    "category": "Shoes"
                }
            except (PlaywrightTimeoutError, Exception) as e:
                logging.warning(f"Attempt {attempt + 1} failed for {url}: {str(e)}")
                if attempt + 1 == max_retries:
                    logging.error(f"Error scraping {url} after {max_retries} attempts: {str(e)}")
                    return None
                page.wait_for_timeout(1000)  # Wait before retry

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