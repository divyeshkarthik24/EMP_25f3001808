# Imports
import os
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

# Init App
app = Flask(__name__)

# DB Config
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'emp.sqlite3')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'dev-secret-key-emp-2026'

# Init DB
db = SQLAlchemy(app)

# --- MODELS ---

# User
class User(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False) 
    role = db.Column(db.String(20), nullable=False)      
    status = db.Column(db.String(20), default='approved') 

# Course
class Course(db.Model):
    __tablename__ = 'course'
    id = db.Column(db.Integer, primary_key=True)
    course_code = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    
    examinations = db.relationship('Examination', backref='course', lazy=True)

# Exam
class Examination(db.Model):
    __tablename__ = 'examination'
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    exam_type = db.Column(db.String(50), nullable=False) 
    duration = db.Column(db.Integer, nullable=False)     
    max_marks = db.Column(db.Integer, nullable=False)
    
    slot_creation_start = db.Column(db.DateTime, nullable=False)
    slot_creation_end = db.Column(db.DateTime, nullable=False)
    booking_start = db.Column(db.DateTime, nullable=False)
    booking_end = db.Column(db.DateTime, nullable=False)
    
    rubrics = db.relationship('ExaminationRubric', backref='examination', lazy=True)

# Rubric
class ExaminationRubric(db.Model):
    __tablename__ = 'examination_rubric'
    id = db.Column(db.Integer, primary_key=True)
    examination_id = db.Column(db.Integer, db.ForeignKey('examination.id'), nullable=False)
    criterion_name = db.Column(db.String(100), nullable=False)
    max_marks = db.Column(db.Integer, nullable=False)
    weightage = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text)

# Slot
class ExaminationSlot(db.Model):
    __tablename__ = 'examination_slot'
    id = db.Column(db.Integer, primary_key=True)
    examination_id = db.Column(db.Integer, db.ForeignKey('examination.id'), nullable=False) 
    examiner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    max_capacity = db.Column(db.Integer, nullable=False)
    available_seats = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default='Available')
    
    examination = db.relationship('Examination', backref='slots', lazy=True)
    bookings = db.relationship('Booking', backref='slot', lazy=True)

# Booking
class Booking(db.Model):
    __tablename__ = 'booking'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    slot_id = db.Column(db.Integer, db.ForeignKey('examination_slot.id'), nullable=False)
    booking_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='Booked') 
    
    marks_obtained = db.Column(db.Float, nullable=True) 
    feedback = db.Column(db.Text, nullable=True)

# Create DB
with app.app_context():
    db.create_all()
    # Create Admin
    if not User.query.filter_by(role='admin').first():
        default_admin = User(username='admin', password='admin123', role='admin')
        db.session.add(default_admin)
        db.session.commit()
        print("Admin generated.")

# --- RBAC_DECORATOR ---
def login_required(role):
    def wrapper(fn):
        @wraps(fn)
        def decorated_view(*args, **kwargs):
            # Check Login
            if 'user_id' not in session:
                flash("Please log in.")
                return redirect(url_for('login'))
            # Verify Role
            if session.get('role') != role:
                flash("Access denied.")
                if session.get('role') == 'student':
                    return redirect(url_for('student_dashboard'))
                elif session.get('role') == 'examiner':
                    return redirect(url_for('examiner_dashboard'))
                return redirect(url_for('login'))
            return fn(*args, **kwargs)
        return decorated_view
    return wrapper

# --- ROUTING ---

# Root
@app.route('/')
def home():
    if 'user_id' in session:
        if session.get('role') == 'admin':
            return redirect(url_for('admin_dashboard'))
        elif session.get('role') == 'examiner':
            return redirect(url_for('examiner_dashboard'))
        elif session.get('role') == 'student':
            return redirect(url_for('student_dashboard'))
    return redirect(url_for('login'))

# Register
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']
        
        # Block Admin
        if role == 'admin':
            flash("Admin registration denied.")
            return redirect(url_for('register'))
            
        # Check Duplicate
        if User.query.filter_by(username=username).first():
            flash("Username exists.")
            return redirect(url_for('register'))
            
        # Hash Password
        hashed_password = generate_password_hash(password)
        # Set Status
        status = 'pending' if role == 'examiner' else 'approved'
        
        # Save User
        new_user = User(username=username, password=hashed_password, role=role, status=status)
        db.session.add(new_user)
        db.session.commit()
        
        flash("Registration successful!")
        return redirect(url_for('login'))
    return render_template('register.html')

# Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # Fetch User
        user = User.query.filter_by(username=username).first()
        
        # Verify Auth
        if user and (check_password_hash(user.password, password) or user.password == password):
            # Check Approval
            if user.status == 'pending':
                flash("Pending Admin approval.")
                return redirect(url_for('login'))
                
            # Set Session
            session['user_id'] = user.id
            session['role'] = user.role
            
            # Route Role
            if user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif user.role == 'examiner':
                return redirect(url_for('examiner_dashboard'))
            elif user.role == 'student':
                return redirect(url_for('student_dashboard'))
                
        flash("Invalid credentials.")
        return redirect(url_for('login'))
    return render_template('login.html')

# Logout
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- ADMIN ---

# Admin Dash
@app.route('/admin_dashboard')
@login_required(role='admin')
def admin_dashboard():
    # Fetch Stats
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

# Setup Courses
@app.route('/admin/manage_courses', methods=['GET', 'POST'])
@login_required(role='admin')
def manage_courses():
    if request.method == 'POST':
        course_code = request.form['course_code'].strip()
        name = request.form['name'].strip()
        description = request.form['description'].strip()
        
        # Validate Input
        if not course_code or not name:
            flash("Required fields missing.")
            return redirect(url_for('manage_courses'))
            
        # Check Duplicate
        if Course.query.filter_by(course_code=course_code).first():
            flash("Course exists.")
            return redirect(url_for('manage_courses'))
            
        # Save Course
        new_course = Course(course_code=course_code, name=name, description=description)
        db.session.add(new_course)
        db.session.commit()
        
        flash("Course created.")
        return redirect(url_for('manage_courses'))
        
    courses = Course.query.all()
    return render_template('manage_courses.html', courses=courses)

# Setup Exams
@app.route('/admin/manage_exams', methods=['GET', 'POST'])
@login_required(role='admin')
def manage_exams():
    if request.method == 'POST':
        course_id = request.form['course_id']
        name = request.form['name'].strip()
        exam_type = request.form['exam_type']
        duration = request.form['duration']
        max_marks = request.form['max_marks']
        
        # Parse Dates
        fmt = '%Y-%m-%dT%H:%M'
        try:
            slot_start = datetime.strptime(request.form['slot_creation_start'], fmt)
            slot_end = datetime.strptime(request.form['slot_creation_end'], fmt)
            booking_start = datetime.strptime(request.form['booking_start'], fmt)
            booking_end = datetime.strptime(request.form['booking_end'], fmt)
        except ValueError:
            flash("Date error.")
            return redirect(url_for('manage_exams'))
            
        # Save Exam
        new_exam = Examination(
            course_id=course_id, name=name, exam_type=exam_type,
            duration=duration, max_marks=max_marks,
            slot_creation_start=slot_start, slot_creation_end=slot_end,
            booking_start=booking_start, booking_end=booking_end
        )
        db.session.add(new_exam)
        db.session.commit()
        
        flash("Exam created.")
        return redirect(url_for('manage_exams'))
        
    courses = Course.query.all()
    exams = Examination.query.all()
    return render_template('manage_exams.html', courses=courses, exams=exams)

# Pending List
@app.route('/admin/approve_examiners')
@login_required(role='admin')
def approve_examiners():
    pending_examiners = User.query.filter_by(role='examiner', status='pending').all()
    return render_template('approve_examiners.html', pending_examiners=pending_examiners)

# Approve Action
@app.route('/admin/approve_examiner/<int:user_id>', methods=['POST'])
@login_required(role='admin')
def approve_examiner_action(user_id):
    # Fetch User
    examiner = db.get_or_404(User, user_id) 
    
    # Update Status
    if examiner.role == 'examiner' and examiner.status == 'pending':
        examiner.status = 'approved'
        db.session.commit()
        flash("Examiner approved.")
        
    return redirect(url_for('approve_examiners'))

# --- STUDENT ---

# Student Dash
@app.route('/student_dashboard')
@login_required(role='student')
def student_dashboard():
    return render_template('student_dashboard.html')

# Book Slot
@app.route('/student/book_slots', methods=['GET', 'POST'])
@login_required(role='student')
def book_slots():
    current_time = datetime.now()
    
    if request.method == 'POST':
        slot_id = request.form.get('slot_id')
        slot = db.get_or_404(ExaminationSlot, slot_id)
        exam = slot.examination
        
        # Verify Window
        if not (exam.booking_start <= current_time <= exam.booking_end):
            flash("Booking closed.")
            return redirect(url_for('book_slots'))
            
        # Verify Seats
        if slot.available_seats <= 0:
            flash("Slot full.")
            return redirect(url_for('book_slots'))
            
        # Verify Duplicate
        already_booked = Booking.query.join(ExaminationSlot).filter(
            Booking.student_id == session['user_id'],
            ExaminationSlot.examination_id == exam.id
        ).first()
        
        if already_booked:
            flash("Already booked.")
            return redirect(url_for('book_slots'))
            
        # Update Capacity
        slot.available_seats -= 1
        if slot.available_seats == 0:
            slot.status = 'Full'
            
        # Save Booking
        new_booking = Booking(student_id=session['user_id'], slot_id=slot.id)
        db.session.add(new_booking)
        db.session.commit()
        
        flash("Booking successful!")
        return redirect(url_for('student_dashboard'))
        
    open_slots = ExaminationSlot.query.filter(ExaminationSlot.available_seats > 0).all()
    return render_template('book_slots.html', slots=open_slots, current_time=current_time)

# View Results
@app.route('/student/results')
@login_required(role='student')
def results():
    evaluated_bookings = Booking.query.filter_by(student_id=session['user_id'], status='Evaluated').all()
    return render_template('results.html', results=evaluated_bookings)

# View Bookings
@app.route('/student/my_bookings')
@login_required(role='student')
def my_bookings():
    bookings = Booking.query.filter_by(student_id=session['user_id']).all()
    return render_template('my_bookings.html', bookings=bookings)

# --- EXAMINER ---

# Examiner Dash
@app.route('/examiner_dashboard')
@login_required(role='examiner')
def examiner_dashboard():
    return render_template('examiner_dashboard.html')

# Setup Slots
@app.route('/examiner/manage_slots', methods=['GET', 'POST'])
@login_required(role='examiner')
def manage_slots():
    if request.method == 'POST':
        exam_id = request.form['exam_id']
        max_capacity = int(request.form['max_capacity'])
        
        # Parse Dates
        fmt = '%Y-%m-%dT%H:%M'
        try:
            start_time = datetime.strptime(request.form['start_time'], fmt)
            end_time = datetime.strptime(request.form['end_time'], fmt)
        except ValueError:
            flash("Date error.")
            return redirect(url_for('manage_slots'))
            
        exam = db.session.get(Examination, exam_id)
        current_time = datetime.now()
        
        # Verify Window
        if not (exam.slot_creation_start <= current_time <= exam.slot_creation_end):
            flash("Creation closed.")
            return redirect(url_for('manage_slots'))
            
        # Verify Order
        if start_time >= end_time:
            flash("Time error.")
            return redirect(url_for('manage_slots'))
            
        # Block Past
        if start_time < current_time:
            flash("Past date error.")
            return redirect(url_for('manage_slots'))
            
        # Block Overlap
        if start_time < exam.booking_end:
            flash("Overlap error.")
            return redirect(url_for('manage_slots'))
            
        # Save Slot
        new_slot = ExaminationSlot(
            examination_id=exam.id,
            examiner_id=session['user_id'],
            start_time=start_time,
            end_time=end_time,
            max_capacity=max_capacity,
            available_seats=max_capacity 
        )
        db.session.add(new_slot)
        db.session.commit()
        
        flash("Slot created.")
        return redirect(url_for('manage_slots'))
        
    exams = Examination.query.all()
    my_slots = ExaminationSlot.query.filter_by(examiner_id=session['user_id']).all()
    return render_template('manage_slots.html', exams=exams, my_slots=my_slots)

# View Students
@app.route('/examiner/booked_students')
@login_required(role='examiner')
def booked_students():
    # Fetch Slots
    my_slots = ExaminationSlot.query.filter_by(examiner_id=session['user_id']).all()
    slot_ids = [slot.id for slot in my_slots]
    
    # Fetch Bookings
    bookings = Booking.query.filter(Booking.slot_id.in_(slot_ids)).all()
    return render_template('booked_students.html', bookings=bookings)

# Evaluate
@app.route('/examiner/evaluate/<int:booking_id>', methods=['GET', 'POST'])
@login_required(role='examiner')
def evaluate(booking_id):
    booking = db.get_or_404(Booking, booking_id)
    
    # Security Check
    if booking.slot.examiner_id != session['user_id']:
        flash("Access denied.")
        return redirect(url_for('booked_students'))
        
    if request.method == 'POST':
        marks = float(request.form['marks_obtained'])
        max_marks = booking.slot.examination.max_marks
        
        # Verify Limits
        if marks < 0 or marks > max_marks:
            flash("Invalid marks.")
            return redirect(url_for('evaluate', booking_id=booking.id))
            
        # Save Eval
        booking.marks_obtained = marks
        booking.feedback = request.form['feedback'].strip()
        booking.status = 'Evaluated'
        db.session.commit()
        
        flash("Evaluation saved.")
        return redirect(url_for('booked_students'))
        
    return render_template('evaluate.html', booking=booking)

# Run
if __name__ == '__main__':
    app.run(debug=True)