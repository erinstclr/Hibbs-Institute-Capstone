from flask import Flask, render_template, request, redirect, url_for, session
from pymongo import MongoClient
import certifi
from dotenv import load_dotenv
import requests, os, re
from datetime import datetime

# --- Flask Setup ---
app = Flask(__name__)
app.secret_key = "your_secret_key"  # Change in production!

# --- Load environment variables ---
load_dotenv()

# --- MongoDB Connection ---
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://User1:1234@hibbstestcluster.ik2lmok.mongodb.net/")
mongo_client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
db = mongo_client["test"]
collection = db["TestHomePrices"]
users_collection = db["Users"]

# --- Regex for ZIP validation ---
ZIP_RE = re.compile(r"^\d{5}$")

# --- RentCast API call + MongoDB caching ---
def fetch_or_cache_zip(zip_code, api_key):
    """Fetch rent data from MongoDB cache or RentCast API if not present."""
    # Try to find existing data
    doc = collection.find_one({"ZipCode": int(zip_code)})
    if doc:
        print(f"✅ Using cached data for {zip_code}")
        doc["_id"] = str(doc["_id"])
        return doc

    print(f"🌐 Fetching data from RentCast for {zip_code} ...")
    url = "https://api.rentcast.io/v1/markets"
    headers = {"X-Api-Key": api_key, "Accept": "application/json"}
    params = {"zipCode": zip_code}

    response = requests.get(url, headers=headers, params=params)
    if response.status_code != 200:
        print(f"❌ API error: {response.status_code} {response.text}")
        return {"error": f"RentCast error {response.status_code}"}

    data = response.json()
    if isinstance(data, list) and data:
        market = data[0]
        rental = market.get("rentalData", {})
        doc = {
            "ZipCode": int(zip_code),
            "City": market.get("city"),
            "County": market.get("county"),
            "State": market.get("state"),
            "LastUpdatedDate": rental.get("lastUpdatedDate", datetime.now().isoformat()),
            "AverageRent": rental.get("averageRent"),
            "MedianRent": rental.get("medianRent"),
            "AverageRentPerSqFt": rental.get("averageRentPerSquareFoot"),
            "MedianRentPerSqFt": rental.get("medianRentPerSquareFoot")
        }
        # Cache in MongoDB
        collection.insert_one(doc)
        doc["_id"] = str(doc["_id"])
        return doc
    else:
        return {"error": "No data found for that ZIP."}


# ---------- ROUTES ----------

@app.route("/", methods=["GET", "POST"])
def login():
    """Login page — users log in with username and password."""
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        user = users_collection.find_one({"username": username, "password": password})
        if user:
            session["user"] = username
            session["api_key"] = user.get("api_key")  # store their RentCast key
            return redirect(url_for("home"))
        else:
            return render_template("LoginHibbs.html", error="Invalid credentials!")

    return render_template("LoginHibbs.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    """Signup page — new users enter username, password, and RentCast API key."""
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        confirm = request.form["confirm_password"]
        api_key = request.form["api_key"].strip()

        if password != confirm:
            return render_template("SignUp.html", error="Passwords do not match!")
        if users_collection.find_one({"username": username}):
            return render_template("SignUp.html", error="Username already exists!")
        if not api_key:
            return render_template("SignUp.html", error="Please provide your RentCast API key!")

        # Store user in DB (⚠️ plaintext password — hash this for production!)
        users_collection.insert_one({
            "username": username,
            "password": password,
            "api_key": api_key
        })
        return redirect(url_for("login"))

    return render_template("SignUp.html")


@app.route("/home", methods=["GET", "POST"])
def home():
    """Main search interface."""
    if "user" not in session:
        return redirect(url_for("login"))

    # initialize ZIP list
    if "zip_list" not in session:
        session["zip_list"] = []

    error = None

    if request.method == "POST":
        action = request.form.get("action")

        if action == "add":
            z = (request.form.get("zipcode") or "").strip()
            if not ZIP_RE.match(z):
                error = "Please enter a valid 5-digit ZIP code."
            elif z in session["zip_list"]:
                error = f"{z} is already in the list."
            else:
                session["zip_list"].append(z)
                session.modified = True

        elif action == "remove":
            z = request.form.get("zipcode")
            if z in session["zip_list"]:
                session["zip_list"].remove(z)
                session.modified = True

        elif action == "search_all":
            zips = session.get("zip_list", [])
            if not zips:
                error = "Add at least one ZIP before searching."
            else:
                api_key = session.get("api_key")
                if not api_key:
                    return render_template("SearchPage.html",
                                           zip_list=session["zip_list"],
                                           error="Missing RentCast API key.")
                results = [fetch_or_cache_zip(z, api_key) for z in zips]
                return render_template("Results.html", multi_results=results)

    return render_template("SearchPage.html", zip_list=session["zip_list"], error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# --- Optional JSON API for frontend integration ---
@app.route("/api/search_zip/<zipcode>")
def api_search_zip(zipcode):
    api_key = session.get("api_key")
    if not api_key:
        return {"error": "Missing API key"}, 403
    result = fetch_or_cache_zip(zipcode, api_key)
    return result


if __name__ == "__main__":
    app.run(debug=True)
