# Campus/Hostel Complaint Redressal System with Auto-Categorization

An MCA academic project: students submit complaints as free text; an NLP
classifier auto-categorizes them (electrical / plumbing / wifi / food / other)
and assigns a priority (High / Medium / Low). Admins get a dashboard with
filters, live status updates, and analytics charts.

## Tech Stack
- Backend: Flask, Flask-SQLAlchemy, Flask-Login
- ML/NLP: scikit-learn (TF-IDF + Logistic Regression), rule-based priority detection
- Database: SQLite
- Frontend: HTML/CSS/JS + Chart.js

## Project Structure
```
complaint_system/
├── app.py                  # Main Flask app (routes, auth, admin logic)
├── models.py                # SQLAlchemy models (User, Complaint)
├── requirements.txt
├── ml/
│   ├── dataset.py           # Labeled training data (300 complaints, 5 categories)
│   ├── priority.py          # Keyword-based priority detection
│   ├── train_model.py       # Trains + saves the classifier
│   ├── predict.py           # Loads model, classifies new complaints
│   └── saved_model/         # category_model.pkl, vectorizer.pkl (generated)
├── templates/                # Jinja2 HTML templates
├── static/css/style.css
└── instance/complaints.db    # SQLite DB (generated)
```

## Setup & Run

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Train the classifier (only needed once, or after editing dataset.py):
   ```
   cd ml
   python train_model.py
   cd ..
   ```
   This prints accuracy, a classification report, and confusion matrix —
   useful for your project report/viva.

3. Run the app:
   ```
   python app.py
   ```
   Visit http://127.0.0.1:5000

4. Default admin login (auto-created on first run):
   - Email: `admin@sitmangalore.edu`
   - Password: `admin123`

   Students register normally via the Register page.

## How the ML Part Works (for your viva)

- **Category classification**: complaint text → TF-IDF vectorization (unigrams +
  bigrams) → Logistic Regression → predicted category + confidence score.
  Trained on a self-labeled dataset of ~330 sample complaints since no public
  dataset exists for this domain (mention this in your report — it's a valid
  and common approach for niche classification tasks).
- **Priority detection**: rule-based keyword matching (urgency words like
  "urgent", "sparking", "no water since 2 days" → High; general issue words →
  Medium; request/suggestion phrasing → Low). Kept rule-based intentionally —
  it's fully explainable and doesn't need labeled priority data.
- **Department routing**: category → department is a simple fixed mapping
  (see `DEPARTMENT_MAP` in `models.py`).

## Extending It Further (optional, if you have extra time)
- Add email/SMS notification when a complaint is marked resolved
- Add student ability to edit/withdraw a complaint before it's picked up
- Swap Logistic Regression for an SVM or a small neural net to compare accuracy
- Deploy on Render/PythonAnywhere for a live demo link
- Add sentence-transformers embeddings instead of TF-IDF for a "we tried both,
  TF-IDF performed comparably with far less compute" comparison section in report

## New Features: Email Verification, Complaint Notifications, Strong Passwords, Admin Hide/Delete

### 1. Email verification on registration
When a student registers, they get a verification link emailed to them and
**cannot log in until they click it**. This ensures only real, owned email
addresses can create accounts. Verification links expire after 24 hours;
students can request a new one from the "Resend Verification" link shown if
they try to log in before verifying.

### 2. Email notification when a complaint is submitted
Every time a complaint is submitted, an email is automatically sent to the
admin notification address with the ticket number, category, priority, and
full complaint text.

### 3. Strong password enforcement
Both registration and "Change Password" now require: 8+ characters, at least
one uppercase letter, one lowercase letter, one number, and one special
character. Weak passwords are rejected with a specific error message.

### 4. Admin hide/delete (only after Resolved)
On the admin dashboard, once a complaint's status is set to **Resolved**,
"Hide" and "Delete" buttons appear next to it. This is intentional — you
can't hide/delete a complaint that's still Pending or In Progress, so nothing
active can be lost. Hidden complaints are excluded from the default admin
view but can be shown again via the "Show N hidden complaints" link. Delete
is permanent.

## Setting Up Email (required for verification + notifications to work)

Without this setup, the app still works fully — emails just get printed to
the server console log instead of actually sending (and, for account
verification, the verification link is also shown on-screen right after
registering so you can still complete the flow without SMTP). To make real
emails go out, you need an email account with SMTP access. The easiest free option is
Gmail with an **App Password** (not your normal Gmail password):

1. Go to your Google Account → Security → 2-Step Verification (turn it on if
   it isn't already — App Passwords require this).
2. Go to myaccount.google.com/apppasswords, create a new app password
   (name it "Complaint System"), and copy the 16-character password shown.
3. Set these environment variables wherever you deploy (see the WSGI file
   instructions in the deployment section below):
   ```
   MAIL_USERNAME = your.email@gmail.com
   MAIL_PASSWORD = the 16-character app password (no spaces)
   MAIL_DEFAULT_SENDER = your.email@gmail.com
   ADMIN_NOTIFY_EMAIL = your.email@gmail.com   (or a different address to receive complaint alerts)
   ```

**On PythonAnywhere**, add these lines to your WSGI configuration file
(`/var/www/yourusername_pythonanywhere_com_wsgi.py`), right before the
`sys.path` lines:
```python
import os
os.environ['MAIL_USERNAME'] = 'your.email@gmail.com'
os.environ['MAIL_PASSWORD'] = 'your16charapppassword'
os.environ['MAIL_DEFAULT_SENDER'] = 'your.email@gmail.com'
os.environ['ADMIN_NOTIFY_EMAIL'] = 'your.email@gmail.com'
```
Then save, and Reload the web app.

**Never commit real email credentials to a public GitHub repo.** For an
academic project on PythonAnywhere this WSGI-file approach is fine since only
you can see your own files there.

## Anti-Abuse Protections (against fake/spam complaint flooding)

Since this is a public-facing app, a few safeguards prevent students from
flooding the system with fake or excessive complaints:

1. **Minimum length check** — complaints under 15 characters are rejected
   (blocks empty/junk submissions).
2. **Cooldown between submissions** — a student must wait 2 minutes between
   complaints (blocks rapid-fire spam bots or button-mashing).
3. **Daily cap** — max 10 complaints per student per day (configurable via
   `MAX_COMPLAINTS_PER_DAY` at the top of `app.py`).
4. **Near-duplicate detection** — if a student's new complaint is highly
   similar (85%+ text match) to one they submitted in the last 24 hours,
   it's blocked with a message pointing to the existing ticket.
5. **Admin: Mark as Spam** — any complaint can be flagged as spam on the
   admin dashboard; flagged complaints are visually marked and can be
   filtered separately without needing to wait for "Resolved" status.
6. **Admin: Suspend user** — an admin can suspend a student's account
   directly from any of their complaint rows. Suspended accounts can't log
   in at all until an admin reinstates them. Admin accounts can't be
   suspended (built-in protection against accidental lockout).

These thresholds are intentionally generous for a real hostel/campus use
case — a genuinely aggrieved student reporting multiple real issues won't
be blocked, but scripted or spam-driven flooding will be.

## Features Adapted From a Reference Implementation

A few ideas were incorporated from a reference SmartCampus-style project after
review, adapted to fit this codebase's structure:

1. **Explainable priority engine** — priority decisions now include a
   human-readable explanation (e.g. "Contains urgent or safety-related
   indicators (\"sparking\", \"burning smell\"). The issue has also been
   ongoing (since yesterday), increasing urgency."). Shown to both students
   (on their ticket) and admins (hover "why?" in the table). Duration
   patterns (e.g. "since yesterday", "for three days") are detected via
   regex and escalate priority even without explicit urgency keywords.

2. **Human-in-the-loop AI correction** — the AI's original category and
   priority prediction (`ai_predicted_category`, `ai_predicted_priority`)
   is preserved permanently, separate from the "final" working values
   (`category`, `priority`) that admins can correct. If an admin overrides
   the AI's guess, the dashboard shows both side by side ("AI said:
   wifi") so the correction is transparent and auditable — a good talking
   point for your viva about human oversight of ML predictions.

3. **Low-confidence flagging** — complaints where the ML model's confidence
   is below 55% are flagged with a "low confidence" badge on the admin
   dashboard, prompting a closer look rather than blind trust in the
   auto-classification.

4. **30-day submission timeline + average resolution time** — the admin
   dashboard now shows a line chart of daily complaint volume over the
   last 30 days, plus an "Avg. Resolution Time" stat card computed from
   actual resolved-complaint timestamps.

## Notes for Your Report
- Include the confusion matrix + classification report screenshot from
  `train_model.py` output as your "model evaluation" section.
- Architecture diagram: Student → Complaint Form → NLP Classifier → DB →
  Admin Dashboard → Department (routing) → Resolution.
- This directly addresses a real SIT Mangalore hostel/campus use case, which
  is a strong answer if asked about real-world relevance.

## Deploying it as a live website

The app is already deployment-ready (uses `gunicorn`, reads `SECRET_KEY`/`DATABASE_URL`
from environment variables, auto-creates tables + admin account on startup).

### Option A: PythonAnywhere (easiest, fully browser-based, no GitHub needed)

1. Create a free account at pythonanywhere.com.
2. Go to the **Files** tab and upload the whole `complaint_system` folder
   (or use the **Consoles** tab, open a Bash console, and `git clone` if you push this to GitHub first).
3. Open a **Bash console** and run:
   ```
   cd complaint_system
   pip install --user -r requirements.txt
   cd ml && python train_model.py && cd ..
   ```
4. Go to the **Web** tab → **Add a new web app** → choose **Manual configuration** → Python 3.10.
5. In the generated WSGI config file, replace the content with:
   ```python
   import sys
   path = '/home/YOURUSERNAME/complaint_system'
   if path not in sys.path:
       sys.path.append(path)
   from app import app as application
   ```
6. Set the **Working directory** to `/home/YOURUSERNAME/complaint_system`.
7. Click **Reload**. Your site is live at `yourusername.pythonanywhere.com`.

### Option B: Render (Git-based, auto-deploys on every push)

1. Push this project to a GitHub repository.
2. Go to render.com → **New** → **Web Service** → connect your GitHub repo.
   Render will auto-detect the included `render.yaml`, or you can set manually:
   - Build command: `pip install -r requirements.txt && cd ml && python train_model.py`
   - Start command: `gunicorn app:app`
3. Render auto-generates a `SECRET_KEY` (already configured in `render.yaml`).
4. Deploy. You'll get a live URL like `campus-complaint-system.onrender.com`.
   Note: free tier services sleep after inactivity, so the first request after
   a while may take ~30 seconds to wake up — worth mentioning if demoing live.

### Important before deploying either way
- Change the default admin password after first login (currently `admin123`).
- SQLite works fine for a class demo, but data may reset on redeploys on some
  free platforms (Render's free tier has an ephemeral filesystem) — for a
  persistent live grading link, PythonAnywhere keeps your SQLite file intact
  since it's a real persistent disk.

