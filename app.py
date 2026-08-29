import os
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import (
    LoginManager, login_user, logout_user, login_required, current_user
)
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature

from models import db, User, Complaint, DEPARTMENT_MAP
from ml.predict import classify_complaint
from utils import validate_password_strength

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ---------- Anti-abuse settings ----------
MAX_COMPLAINTS_PER_DAY = 10          # per student
MIN_SECONDS_BETWEEN_SUBMISSIONS = 120  # 2-minute cooldown
DUPLICATE_SIMILARITY_THRESHOLD = 0.85  # 0-1, higher = stricter match
DUPLICATE_LOOKBACK_HOURS = 24

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-key-change-in-production")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'complaints.db')}"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# ---------- Mail configuration ----------
# Set these as real environment variables (e.g. in your WSGI file on
# PythonAnywhere) — never hardcode real credentials in this file.
app.config["MAIL_SERVER"] = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
app.config["MAIL_PORT"] = int(os.environ.get("MAIL_PORT", 587))
app.config["MAIL_USE_TLS"] = os.environ.get("MAIL_USE_TLS", "True") == "True"
app.config["MAIL_USERNAME"] = os.environ.get("MAIL_USERNAME", "")
app.config["MAIL_PASSWORD"] = os.environ.get("MAIL_PASSWORD", "")
app.config["MAIL_DEFAULT_SENDER"] = os.environ.get("MAIL_DEFAULT_SENDER", app.config["MAIL_USERNAME"])
# If mail isn't configured yet, suppress actual sending so the app doesn't crash —
# emails get printed to the console log instead.
app.config["MAIL_SUPPRESS_SEND"] = not bool(app.config["MAIL_USERNAME"])
app.config["ADMIN_NOTIFY_EMAIL"] = os.environ.get("ADMIN_NOTIFY_EMAIL", app.config["MAIL_USERNAME"])

mail = Mail(app)
serializer = URLSafeTimedSerializer(app.config["SECRET_KEY"])

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"


def send_email(to, subject, body):
    """Sends an email, or logs it to console if mail isn't configured yet."""
    if not to or not app.config["MAIL_USERNAME"]:
        print(f"[Email not sent - mail not configured] To: {to} | Subject: {subject}\n{body}")
        return
    try:
        msg = Message(subject=subject, recipients=[to], body=body)
        mail.send(msg)
    except Exception as e:
        print(f"Failed to send email to {to}: {e}")


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ---------- Auth ----------

@app.route("/")
def index():
    if current_user.is_authenticated:
        if current_user.is_admin():
            return redirect(url_for("admin_dashboard"))
        return redirect(url_for("student_dashboard"))
    return redirect(url_for("login"))


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        room_number = request.form.get("room_number", "").strip()
        role = "student"  # public registration can only ever create student accounts

        sticky = {"name": name, "email": email, "room_number": room_number}

        if not name or not email or not password:
            flash("All fields are required.", "error")
            return render_template("register.html", **sticky)

        if User.query.filter_by(email=email).first():
            flash("An account with this email already exists.", "error")
            return render_template("register.html", **sticky)

        is_valid, msg = validate_password_strength(password)
        if not is_valid:
            flash(msg, "error")
            return render_template("register.html", **sticky)

        user = User(name=name, email=email, room_number=room_number, role=role, email_verified=True)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash("Registration successful! You can now log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            if user.is_suspended:
                flash("Your account has been suspended due to policy violations. Contact hostel administration if you believe this is a mistake.", "error")
                return render_template("login.html", email=email)

            login_user(user)
            flash(f"Welcome back, {user.name}!", "success")
            if user.is_admin():
                return redirect(url_for("admin_dashboard"))
            return redirect(url_for("student_dashboard"))

        flash("Invalid email or password.", "error")
        return render_template("login.html", email=email)

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))


# ---------- Student ----------

@app.route("/student/dashboard")
@login_required
def student_dashboard():
    if current_user.is_admin():
        return redirect(url_for("admin_dashboard"))

    complaints = (
        Complaint.query.filter_by(student_id=current_user.id)
        .order_by(Complaint.created_at.desc())
        .all()
    )
    return render_template("student_dashboard.html", complaints=complaints)


@app.route("/student/submit", methods=["GET", "POST"])
@login_required
def submit_complaint():
    if current_user.is_admin():
        return redirect(url_for("admin_dashboard"))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        text = request.form.get("text", "").strip()
        manual_category = request.form.get("manual_category", "").strip()

        if not title or not text:
            flash("Please fill in both the complaint title and description.", "error")
            return redirect(url_for("submit_complaint"))

        if len(title) < 5:
            flash("Complaint title must be at least 5 characters.", "error")
            return redirect(url_for("submit_complaint"))

        if len(text) < 20:
            flash("Please provide a bit more detail in the description (at least 20 characters).", "error")
            return redirect(url_for("submit_complaint"))

        # ---- Anti-abuse check 1: cooldown between submissions ----
        last_complaint = (
            Complaint.query.filter_by(student_id=current_user.id)
            .order_by(Complaint.created_at.desc())
            .first()
        )
        if last_complaint:
            seconds_since_last = (datetime.utcnow() - last_complaint.created_at).total_seconds()
            if seconds_since_last < MIN_SECONDS_BETWEEN_SUBMISSIONS:
                wait_seconds = int(MIN_SECONDS_BETWEEN_SUBMISSIONS - seconds_since_last)
                flash(f"Please wait {wait_seconds} more seconds before submitting another complaint.", "error")
                return redirect(url_for("submit_complaint"))

        # ---- Anti-abuse check 2: daily cap ----
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        today_count = Complaint.query.filter(
            Complaint.student_id == current_user.id,
            Complaint.created_at >= today_start,
        ).count()
        if today_count >= MAX_COMPLAINTS_PER_DAY:
            flash(f"You've reached the daily limit of {MAX_COMPLAINTS_PER_DAY} complaints. Please try again tomorrow.", "error")
            return redirect(url_for("submit_complaint"))

        # ---- Anti-abuse check 3: near-duplicate detection ----
        combined_new = f"{title} {text}".lower()
        lookback_time = datetime.utcnow() - timedelta(hours=DUPLICATE_LOOKBACK_HOURS)
        recent_complaints = Complaint.query.filter(
            Complaint.student_id == current_user.id,
            Complaint.created_at >= lookback_time,
        ).all()
        for rc in recent_complaints:
            combined_old = f"{rc.title} {rc.text}".lower()
            similarity = SequenceMatcher(None, combined_new, combined_old).ratio()
            if similarity >= DUPLICATE_SIMILARITY_THRESHOLD:
                flash(
                    f"This looks very similar to a complaint you already submitted "
                    f"(TKT-{rc.id:04d}, status: {rc.status}). "
                    f"Please wait for a response instead of submitting duplicates.",
                    "error",
                )
                return redirect(url_for("submit_complaint"))

        result = classify_complaint(title, text)
        category = manual_category if manual_category else result["category"]

        complaint = Complaint(
            student_id=current_user.id,
            title=title,
            text=text,
            category=category,
            confidence=result["confidence"],
            priority=result["priority"],
            department=DEPARTMENT_MAP.get(category, "General Administration"),
            status="Pending",
            ai_predicted_category=result["category"],
            ai_predicted_priority=result["priority"],
            priority_explanation=result["priority_explanation"],
            low_confidence=result["low_confidence"],
        )
        db.session.add(complaint)
        db.session.commit()

        send_email(
            app.config.get("ADMIN_NOTIFY_EMAIL"),
            f"New Complaint TKT-{complaint.id:04d} - {category} ({result['priority']} priority)",
            f"A new complaint has been submitted.\n\n"
            f"Ticket: TKT-{complaint.id:04d}\n"
            f"Title: {title}\n"
            f"Student: {current_user.name} (Room {current_user.room_number or '-'})\n"
            f"Category: {category} ({result['confidence']}% confidence)\n"
            f"Priority: {result['priority']}\n"
            f"Department: {complaint.department}\n\n"
            f"Description:\n{text}\n\n"
            f"Log in to the admin dashboard to review and update its status.",
        )

        flash(
            f"Complaint submitted! Auto-classified as '{category}' "
            f"({result['confidence']}% confidence), priority: {result['priority']}.",
            "success",
        )
        return redirect(url_for("student_dashboard"))

    return render_template("submit_complaint.html", categories=list(DEPARTMENT_MAP.keys()))


@app.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not current_user.check_password(current_password):
            flash("Current password is incorrect.", "error")
            return redirect(url_for("change_password"))

        is_valid, msg = validate_password_strength(new_password)
        if not is_valid:
            flash(msg, "error")
            return redirect(url_for("change_password"))

        if new_password != confirm_password:
            flash("New password and confirmation do not match.", "error")
            return redirect(url_for("change_password"))

        current_user.set_password(new_password)
        db.session.commit()
        flash("Password updated successfully.", "success")
        if current_user.is_admin():
            return redirect(url_for("admin_dashboard"))
        return redirect(url_for("student_dashboard"))

    return render_template("change_password.html")


@app.route("/student/complaint/<int:complaint_id>/withdraw", methods=["POST"])
@login_required
def withdraw_complaint(complaint_id):
    if current_user.is_admin():
        return redirect(url_for("admin_dashboard"))

    complaint = Complaint.query.get_or_404(complaint_id)

    if complaint.student_id != current_user.id:
        flash("You can only withdraw your own complaints.", "error")
        return redirect(url_for("student_dashboard"))

    if complaint.status != "Pending":
        flash("This complaint is already being worked on and can no longer be withdrawn.", "error")
        return redirect(url_for("student_dashboard"))

    db.session.delete(complaint)
    db.session.commit()
    flash(f"Complaint #{complaint.id} has been withdrawn.", "success")
    return redirect(url_for("student_dashboard"))


# ---------- Admin ----------

def admin_required(func):
    from functools import wraps

    @wraps(func)
    @login_required
    def wrapper(*args, **kwargs):
        if not current_user.is_admin():
            flash("Admin access required.", "error")
            return redirect(url_for("student_dashboard"))
        return func(*args, **kwargs)

    return wrapper


@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    status_filter = request.args.get("status", "")
    category_filter = request.args.get("category", "")
    priority_filter = request.args.get("priority", "")
    show_hidden = request.args.get("show_hidden", "") == "1"
    show_spam_only = request.args.get("spam", "") == "1"

    query = Complaint.query
    if not show_hidden:
        query = query.filter_by(is_hidden=False)
    if show_spam_only:
        query = query.filter_by(is_spam=True)

    if status_filter:
        query = query.filter_by(status=status_filter)
    if category_filter:
        query = query.filter_by(category=category_filter)
    if priority_filter:
        query = query.filter_by(priority=priority_filter)

    complaints = query.order_by(Complaint.created_at.desc()).all()

    base = Complaint.query.filter_by(is_hidden=False)
    total = base.count()
    pending = base.filter_by(status="Pending").count()
    in_progress = base.filter_by(status="In Progress").count()
    resolved = base.filter_by(status="Resolved").count()
    hidden_count = Complaint.query.filter_by(is_hidden=True).count()
    spam_count = Complaint.query.filter_by(is_spam=True).count()

    category_counts = {}
    for cat in DEPARTMENT_MAP.keys():
        category_counts[cat] = base.filter_by(category=cat).count()

    # ---- 30-day submission timeline ----
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    recent = Complaint.query.filter(Complaint.created_at >= thirty_days_ago).all()
    daily_counts = {}
    for c in recent:
        day_str = c.created_at.strftime("%Y-%m-%d")
        daily_counts[day_str] = daily_counts.get(day_str, 0) + 1
    timeline_labels = []
    timeline_values = []
    for i in range(29, -1, -1):
        d = (datetime.utcnow() - timedelta(days=i)).strftime("%Y-%m-%d")
        timeline_labels.append(d[5:])  # MM-DD
        timeline_values.append(daily_counts.get(d, 0))

    # ---- Average resolution time ----
    resolved_complaints = Complaint.query.filter(
        Complaint.status == "Resolved", Complaint.resolved_at.isnot(None)
    ).all()
    if resolved_complaints:
        total_hours = sum(
            (c.resolved_at - c.created_at).total_seconds() / 3600 for c in resolved_complaints
        )
        avg_resolution_hours = round(total_hours / len(resolved_complaints), 1)
    else:
        avg_resolution_hours = 0

    return render_template(
        "admin_dashboard.html",
        complaints=complaints,
        total=total,
        pending=pending,
        in_progress=in_progress,
        resolved=resolved,
        hidden_count=hidden_count,
        spam_count=spam_count,
        show_hidden=show_hidden,
        show_spam_only=show_spam_only,
        category_counts=category_counts,
        categories=list(DEPARTMENT_MAP.keys()),
        timeline_labels=timeline_labels,
        timeline_values=timeline_values,
        avg_resolution_hours=avg_resolution_hours,
        current_filters={
            "status": status_filter,
            "category": category_filter,
            "priority": priority_filter,
        },
    )


@app.route("/admin/complaint/<int:complaint_id>/update", methods=["POST"])
@admin_required
def update_complaint(complaint_id):
    complaint = Complaint.query.get_or_404(complaint_id)
    new_status = request.form.get("status")
    admin_notes = request.form.get("admin_notes", "").strip()

    if new_status in ("Pending", "In Progress", "Resolved"):
        complaint.status = new_status
        if new_status == "Resolved" and not complaint.resolved_at:
            complaint.resolved_at = datetime.utcnow()
        elif new_status != "Resolved":
            complaint.resolved_at = None

    if admin_notes:
        complaint.admin_notes = admin_notes

    db.session.commit()
    flash(f"Complaint #{complaint.id} updated.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/complaint/<int:complaint_id>/correct", methods=["POST"])
@admin_required
def correct_classification(complaint_id):
    complaint = Complaint.query.get_or_404(complaint_id)
    new_category = request.form.get("final_category", "").strip()
    new_priority = request.form.get("final_priority", "").strip()

    if new_category and new_category in DEPARTMENT_MAP:
        complaint.category = new_category
        complaint.department = DEPARTMENT_MAP[new_category]

    if new_priority in ("High", "Medium", "Low"):
        complaint.priority = new_priority

    db.session.commit()
    flash(f"Complaint #{complaint.id} classification corrected by admin.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/complaint/<int:complaint_id>/hide", methods=["POST"])
@admin_required
def hide_complaint(complaint_id):
    complaint = Complaint.query.get_or_404(complaint_id)

    if complaint.status != "Resolved":
        flash("Only resolved complaints can be hidden.", "error")
        return redirect(url_for("admin_dashboard"))

    complaint.is_hidden = not complaint.is_hidden
    db.session.commit()
    flash(f"Complaint #{complaint.id} {'hidden' if complaint.is_hidden else 'unhidden'}.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/complaint/<int:complaint_id>/delete", methods=["POST"])
@admin_required
def delete_complaint(complaint_id):
    complaint = Complaint.query.get_or_404(complaint_id)

    if complaint.status != "Resolved":
        flash("Only resolved complaints can be deleted.", "error")
        return redirect(url_for("admin_dashboard"))

    db.session.delete(complaint)
    db.session.commit()
    flash(f"Complaint #{complaint_id} deleted permanently.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/complaint/<int:complaint_id>/spam", methods=["POST"])
@admin_required
def flag_spam(complaint_id):
    complaint = Complaint.query.get_or_404(complaint_id)
    complaint.is_spam = not complaint.is_spam
    db.session.commit()
    flash(f"Complaint #{complaint.id} marked as {'spam' if complaint.is_spam else 'not spam'}.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/user/<int:user_id>/suspend", methods=["POST"])
@admin_required
def suspend_user(user_id):
    user = User.query.get_or_404(user_id)

    if user.is_admin():
        flash("Admin accounts cannot be suspended.", "error")
        return redirect(url_for("admin_dashboard"))

    user.is_suspended = not user.is_suspended
    db.session.commit()
    flash(f"{user.name}'s account has been {'suspended' if user.is_suspended else 'reinstated'}.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/api/analytics")
@admin_required
def analytics():
    category_counts = {}
    for cat in DEPARTMENT_MAP.keys():
        category_counts[cat] = Complaint.query.filter_by(category=cat).count()

    status_counts = {
        "Pending": Complaint.query.filter_by(status="Pending").count(),
        "In Progress": Complaint.query.filter_by(status="In Progress").count(),
        "Resolved": Complaint.query.filter_by(status="Resolved").count(),
    }

    priority_counts = {
        "High": Complaint.query.filter_by(priority="High").count(),
        "Medium": Complaint.query.filter_by(priority="Medium").count(),
        "Low": Complaint.query.filter_by(priority="Low").count(),
    }

    return jsonify({
        "category_counts": category_counts,
        "status_counts": status_counts,
        "priority_counts": priority_counts,
    })


def create_default_admin():
    """Creates a default admin account if none exists (for demo purposes)."""
    admin = User.query.filter_by(role="admin").first()
    if not admin:
        admin = User(
            name="Admin",
            email="admin@sitmangalore.edu",
            role="admin",
            email_verified=True,
        )
        admin.set_password("admin123")
        db.session.add(admin)
        db.session.commit()
        print("Default admin created -> email: admin@sitmangalore.edu | password: admin123")


# Ensure DB tables + default admin exist whether run via `python app.py`
# or imported by a WSGI server like gunicorn (used on Render/PythonAnywhere).
with app.app_context():
    db.create_all()
    create_default_admin()


if __name__ == "__main__":
    app.run(debug=True, port=5000)
