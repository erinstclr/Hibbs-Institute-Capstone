from pymongo import MongoClient
import pandas

# MongoDB connection
client = MongoClient("mongodb+srv://User1:1234@hibbstestcluster.ik2lmok.mongodb.net/")
db = client["test"]
collection = db["TestHomePrices"]

print("Input the csv file name.")

csv_file_path = input("csv file: ").strip()

# Load CSV
df = pandas.read_csv(csv_file_path)

# Convert to dictionary and insert to database
data = df.to_dict(orient="records")
collection.insert_many(data)

# Verify
print(f"Inserted {len(data)} records successfully.")