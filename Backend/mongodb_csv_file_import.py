from pymongo import MongoClient
import pandas as pd
import os

# MongoDB Connection
client = MongoClient("mongodb+srv://hibbssponsoredproject_db_user:oJwwztzlmDDddnjc@hibbssponsoredproject.unhqzaj.mongodb.net/")
db = client["Rentcast"]
collection = db["Rentcast_Zipcodes"]

print("Input the CSV file name (include .csv extension):")
csv_file_path = input("csv file: ").strip()

# Validate the CSV File
if not os.path.exists(csv_file_path):
    print(f"Error: File '{csv_file_path}' not found.")
    exit()

try:
    df = pd.read_csv(csv_file_path)
except Exception as e:
    print(f"Error reading CSV file: {e}")
    exit()

# Define required columns
required_columns = {"ZipCode", "City", "County", "State", "LastUpdatedDate", "AverageRent", "MedianRent", "AverageRentPerSqFt", "MedianRentPerSqFt"}

# Check for missing columns
missing = required_columns - set(df.columns)
if missing:
    print(f"Error: CSV file is missing required column(s): {', '.join(missing)}")
    exit()

# Check for empty data
if df.empty:
    print("Error: CSV file is empty, no records to insert.")
    exit()

# Insert into MongoDB
data = df.to_dict(orient="records")
collection.insert_many(data)

# Verify
print(f"Successfully validated and inserted {len(data)} records into MongoDB.")
