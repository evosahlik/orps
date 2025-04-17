import sys
import os
import random
import time
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

    def clean_sku(self, sku_str):
        return re.sub(r'[\'"]', '', sku_str).strip() if sku_str else None

    def scrape_academy(self, url, max_retries=3):
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0"
        ]
        for attempt in range(max_retries):
            browser = None
            try:
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=False, args=['--disable-blink-features=AutomationControlled'])
                    context = browser.new_context(
                        viewport={"width": 1280, "height": 720},
                        user_agent=random.choice(user_agents),
                        java_script_enabled=True,
                        bypass_csp=True,
                        locale="en-US",
                        permissions=['geolocation'],
                        geolocation={'latitude': 37.7749, 'longitude': -122.4194},  # Example: San Francisco
                        timezone_id="America/Los_Angeles"
                    )
                    context.set_extra_http_headers({
                        "Accept-Language": "en-US,en;q=0.9",
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                        "Accept-Encoding": "gzip, deflate, br",
                        "Connection": "keep-alive",
                        "Upgrade-Insecure-Requests": "1"
                    })
                    page = context.new_page()
                    page.goto(url, wait_until="domcontentloaded", timeout=40000)

                    # Check for CAPTCHA
                    if 'captcha' in page.url.lower():
                        logging.warning(f"CAPTCHA detected at {page.url}. Waiting 30s for manual solving...")
                        page.wait_for_timeout(30000)  # Pause for manual CAPTCHA solving
                        if 'captcha' in page.url.lower():
                            logging.error("CAPTCHA not solved. Aborting.")
                            browser.close()
                            return None

                    page.wait_for_selector('span.fwBold', timeout=15000)
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    page.wait_for_timeout(15000)
                    html = page.content()
                    browser.close()
                    browser = None

                soup = BeautifulSoup(html, 'html.parser')
                name_elem = soup.select_one('span.class.productTitle--FWmuK')
                name = name_elem.text.strip() if name_elem else "Unknown Product"
                price_elem = soup.select_one('div.was-now-price > div > span')
                price = self.clean_price(price_elem.text) if price_elem else 0.0

                # SKU extraction
                sku = None
                sku_elem = soup.select_one('span.fwBold + span')
                if sku_elem and sku_elem.text.strip():
                    sku = self.clean_sku(sku_elem.text)
                    logging.info(f"SKU found with selector 'span.fwBold + span': {sku}")

                # Fallback: Text-based search
                if not sku:
                    logging.warning("SKU not found with selector. Trying text-based search.")
                    sku_span = soup.find('span', text=re.compile(r'SKU[:\s]*', re.I))
                    if sku_span:
                        next_span = sku_span.find_next('span')
                        sku = self.clean_sku(next_span.text) if next_span else None
                        if sku:
                            logging.info(f"SKU found with text-based search: {sku}")

                # Debug if SKU not found
                if not sku:
                    logging.warning("SKU still not found. HTML snippet:")
                    sku_container = soup.find('span', class_='fwBold')
                    if sku_container:
                        parent = sku_container.find_parent('div')
                        logging.warning(str(parent) if parent else str(sku_container))
                    else:
                        logging.warning("No fwBold span found")

                return {
                    "name": name,
                    "price": price,
                    "sku": sku,
                    "category": "Shoes"
                }
            except (PlaywrightTimeoutError, Exception) as e:
                logging.warning(f"Attempt {attempt + 1} failed for {url}: {str(e)}")
                if browser:
                    browser.close()
                if attempt + 1 == max_retries:
                    logging.error(f"Error scraping {url} after {max_retries} attempts: {str(e)}")
                    return None
                logging.info(f"Retrying after 5 seconds...")
                time.sleep(5000)

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