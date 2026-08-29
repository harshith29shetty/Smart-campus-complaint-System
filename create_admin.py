"""
Creates an admin account. Run this from the Bash console — it is NOT a web
route, so there's no way for the public to reach it. This is the only way
to create additional admin accounts (the registration page only ever
creates student accounts, on purpose).

Usage:
    python create_admin.py
Then follow the prompts.
"""

from app import app, db
from models import User

with app.app_context():
    db.create_all()

    name = input("Admin name: ").strip()
    email = input("Admin email: ").strip().lower()
    password = input("Admin password: ").strip()

    if User.query.filter_by(email=email).first():
        print(f"An account with email '{email}' already exists.")
    else:
        from utils import validate_password_strength
        is_valid, msg = validate_password_strength(password)
        if not is_valid:
            print(f"Password rejected: {msg}")
        else:
            admin = User(name=name, email=email, role="admin", email_verified=True)
            admin.set_password(password)
            db.session.add(admin)
            db.session.commit()
            print(f"Admin account created: {email}")
