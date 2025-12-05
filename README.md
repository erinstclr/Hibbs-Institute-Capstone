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

## Project Structure (simplified)

```text
.
├── app.py
├── requirements.txt
├── README.md
├── .env                # NOT committed to Git
└── templates/
    ├── LoginHibbs.html
    ├── SignUp.html
    ├── ForgotPassword.html
    ├── SearchPage.html
    └── Results.html
# Hibbs-Institute-Capstone
