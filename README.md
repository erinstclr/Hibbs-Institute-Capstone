# Hibbs Rental Dashboard

A Flask-based rental market dashboard for Texas ZIP codes using the RentCast API, MongoDB Atlas, and a simple authentication system (login, signup, security-question-based password reset). The app can optionally run inside a PyWebView desktop window for a nicer UI.

---

## Features

- User authentication (signup, login, logout)
- Security questions + 2-step "Forgot Password" flow
- Search by one or multiple ZIP codes
- RentCast API integration for rental market data
- MongoDB caching of ZIP results (avoids duplicate API calls)
- Results page with average & median rent per ZIP
- Optional PyWebView desktop window wrapper

---

## Tech Stack

- **Backend:** Python, Flask
- **Database:** MongoDB Atlas (cloud)
- **External API:** RentCast
- **Auth:** Simple username/password + security question (demo-level)
- **Desktop Wrapper (optional):** PyWebView

---

## Project Structure 

```text
.
Hibbs-Institute-Capstone/
│
├── Application/
│   ├── app.py                          # Main Flask application (auth, search, RentCast, webview)
│   ├── RentCastRequester.py            # Helper script for calling the RentCast API in batch/testing
│   ├── csv_file_merger.py              # Merges raw CSV rental data into unified datasets
│   ├── mongodb_csv_file_import.py      # Loads rental CSV data into MongoDB collections
│   ├── mongodb_python_search.py        # Standalone MongoDB search/query script (CLI)
│   ├── mongodb_user_login.py           # Initial login prototype (kept for reference)
│   ├── texas_rent_market_data(in).csv  # Raw rental dataset
│   ├── texas_rent_market_data_updated.csv # Cleaned/processed rental dataset
│   ├── texas_zipcode_list.csv          # Formatted list of Texas ZIP codes
│   ├── templates/
│   │   ├── LoginHibbs.html
│   │   ├── SignUp.html
│   │   ├── ForgotPassword.html
│   │   ├── SearchPage.html
│   │   └── Results.html
│   └── .env                            # Local environment variables (NOT committed to Git)
│
├── README.md
├── requirements.txt
└── .gitignore
