import os
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
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

# --- ROLE-BASED ACCESS CONTROL DECORATOR ---
def login_required(role):
    def wrapper(fn):
        @wraps(fn)
        def decorated_view(*args, **kwargs):
            if 'user_id' not in session:
                flash("Please log in to access this page.")
                return redirect(url_for('login'))
            if session.get('role') != role:
                flash("Access denied. You do not have the required permissions.")
                # Send them back to their own dashboard
                if session.get('role') == 'student':
                    return redirect(url_for('student_dashboard'))
                elif session.get('role') == 'examiner':
                    return redirect(url_for('examiner_dashboard'))
                return redirect(url_for('login'))
            return fn(*args, **kwargs)
        return decorated_view
    return wrapper

# --- AUTHENTICATION ROUTES ---

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']
        
        # Enforce constraint: Admin cannot be registered via the portal
        if role == 'admin':
            flash("Admin registration is not permitted.")
            return redirect(url_for('register'))
            
        # Check if user already exists
        if User.query.filter_by(username=username).first():
            flash("Username already exists. Please choose another.")
            return redirect(url_for('register'))
            
        # Hash password and create user
        hashed_password = generate_password_hash(password)
        
        # Examiners require admin approval, so default status is 'pending'
        # Students are automatically 'approved'
        status = 'pending' if role == 'examiner' else 'approved'
        
        new_user = User(username=username, password=hashed_password, role=role, status=status)
        db.session.add(new_user)
        db.session.commit()
        
        flash("Registration successful! Please log in.")
        return redirect(url_for('login'))
        
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.query.filter_by(username=username).first()
        
        # Admin has a plain text default password based on our DB setup, 
        # but regular users have hashed passwords. We check both.
        if user and (check_password_hash(user.password, password) or user.password == password):
            if user.status == 'pending':
                flash("Your account is pending Admin approval.")
                return redirect(url_for('login'))
                
            # Log the user in by storing data in the session
            session['user_id'] = user.id
            session['role'] = user.role
            
            # Route to appropriate dashboards based on role
            if user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif user.role == 'examiner':
                return redirect(url_for('examiner_dashboard'))
            elif user.role == 'student':
                return redirect(url_for('student_dashboard'))
                
        flash("Invalid username or password.")
        return redirect(url_for('login'))
        
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# Placeholder routes for dashboards to prevent crash on successful login
@app.route('/admin_dashboard')
@login_required(role='admin')
def admin_dashboard():
    # Fetching all required statistics for the admin dashboard
    course_count = Course.query.count()
    exam_count = Examination.query.count()
    student_count = User.query.filter_by(role='student').count()
    examiner_count = User.query.filter_by(role='examiner').count()
    slot_count = ExaminationSlot.query.count()
    booking_count = Booking.query.count()
    
    return render_template('admin_dashboard.html', 
                           course_count=course_count,
                           exam_count=exam_count,
                           student_count=student_count,
                           examiner_count=examiner_count,
                           slot_count=slot_count,
                           booking_count=booking_count)

@app.route('/student_dashboard')
@login_required(role='student')
def student_dashboard():
    # We will query actual available exams and bookings here in the next phase
    return render_template('student_dashboard.html')

@app.route('/examiner_dashboard')
@login_required(role='examiner')
def examiner_dashboard():
    # We will query assigned exams and slots here later
    return render_template('examiner_dashboard.html')
# --- ROLE-BASED ACCESS CONTROL DECORATOR ---
def login_required(role):
    def wrapper(fn):
        @wraps(fn)
        def decorated_view(*args, **kwargs):
            if 'user_id' not in session:
                flash("Please log in to access this page.")
                return redirect(url_for('login'))
            if session.get('role') != role:
                flash("Access denied. You do not have the required permissions.")
                # Send them back to their own dashboard
                if session.get('role') == 'student':
                    return redirect(url_for('student_dashboard'))
                elif session.get('role') == 'examiner':
                    return redirect(url_for('examiner_dashboard'))
                return redirect(url_for('login'))
            return fn(*args, **kwargs)
        return decorated_view
    return wrapper
# Home route
@app.route('/')
def home():
    # If the user is already logged in, send them to their specific dashboard
    if 'user_id' in session:
        if session.get('role') == 'admin':
            return redirect(url_for('admin_dashboard'))
        elif session.get('role') == 'examiner':
            return redirect(url_for('examiner_dashboard'))
        elif session.get('role') == 'student':
            return redirect(url_for('student_dashboard'))
            
    # Otherwise, send them to the login page
    return redirect(url_for('login'))
# Run app
if __name__ == '__main__':
    app.run(debug=True)