from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

DEPARTMENT_MAP = {
    "electrical": "Electrical Maintenance Dept.",
    "plumbing": "Plumbing / Civil Maintenance Dept.",
    "wifi": "IT / Network Dept.",
    "food": "Mess Committee",
    "other": "General Administration",
}


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="student")  # student / admin
    room_number = db.Column(db.String(20))
    email_verified = db.Column(db.Boolean, default=False, nullable=False)
    is_suspended = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    complaints = db.relationship("Complaint", backref="student", lazy=True,
                                  foreign_keys="Complaint.student_id")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_admin(self):
        return self.role == "admin"


class Complaint(db.Model):
    __tablename__ = "complaints"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    title = db.Column(db.String(150), nullable=False, default="")
    text = db.Column(db.Text, nullable=False)

    category = db.Column(db.String(50), nullable=False)
    confidence = db.Column(db.Float, default=0.0)
    priority = db.Column(db.String(20), nullable=False, default="Medium")
    department = db.Column(db.String(100))

    # Original AI predictions, preserved even if admin later corrects category/priority above.
    # This demonstrates human-in-the-loop AI verification for the report/viva.
    ai_predicted_category = db.Column(db.String(50))
    ai_predicted_priority = db.Column(db.String(20))
    priority_explanation = db.Column(db.Text)
    low_confidence = db.Column(db.Boolean, default=False, nullable=False)

    status = db.Column(db.String(20), nullable=False, default="Pending")  # Pending / In Progress / Resolved
    admin_notes = db.Column(db.Text)
    is_hidden = db.Column(db.Boolean, default=False, nullable=False)
    is_spam = db.Column(db.Boolean, default=False, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    resolved_at = db.Column(db.DateTime)

    def to_dict(self):
        return {
            "id": self.id,
            "student_name": self.student.name if self.student else None,
            "room_number": self.student.room_number if self.student else None,
            "text": self.text,
            "category": self.category,
            "confidence": self.confidence,
            "priority": self.priority,
            "department": self.department,
            "status": self.status,
            "admin_notes": self.admin_notes,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M") if self.created_at else None,
            "resolved_at": self.resolved_at.strftime("%Y-%m-%d %H:%M") if self.resolved_at else None,
        }
