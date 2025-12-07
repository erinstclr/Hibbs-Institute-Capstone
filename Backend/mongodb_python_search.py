from pymongo import MongoClient
from dotenv import load_dotenv
import certifi
import os

# MongoDB connection
load_dotenv()  # Loads the .env file

MONGO_URI = os.getenv("MONGO_URI")
SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "fallback_secret_key")

# Safety checks (optional but helpful)
if not MONGO_URI:
    raise ValueError("Missing MONGO_URI in your .env file")

client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
db = client["Rentcast"]
collection = db["Rentcast_Zipcodes"]

print("Search Home Prices ")
print("(Leave any field blank to skip it.)\n")

# Gather user input
zipcode = input("ZipCode: ").strip()
city = input("City: ").strip()
county = input("County: ").strip()
state = input("State: ").strip()
average_rent = input("AverageRent: ").strip()
median_rent = input("MedianRent: ").strip()
average_rent_per_sq_ft = input("AverageRentPerSqFt: ").strip()
median_rent_per_sq_ft = input("MedianRentPerSqFt: ").strip()
date_modified = input("LastUpdatedDate: ").strip()

# Build the query
query = {}

if zipcode:
    try:
        query["ZipCode"] = int(zipcode)
    except ValueError:
        print("Invalid Zipcode format. Skipping Zipcode filter.")

if city:
    query["City"] = city

if county:
    query["County"] = county

if state:
    query["State"] = state

if average_rent:
    try:
        query["AverageRent"] = float(average_rent)
    except ValueError:
        print("Invalid AverageRent format. Skipping AverageRent filter.")

if median_rent:
    try:
        query["MedianRent"] = float(median_rent)
    except ValueError:
        print("Invalid MedianRent format. Skipping MedianRent filter.")

if average_rent_per_sq_ft:
    try:
        query["AverageRentPerSqFt"] = float(average_rent_per_sq_ft)
    except ValueError:
        print("Invalid AverageRentPerSqFt format. Skipping AverageRentPerSqFt filter.")

if median_rent_per_sq_ft:
    try:
        query["MedianRentPerSqFt"] = float(median_rent_per_sq_ft)
    except ValueError:
        print("Invalid MedianRentPerSqFt format. Skipping MedianRentPerSqFt filter.")

if date_modified:
    query["LastUpdatedDate"] = date_modified  # I dont know how we're storied this yet, probably as datetime

print("\n Searching with the filters:")
print(query)

# Execute the search
results = collection.find(query)

found_any = False
for doc in results:
    found_any = True
    print("\nFound Document")
    for key, value in doc.items():
        print(f"{key}: {value}")

if not found_any:

    print("\n No documents found matching your search.")


