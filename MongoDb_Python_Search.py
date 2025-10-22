from pymongo import MongoClient

# MongoDB connection
client = MongoClient("mongodb+srv://justinhaynie26_db_user:1234@hibbstestcluster.ik2lmok.mongodb.net/")
db = client["test"]
collection = db["TestHomePrices"]

print("Search Home Prices ")
print("(Leave any field blank to skip it.)\n")

# Gather user input
address = input("Address: ").strip()
price_input = input("Price: ").strip()
zipcode = input("Zipcode: ").strip()
city = input("City: ").strip()
county = input("County: ").strip()
state = input("State: ").strip()
date_modified = input("Date Modified: ").strip()

# Build the query
query = {}

if address:
    query["Address"] = address

if price_input:
    try:
        query["Price"] = float(price_input)
    except ValueError:
        print("Invalid price format. Skipping price filter.")

if zipcode:
    query["Zipcode"] = zipcode

if city:
    query["City"] = city

if county:
    query["County"] = county

if state:
    query["State"] = state

if date_modified:
    query["DateModified"] = date_modified  # I dont know how we're storied this yet, probably as datetime

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