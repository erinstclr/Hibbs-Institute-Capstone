# COSC 4375 Capstone Project: Hibbs Institute
# Zillow Web Scraper with Selenium - Full Details + Pagination
# Ethan Baker (9/29/2025)

import time
import random
import os
import csv
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager

# --- Selenium Setup ---
options = webdriver.ChromeOptions()
options.add_argument("--start-maximized")
options.add_argument("--disable-blink-features=AutomationControlled")
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

# --- Output CSV ---
CSV_FILE = "smith_county_full_listings.csv"

# Load existing data for resume
if os.path.exists(CSV_FILE):
    with open(CSV_FILE, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        scraped_urls = set(row['URL'] for row in reader)
    print(f"Resuming, {len(scraped_urls)} listings already saved.")
else:
    scraped_urls = set()

# --- Zillow Starting URL ---
url = "https://www.zillow.com/smith-county-tx/"
driver.get(url)
time.sleep(random.uniform(3, 6))

data = []

def save_progress():
    """Save progress to CSV"""
    with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["City","Zipcode","Address","Price",
                                               "Time on Market","Reviews","HOA","Year Built","URL"])
        writer.writeheader()
        writer.writerows(data)

def scrape_listings_on_page():
    """Scrape all listings on the current page"""
    # Scroll to load all listings
    for _ in range(3):
        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.END)
        time.sleep(random.uniform(2, 4))

    listings = driver.find_elements(By.CSS_SELECTOR, "a.property-card-link")

    for i, listing in enumerate(listings):
        try:
            link = listing.get_attribute("href")
            if not link or link in scraped_urls:
                continue

            # Open listing in new tab
            driver.execute_script("window.open(arguments[0]);", link)
            driver.switch_to.window(driver.window_handles[-1])
            time.sleep(random.uniform(3, 6))

            page = BeautifulSoup(driver.page_source, "html.parser")

            # Extract fields
            try:
                address = page.find("h1", {"data-testid": "address"}).text
            except: address = "N/A"

            try:
                price = page.find("span", {"data-testid": "price"}).text
            except: price = "N/A"

            try:
                city_zip = address.split(",")[-1].strip()
                zipcode = city_zip.split()[-1]
                city = city_zip.replace(zipcode, "").strip()
            except: city, zipcode = "N/A", "N/A"

            # Time on market
            try:
                time_on_market = page.find("span", string=lambda s: s and "days" in s.lower()).text
            except: time_on_market = "N/A"

            # HOA fees
            try:
                hoa = page.find(string=lambda s: "HOA" in s).parent.text
            except: hoa = "N/A"

            # Year built
            try:
                year_built = page.find(string=lambda s: "Built" in s).parent.text
            except: year_built = "N/A"

            # Reviews
            reviews = "N/A"

            data.append({
                "City": city,
                "Zipcode": zipcode,
                "Address": address,
                "Price": price,
                "Time on Market": time_on_market,
                "Reviews": reviews,
                "HOA": hoa,
                "Year Built": year_built,
                "URL": link
            })
            scraped_urls.add(link)

            # Save progress incrementally
            save_progress()

            # Close tab and switch back
            driver.close()
            driver.switch_to.window(driver.window_handles[0])

            print(f"Scraped listing: {address}")

        except Exception as e:
            print("Error scraping listing:", e)
            if len(driver.window_handles) > 1:
                driver.close()
                driver.switch_to.window(driver.window_handles[0])

# --- Pagination Loop ---
while True:
    scrape_listings_on_page()

    try:
        next_button = driver.find_element(By.XPATH, "//a[@title='Next page']")
        if next_button.is_enabled():
            time.sleep(random.uniform(3, 6))
            next_button.click()
            time.sleep(random.uniform(4, 7))
        else:
            print("No more pages.")
            break
    except:
        print("No next page found, finished scraping.")
        break

driver.quit()
print(f"✅ Finished! Total listings scraped: {len(scraped_urls)}")
