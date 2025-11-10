from pymongo import MongoClient
from pymongo.errors import OperationFailure
import getpass

# Ask for login credentials
print("MongoDB Login")
username = input("Username: ")
password = getpass.getpass("Password (hidden): ")

# Build the connection string
cluster_url = "hibbstestcluster.ik2lmok.mongodb.net"  # Cluster address
database_name = "test"

uri = f"mongodb+srv://{username}:{password}@{cluster_url}/?retryWrites=true&w=majority"

# Attempt to connect 
try:
    client = MongoClient(uri)
    db = client[database_name]
    
    # Verify credentials
    db.command("ping")
    print(f"\nSuccessfully logged in and connected to database: '{database_name}'")

except OperationFailure:
    print("\nLogin failed: Incorrect username or password.")
    exit()
except Exception as e:
    print(f"\nConnection error: {e}")
    exit()

# Use the database
collection = db["TestHomePrices"]

print(f"\nReady to use collection: {collection.name}")
