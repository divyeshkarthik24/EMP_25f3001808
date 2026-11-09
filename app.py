import os
from datetime import datetime
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

# App init
app = Flask(__name__)

# DB setup
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'emp.sqlite3')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'dev-secret-key-emp-2026'

# Init DB
db = SQLAlchemy(app)

# User model
class User(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False) # Needs hashing
    role = db.Column(db.String(20), nullable=False)      # Role types
    status = db.Column(db.String(20), default='approved') # Default status

# Course model
class Course(db.Model):
    __tablename__ = 'course'
    id = db.Column(db.Integer, primary_key=True)
    course_code = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    
    # Exam relation
    examinations = db.relationship('Examination', backref='course', lazy=True)

# Exam model
class Examination(db.Model):
    __tablename__ = 'examination'
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    exam_type = db.Column(db.String(50), nullable=False) # Exam type
    duration = db.Column(db.Integer, nullable=False)     # Minutes duration
    max_marks = db.Column(db.Integer, nullable=False)
    
    # Timeline settings
    slot_creation_start = db.Column(db.DateTime, nullable=False)
    slot_creation_end = db.Column(db.DateTime, nullable=False)
    booking_start = db.Column(db.DateTime, nullable=False)
    booking_end = db.Column(db.DateTime, nullable=False)
    
    # Rubric relation
    rubrics = db.relationship('ExaminationRubric', backref='examination', lazy=True)

# Rubric model
class ExaminationRubric(db.Model):
    __tablename__ = 'examination_rubric'
    id = db.Column(db.Integer, primary_key=True)
    examination_id = db.Column(db.Integer, db.ForeignKey('examination.id'), nullable=False)
    criterion_name = db.Column(db.String(100), nullable=False)
    max_marks = db.Column(db.Integer, nullable=False)
    weightage = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text)

# Slot model
class ExaminationSlot(db.Model):
    __tablename__ = 'examination_slot'
    id = db.Column(db.Integer, primary_key=True)
    examiner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    max_capacity = db.Column(db.Integer, nullable=False)
    available_seats = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default='Available') # Status state
    
    # Booking relation
    bookings = db.relationship('Booking', backref='slot', lazy=True)

# Booking model
class Booking(db.Model):
    __tablename__ = 'booking'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    slot_id = db.Column(db.Integer, db.ForeignKey('examination_slot.id'), nullable=False)
    booking_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='Booked') # Status state

# DB creation
with app.app_context():
    db.create_all()
    
    # Admin setup
    if not User.query.filter_by(role='admin').first():
        default_admin = User(username='admin', password='admin123', role='admin')
        db.session.add(default_admin)
        db.session.commit()
        print("Pre-existing Admin user created successfully.")

# Home route
@app.route('/')
def home():
    return "Examination Management Portal - Complete Database Active"

# Run app
if __name__ == '__main__':
    app.run(debug=True)