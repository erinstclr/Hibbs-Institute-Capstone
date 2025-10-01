from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import csv
import time
import pandas as pd

# Set up the Chrome driver
service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service)

# List of East Texas counties (based on common definitions: 38 counties)
east_texas_counties = [
    'Anderson County', 'Angelina County', 'Bowie County', 'Camp County', 'Cass County',
    'Cherokee County', 'Delta County', 'Franklin County', 'Gregg County', 'Hardin County',
    'Harrison County', 'Henderson County', 'Hopkins County', 'Houston County', 'Jasper County',
    'Jefferson County', 'Lamar County', 'Marion County', 'Morris County', 'Nacogdoches County',
    'Newton County', 'Orange County', 'Panola County', 'Polk County', 'Rains County',
    'Red River County', 'Rusk County', 'Sabine County', 'San Augustine County', 'San Jacinto County',
    'Shelby County', 'Smith County', 'Titus County', 'Trinity County', 'Tyler County',
    'Upshur County', 'Van Zandt County', 'Wood County'
]

# Function to scrape data for a single county
def scrape_county(county_name):
    county_slug = county_name.replace(' ', '+').replace('.', '')  # e.g., 'Smith+County'
    url = f"https://trerc.tamu.edu/data/housing-activity/?data-County={county_slug}"
    
    try:
        driver.get(url)
        wait = WebDriverWait(driver, 15)
        table = wait.until(EC.presence_of_element_located((By.TAG_NAME, "table")))
        
        # Extract headers
        headers = [th.text.strip() for th in table.find_elements(By.TAG_NAME, "th")]
        
        # Extract rows
        rows = []
        for tr in table.find_elements(By.TAG_NAME, "tr")[1:]:  # Skip header
            cells = [td.text.strip() for td in tr.find_elements(By.TAG_NAME, "td")]
            if len(cells) == len(headers):  # Ensure full row
                rows.append(cells + [county_name])  # Add county name as extra column
        
        time.sleep(2)  # Be respectful to the server
        return rows, headers
    except Exception as e:
        print(f"Error scraping {county_name}: {e}")
        return [], []

# Collect all data
all_rows = []
master_headers = None

for county in east_texas_counties:
    print(f"Scraping {county}...")
    rows, headers = scrape_county(county)
    if rows:
        if master_headers is None:
            master_headers = headers + ['County']
        all_rows.extend(rows)

# Save to CSV
if all_rows and master_headers:
    filename = "east_texas_housing_activity.csv"
    with open(filename, 'w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(master_headers)
        writer.writerows(all_rows)
    
    print(f"Aggregated data for all East Texas counties saved to {filename}")
    
    # Optional: Preview with pandas
    df = pd.DataFrame(all_rows, columns=master_headers)
    print("\nDataset shape:", df.shape)
    print("\nColumns:", list(df.columns))
    print("\nSample data:\n", df.head())
else:
    print("No data scraped. Check selectors or connectivity.")

driver.quit()
