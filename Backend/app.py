from flask import Flask, render_template, request, redirect, url_for, session
from pymongo import MongoClient
import certifi
import requests
import re
from datetime import datetime
from dotenv import load_dotenv
import os

# ===========================================================
#   Load environment variables
# ===========================================================
load_dotenv()  # Loads the .env file

MONGO_URI = os.getenv("MONGO_URI")
RENTCAST_API_KEY = os.getenv("RENTCAST_API_KEY")
SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "fallback_secret_key")

# Safety checks (optional but helpful)
if not MONGO_URI:
    raise ValueError("❌ Missing MONGO_URI in your .env file")

if not RENTCAST_API_KEY:
    raise ValueError("❌ Missing RENTCAST_API_KEY in your .env file")

# -----------------------------
#    Flask Setup
# -----------------------------
app = Flask(__name__)
app.secret_key = SECRET_KEY  # Loaded from .env

# -----------------------------
#   MongoDB Setup (correct DB)
# -----------------------------
mongo_client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())

db = mongo_client["Rentcast"]
collection = db["Rentcast_Zipcodes"]
users_collection = db["Users"]

# ZIP validation
ZIP_RE = re.compile(r"^\d{5}$")

# -----------------------------------------------------------------
#  Security Questions (keys must match <option value=""> in signup
# -----------------------------------------------------------------
SECURITY_QUESTIONS = {
    "pet": "What is the name of your first pet?",
    "school": "What is the name of your elementary school?",
    "city": "In what city were you born?",
    "nickname": "What was your childhood nickname?"
}


# ===========================================================
#   RentCast API Fetch + MongoDB Cache
# ===========================================================
def fetch_or_cache_zip(zip_code: str):
    """Fetch rent data from cache or RentCast API."""

    # 1️⃣ Look in MongoDB first
    doc = collection.find_one({"ZipCode": int(zip_code)})
    if doc:
        doc["_id"] = str(doc["_id"])
        print(f"✓ Using cached data for ZIP {zip_code}")
        return doc

    print(f"🌐 Fetching new data from RentCast for ZIP {zip_code}")

    url = "https://api.rentcast.io/v1/markets"
    headers = {"X-Api-Key": RENTCAST_API_KEY, "Accept": "application/json"}
    params = {"zipCode": zip_code}

    response = requests.get(url, headers=headers, params=params)

    # Debug: print full JSON structure
    try:
        print("\n🔍 RAW API RESPONSE:", response.json(), "\n")
    except Exception:
        print("❌ Could not print JSON response")

    if response.status_code != 200:
        return {"error": f"RentCast API error {response.status_code}: {response.text}"}

    data = response.json()
    if not isinstance(data, list) or len(data) == 0:
        return {"error": "No data found for that ZIP code."}

    market = data[0]
    rental = market.get("rentalData", {}) or {}

    # Build consistent document format
    doc = {
        "ZipCode": int(zip_code),
        "City": market.get("city"),
        "County": market.get("county"),
        "State": market.get("state"),
        "LastUpdatedDate": rental.get("lastUpdatedDate") or datetime.now().isoformat(),
        "AverageRent": rental.get("averageRent"),
        "MedianRent": rental.get("medianRent"),
        "AverageRentPerSqFt": rental.get("averageRentPerSquareFoot"),
        "MedianRentPerSqFt": rental.get("medianRentPerSquareFoot")
    }

    # Store in Mongo
    collection.insert_one(doc)
    doc["_id"] = str(doc["_id"])

    return doc


# ===========================================================
#   Authentication Routes
# ===========================================================
@app.route("/", methods=["GET", "POST"])
def login():
    """Login page — users log in with username and password."""
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""

        user = users_collection.find_one({"username": username, "password": password})

        if not user:
            return render_template("LoginHibbs.html", error="Invalid username or password.")

        session["user"] = username
        session["zip_list"] = []
        return redirect(url_for("home"))

    return render_template("LoginHibbs.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    """
    Signup page — new users enter username, password, and security question/answer.
    (Your version does NOT require per-user API keys; it uses the global env key.)
    """
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm_password") or ""
        security_question = request.form.get("security_question") or ""
        security_answer = (request.form.get("security_answer") or "").strip()

        # Basic validations
        if not username:
            return render_template("SignUp.html", error="Username is required!")

        if password != confirm:
            return render_template("SignUp.html", error="Passwords do not match!")

        if users_collection.find_one({"username": username}):
            return render_template("SignUp.html", error="Username already exists!")

        if not security_question:
            return render_template("SignUp.html", error="Please select a security question.")

        if not security_answer:
            return render_template("SignUp.html", error="Please provide an answer to your security question.")

        # Store user in DB (plaintext for class project; hash in real apps)
        users_collection.insert_one({
            "username": username,
            "password": password,
            "security_question": security_question,   # e.g., "pet"
            "security_answer": security_answer        # their answer
        })

        return redirect(url_for("login"))

    # On GET, you might want to pass SECURITY_QUESTIONS to your template
    return render_template("SignUp.html", security_questions=SECURITY_QUESTIONS)


@app.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():
    """
    2-step flow using security questions:
    1) User enters username -> we show their security question.
    2) User answers + enters new password -> we verify & update.
    """
    if request.method == "POST":
        step = request.form.get("step", "lookup")

        # --- STEP 1: USERNAME LOOKUP ---
        if step == "lookup":
            username = (request.form.get("username") or "").strip()

            if not username:
                return render_template(
                    "ForgotPassword.html",
                    error="Please enter your username.",
                    show_reset=False
                )

            user = users_collection.find_one({"username": username})
            if not user:
                return render_template(
                    "ForgotPassword.html",
                    error="No account found with that username.",
                    show_reset=False
                )

            question_key = user.get("security_question")
            question_text = SECURITY_QUESTIONS.get(question_key, "Your security question.")

            # Show the question + second step inputs
            return render_template(
                "ForgotPassword.html",
                username=username,
                question_text=question_text,
                show_reset=True
            )

        # --- STEP 2: SECURITY ANSWER + NEW PASSWORD ---
        elif step == "reset":
            username = (request.form.get("username") or "").strip()
            security_answer = (request.form.get("security_answer") or "").strip()
            new_password = request.form.get("new_password") or ""
            confirm_password = request.form.get("confirm_password") or ""

            if not username:
                return render_template(
                    "ForgotPassword.html",
                    error="Missing username. Please start again.",
                    show_reset=False
                )

            user = users_collection.find_one({"username": username})
            if not user:
                return render_template(
                    "ForgotPassword.html",
                    error="No account found with that username.",
                    show_reset=False
                )

            question_key = user.get("security_question")
            question_text = SECURITY_QUESTIONS.get(question_key, "Your security question.")
            stored_answer = (user.get("security_answer") or "").strip()

            # Validate security answer
            if not security_answer:
                return render_template(
                    "ForgotPassword.html",
                    error="Please enter your security answer.",
                    username=username,
                    question_text=question_text,
                    show_reset=True
                )

            if security_answer != stored_answer:
                return render_template(
                    "ForgotPassword.html",
                    error="Security answer is incorrect.",
                    username=username,
                    question_text=question_text,
                    show_reset=True
                )

            # Validate new passwords
            if not new_password or not confirm_password:
                return render_template(
                    "ForgotPassword.html",
                    error="Please enter and confirm your new password.",
                    username=username,
                    question_text=question_text,
                    show_reset=True
                )

            if new_password != confirm_password:
                return render_template(
                    "ForgotPassword.html",
                    error="Passwords do not match.",
                    username=username,
                    question_text=question_text,
                    show_reset=True
                )

            # Update password in DB
            users_collection.update_one(
                {"_id": user["_id"]},
                {"$set": {"password": new_password}}
            )

            return render_template(
                "ForgotPassword.html",
                success="Password updated successfully. You can now log in.",
                show_reset=False
            )

    # GET: just show username input
    return render_template("ForgotPassword.html", show_reset=False)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ===========================================================
#   Main Search Interface
# ===========================================================
@app.route("/home", methods=["GET", "POST"])
def home():
    """Main search interface."""
    if "user" not in session:
        return redirect(url_for("login"))

    zip_list = session.get("zip_list", [])
    error = None

    if request.method == "POST":
        action = request.form.get("action")
        entered_zip = (request.form.get("zipcode") or "").strip()

        # Add ZIP
        if action == "add":
            if not ZIP_RE.match(entered_zip):
                error = "Enter a valid 5-digit ZIP."
            elif entered_zip in zip_list:
                error = "ZIP already in the list."
            else:
                zip_list.append(entered_zip)

        # Remove ZIP
        elif action == "remove":
            if entered_zip in zip_list:
                zip_list.remove(entered_zip)

        # Single ZIP quick search
        elif action and action.startswith("search_single_"):
            z = action.replace("search_single_", "")
            result = fetch_or_cache_zip(z)

            if result.get("error"):
                return render_template("SearchPage.html", zip_list=zip_list, error=result["error"])

            return render_template(
                "Results.html",
                multi_results=[result],
                labels=[z],
                avg_rents=[result.get("AverageRent")],
                median_rents=[result.get("MedianRent")],
            )

        # Search all ZIPs
        elif action == "search_all":
            zips_to_search = zip_list.copy()

            if entered_zip:
                if ZIP_RE.match(entered_zip):
                    zips_to_search = [entered_zip]
                else:
                    return render_template("SearchPage.html", zip_list=zip_list, error="Invalid ZIP.")

            if not zips_to_search:
                return render_template("SearchPage.html", zip_list=zip_list, error="Add ZIPs first.")

            results = [fetch_or_cache_zip(z) for z in zips_to_search]

            valid = [r for r in results if not r.get("error")]
            labels = [str(r["ZipCode"]) for r in valid]
            avg_rents = [r["AverageRent"] for r in valid]
            median_rents = [r["MedianRent"] for r in valid]

            return render_template(
                "Results.html",
                multi_results=results,
                labels=labels,
                avg_rents=avg_rents,
                median_rents=median_rents,
            )

        session["zip_list"] = zip_list

    return render_template("SearchPage.html", zip_list=zip_list, error=error)


# ===========================================================
#   Optional API Endpoint
# ===========================================================
@app.route("/api/search_zip/<zipcode>")
def api_search_zip(zipcode):
    # Uses the global API key from env
    return fetch_or_cache_zip(zipcode)


# ===========================================================
#   PYWEBVIEW Launcher
# ===========================================================
if __name__ == "__main__":
    import threading, time, webview

    def start_flask():
        app.run(host="127.0.0.1", port=5000, debug=False)

    threading.Thread(target=start_flask, daemon=True).start()
    time.sleep(1.2)

    webview.create_window(
        "Hibbs Rental Dashboard",
        "http://127.0.0.1:5000",
        width=1200,
        height=900,
        resizable=True
    )
    webview.start()
