from flask import Flask, render_template, request, redirect, url_for, session
from pymongo import MongoClient
import certifi
from dotenv import load_dotenv
import requests, os, re
from datetime import datetime

# --- Flask Setup ---
app = Flask(__name__)
app.secret_key = "enter your api key"  # Change in production!

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

# --- Security Questions (keys must match <option value=""> in signup template) ---
SECURITY_QUESTIONS = {
    "pet": "What is the name of your first pet?",
    "school": "What is the name of your elementary school?",
    "city": "In what city were you born?",
    "nickname": "What was your childhood nickname?"
}

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
        username = request.form.get("username") or ""
        password = request.form.get("password") or ""

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
    """Signup page — new users enter username, password, RentCast API key, and security question."""
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm_password") or ""
        api_key = (request.form.get("api_key") or "").strip()
        security_question = request.form.get("security_question") or ""
        security_answer = (request.form.get("security_answer") or "").strip()

        # Basic validations
        if not username:
            return render_template("SignUp.html", error="Username is required!")
        if password != confirm:
            return render_template("SignUp.html", error="Passwords do not match!")
        if users_collection.find_one({"username": username}):
            return render_template("SignUp.html", error="Username already exists!")
        if not api_key:
            return render_template("SignUp.html", error="Please provide your RentCast API key!")
        if not security_question:
            return render_template("SignUp.html", error="Please select a security question.")
        if not security_answer:
            return render_template("SignUp.html", error="Please provide an answer to your security question.")

        # Store user in DB (plaintext for project; hash in real apps)
        users_collection.insert_one({
            "username": username,
            "password": password,
            "api_key": api_key,
            "security_question": security_question,   # store the key (e.g., "pet")
            "security_answer": security_answer        # store the answer
        })
        return redirect(url_for("login"))

    return render_template("SignUp.html")


@app.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():
    """
    2-step flow:
    1) User enters username -> we show their security question.
    2) User answers + enters new password -> we verify & update.
    """
    if request.method == "POST":
        step = request.form.get("step", "lookup")

        # --- STEP 1: USERNAME LOOKUP ---
        if step == "lookup":
            username = (request.form.get("username") or "").strip()

            if not username:
                return render_template("ForgotPassword.html",
                                       error="Please enter your username.",
                                       show_reset=False)

            user = users_collection.find_one({"username": username})
            if not user:
                return render_template("ForgotPassword.html",
                                       error="No account found with that username.",
                                       show_reset=False)

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
                return render_template("ForgotPassword.html",
                                       error="Missing username. Please start again.",
                                       show_reset=False)

            user = users_collection.find_one({"username": username})
            if not user:
                return render_template("ForgotPassword.html",
                                       error="No account found with that username.",
                                       show_reset=False)

            question_key = user.get("security_question")
            question_text = SECURITY_QUESTIONS.get(question_key, "Your security question.")

            # Check security answer
            stored_answer = (user.get("security_answer") or "").strip()
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

            # Check passwords
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

            # Update password
            users_collection.update_one(
                {"_id": user["_id"]},
                {"$set": {"password": new_password}}
            )

            return render_template(
                "ForgotPassword.html",
                success="Password updated successfully. You can now log in.",
                show_reset=False
            )

    # GET: just show username form
    return render_template("ForgotPassword.html", show_reset=False)


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

        elif action and action.startswith("search_single_"):
            selected_zip = action.replace("search_single_", "")

            api_key = session.get("api_key")
            if not api_key:
                return render_template(
                    "SearchPage.html",
                    zip_list=session["zip_list"],
                    error="Missing RentCast API key."
                )

            result = fetch_or_cache_zip(selected_zip, api_key)

            if result.get("error"):
                labels = []
                avg_rents = []
                median_rents = []
                multi_results = [result]
            else:
                labels = [str(result.get("ZipCode"))]
                avg_rents = [result.get("AverageRent")]
                median_rents = [result.get("MedianRent")]
                multi_results = [result]

            return render_template(
                "Results.html",
                multi_results=multi_results,
                labels=labels,
                avg_rents=avg_rents,
                median_rents=median_rents
            )

        elif action == "search_all":
            typed_zip = (request.form.get("zipcode") or "").strip()

            if typed_zip:
                if not ZIP_RE.match(typed_zip):
                    error = "Please enter a valid 5-digit ZIP code."
                    return render_template("SearchPage.html",
                                           zip_list=session["zip_list"],
                                           error=error)
                zips = [typed_zip]
            else:
                zips = session.get("zip_list", [])

            if not zips:
                error = "Add at least one ZIP or type a ZIP before searching."
                return render_template("SearchPage.html",
                                       zip_list=session["zip_list"],
                                       error=error)

            api_key = session.get("api_key")
            if not api_key:
                return render_template("SearchPage.html",
                                       zip_list=session["zip_list"],
                                       error="Missing RentCast API key.")

            results = [fetch_or_cache_zip(z, api_key) for z in zips]

            valid_results = [r for r in results if not r.get("error")]
            labels = [str(r.get("ZipCode")) for r in valid_results]
            avg_rents = [r.get("AverageRent") for r in valid_results]
            median_rents = [r.get("MedianRent") for r in valid_results]

            return render_template("Results.html",
                                   multi_results=results,
                                   labels=labels,
                                   avg_rents=avg_rents,
                                   median_rents=median_rents)

    return render_template("SearchPage.html", zip_list=session["zip_list"], error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/api/search_zip/<zipcode>")
def api_search_zip(zipcode):
    api_key = session.get("api_key")
    if not api_key:
        return {"error": "Missing API key"}, 403
    result = fetch_or_cache_zip(zipcode, api_key)
    return result


if __name__ == "__main__":
    app.run(debug=True)
