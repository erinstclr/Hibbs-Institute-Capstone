from pymongo import MongoClient

# MongoDB connection
client = MongoClient("mongodb+srv://justinhaynie26_db_user:1234@hibbstestcluster.ik2lmok.mongodb.net/")
db = client["test"]
collection = db["TestHomePrices"]

print("Search Home Prices ")
print("(Leave any field blank to skip it.)\n")

# Gather user input
# address = input("Address: ").strip() This line does not exist in the sample data
# price_input = input("Price: ").strip() This line does not exist in the sample data
zipcode = input("Zipcode: ").strip()
city = input("City: ").strip()
county = input("County: ").strip()
state = input("State: ").strip()
date_modified = input("Date Modified: ").strip()
average_rent = input("Average Rent: ").strip()
median_rent = input("Median Rent: ").strip()
average_rent_per_sq_ft = input("Average Rent Per Sq Ft: ").strip()
median_rent_per_sq_ft = input("Median Rent Per Sq Ft: ").strip()

# Build the query
query = {}

# if address:
#    query["Address"] = address

# if price_input:
#    try:
#        query["Price"] = float(price_input)
#    except ValueError:
#        print("Invalid price format. Skipping price filter.")

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

if average_rent:
    try:
        query["Average Rent"] = float(average_rent)
    except ValueError:
        print("Invalid Average Rent format. Skipping Average Rent filter.")

if median_rent:
    try:
        query["Median Rent"] = float(median_rent)
    except ValueError:
        print("Invalid Median Rent format. Skipping Median Rent filter.")

if average_rent_per_sq_ft:
    try:
        query["Average Rent Per Sq Ft"] = float(average_rent_per_sq_ft)
    except ValueError:
        print("Invalid Average Rent Per Sq Ft format. Skipping Average Rent Per Sq Ft filter.")

if median_rent_per_sq_ft:
    try:
        query["Median Rent Per Sq Ft"] = float(median_rent_per_sq_ft)
    except ValueError:
        print("Invalid Median Rent Per Sq Ft format. Skipping Median Rent Per Sq Ft filter.")

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
