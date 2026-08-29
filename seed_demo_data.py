"""
Seeds the database with demo student accounts and sample complaints across
every category, priority, and status — useful for populating your dashboard
before a demo/viva so it doesn't look empty.

Run this from the Bash console:
    python seed_demo_data.py

Safe to run multiple times — it skips creating a demo student if one with
that email already exists, but will still add fresh complaints each time
you run it (so don't run it repeatedly unless you want more data).
"""

from datetime import datetime, timedelta
from app import app, db
from models import User, Complaint, DEPARTMENT_MAP
from ml.predict import classify_complaint

DEMO_STUDENTS = [
    {"name": "Ananya Rao", "email": "ananya.demo@sitmangalore.edu", "room_number": "112"},
    {"name": "Rohit Shetty", "email": "rohit.demo@sitmangalore.edu", "room_number": "204"},
    {"name": "Sneha Kamath", "email": "sneha.demo@sitmangalore.edu", "room_number": "308"},
]

DEMO_COMPLAINTS = [
    # (title, description, target_status)
    ("Fan sparking in room", "The ceiling fan in my room 112 is sparking and making a burning smell since this morning. It feels dangerous to leave it on.", "Pending"),
    ("No water supply since morning", "There has been no water supply in the bathroom on our floor since 7 AM today. Several students are affected.", "Pending"),
    ("WiFi extremely slow in hostel block", "The wifi speed in Block A has been under 1 mbps for the past two days, making it impossible to attend online classes.", "In Progress"),
    ("Mess food quality complaint", "Found a hair in my food today at lunch and the rice was undercooked. This has happened a few times this week.", "In Progress"),
    ("Washbasin pipe leaking", "The washbasin pipe in the common bathroom has been leaking continuously for two days, flooding the floor.", "Pending"),
    ("Tube light flickering constantly", "The tube light in the study room keeps flickering on and off, making it hard to study in the evenings.", "Resolved"),
    ("Toilet flush not working", "The toilet flush in the third floor common washroom has not been working properly for the last three days.", "Resolved"),
    ("Request for extra dustbins", "Requesting a couple of extra dustbins to be placed in the hostel corridor near room 300, as the current one overflows quickly.", "Pending"),
    ("Wifi router down entire wing", "The wifi router for our entire wing has been completely down since yesterday night, no internet access at all.", "In Progress"),
    ("Buttermilk served was sour", "The buttermilk served during breakfast today had gone sour and tasted off. Please check the storage.", "Resolved"),
    ("Power socket sparking near study table", "The power socket near my study table sparks whenever I plug in my laptop charger, it's an urgent safety issue.", "Pending"),
    ("Water leakage from bathroom ceiling", "There is water leaking from the bathroom ceiling into the room below, causing damage since last week.", "In Progress"),
]

with app.app_context():
    db.create_all()

    student_objs = []
    for s in DEMO_STUDENTS:
        existing = User.query.filter_by(email=s["email"]).first()
        if existing:
            student_objs.append(existing)
            continue
        user = User(
            name=s["name"],
            email=s["email"],
            room_number=s["room_number"],
            role="student",
            email_verified=True,
        )
        user.set_password("Demo@Pass123")
        db.session.add(user)
        db.session.commit()
        student_objs.append(user)
        print(f"Created demo student: {s['email']} / Demo@Pass123")

    created_count = 0
    for i, (title, text, target_status) in enumerate(DEMO_COMPLAINTS):
        student = student_objs[i % len(student_objs)]
        result = classify_complaint(title, text)
        category = result["category"]

        complaint = Complaint(
            student_id=student.id,
            title=title,
            text=text,
            category=category,
            confidence=result["confidence"],
            priority=result["priority"],
            department=DEPARTMENT_MAP.get(category, "General Administration"),
            status=target_status,
            ai_predicted_category=result["category"],
            ai_predicted_priority=result["priority"],
            priority_explanation=result["priority_explanation"],
            low_confidence=result["low_confidence"],
            created_at=datetime.utcnow() - timedelta(hours=(len(DEMO_COMPLAINTS) - i) * 3),
        )
        if target_status == "Resolved":
            complaint.resolved_at = complaint.created_at + timedelta(hours=6)
            complaint.admin_notes = "Issue fixed by maintenance staff."

        db.session.add(complaint)
        created_count += 1

    db.session.commit()
    print(f"\nSeeded {created_count} demo complaints across {len(student_objs)} demo students.")
    print("Demo student login: any of the emails above, password: Demo@Pass123")
