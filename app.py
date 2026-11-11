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

# --- DATABASE MODELS ---

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
    examination_id = db.Column(db.Integer, db.ForeignKey('examination.id'), nullable=False) # ADDED THIS
    examiner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    max_capacity = db.Column(db.Integer, nullable=False)
    available_seats = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default='Available')
    
    # Establish relationship to Examination to easily access exam details
    examination = db.relationship('Examination', backref='slots', lazy=True)
    bookings = db.relationship('Booking', backref='slot', lazy=True)
# Booking model
class Booking(db.Model):
    __tablename__ = 'booking'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    slot_id = db.Column(db.Integer, db.ForeignKey('examination_slot.id'), nullable=False)
    booking_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='Booked') # Status state
    
    # NEW COLUMNS FOR EVALUATION
    marks_obtained = db.Column(db.Float, nullable=True) 
    feedback = db.Column(db.Text, nullable=True)
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

# --- CORE ROUTES ---

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

# --- ADMIN ROUTES ---

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

@app.route('/admin/manage_courses', methods=['GET', 'POST'])
@login_required(role='admin')
def manage_courses():
    if request.method == 'POST':
        course_code = request.form['course_code'].strip()
        name = request.form['name'].strip()
        description = request.form['description'].strip()
        
        # Backend validation: check if fields are empty
        if not course_code or not name:
            flash("Course Code and Name are strictly required.")
            return redirect(url_for('manage_courses'))
            
        # Backend validation: prevent duplicate course codes
        if Course.query.filter_by(course_code=course_code).first():
            flash("Error: A course with this code already exists.")
            return redirect(url_for('manage_courses'))
            
        # Add to database
        new_course = Course(course_code=course_code, name=name, description=description)
        db.session.add(new_course)
        db.session.commit()
        
        flash(f"Course '{course_code} - {name}' created successfully.")
        return redirect(url_for('manage_courses'))
        
    # GET request: fetch all courses to display in the table
    courses = Course.query.all()
    return render_template('manage_courses.html', courses=courses)
@app.route('/admin/manage_exams', methods=['GET', 'POST'])
@login_required(role='admin')
def manage_exams():
    if request.method == 'POST':
        course_id = request.form['course_id']
        name = request.form['name'].strip()
        exam_type = request.form['exam_type']
        duration = request.form['duration']
        max_marks = request.form['max_marks']
        
        # Parse datetime strings from the HTML5 datetime-local inputs
        fmt = '%Y-%m-%dT%H:%M'
        try:
            slot_start = datetime.strptime(request.form['slot_creation_start'], fmt)
            slot_end = datetime.strptime(request.form['slot_creation_end'], fmt)
            booking_start = datetime.strptime(request.form['booking_start'], fmt)
            booking_end = datetime.strptime(request.form['booking_end'], fmt)
        except ValueError:
            flash("Error parsing dates. Please try again.")
            return redirect(url_for('manage_exams'))
            
        new_exam = Examination(
            course_id=course_id, name=name, exam_type=exam_type,
            duration=duration, max_marks=max_marks,
            slot_creation_start=slot_start, slot_creation_end=slot_end,
            booking_start=booking_start, booking_end=booking_end
        )
        db.session.add(new_exam)
        db.session.commit()
        
        flash(f"Examination '{name}' created successfully.")
        return redirect(url_for('manage_exams'))
        
    # GET request: fetch courses for the dropdown and exams for the table
    courses = Course.query.all()
    exams = Examination.query.all()
    return render_template('manage_exams.html', courses=courses, exams=exams)

@app.route('/admin/approve_examiners')
@login_required(role='admin')
def approve_examiners():
    # Fetch all users who registered as examiners but are still pending
    pending_examiners = User.query.filter_by(role='examiner', status='pending').all()
    return render_template('approve_examiners.html', pending_examiners=pending_examiners)

@app.route('/admin/approve_examiner/<int:user_id>', methods=['POST'])
@login_required(role='admin')
def approve_examiner_action(user_id):
    # Find the user by ID or return a 404 error if they don't exist
    examiner = User.query.get_or_404(user_id)
    
    # Ensure we are only approving pending examiners
    if examiner.role == 'examiner' and examiner.status == 'pending':
        examiner.status = 'approved'
        db.session.commit()
        flash(f"Examiner '{examiner.username}' has been successfully approved.")
        
    return redirect(url_for('approve_examiners'))

# --- STUDENT ROUTES ---

@app.route('/student_dashboard')
@login_required(role='student')
def student_dashboard():
    # We will query actual available exams and bookings here in the next phase
    return render_template('student_dashboard.html')
@app.route('/student/book_slots', methods=['GET', 'POST'])
@login_required(role='student')
def book_slots():
    current_time = datetime.now()
    
    if request.method == 'POST':
        slot_id = request.form.get('slot_id')
        slot = ExaminationSlot.query.get_or_404(slot_id)
        exam = slot.examination
        
        # Validation 1: Is the booking window currently open?
        if not (exam.booking_start <= current_time <= exam.booking_end):
            flash("Error: The booking window for this examination is currently closed.")
            return redirect(url_for('book_slots'))
            
        # Validation 2: Are there still seats left?
        if slot.available_seats <= 0:
            flash("Error: This slot is fully booked.")
            return redirect(url_for('book_slots'))
            
        # Validation 3: Has the student already booked a slot for this specific exam?
        already_booked = Booking.query.join(ExaminationSlot).filter(
            Booking.student_id == session['user_id'],
            ExaminationSlot.examination_id == exam.id
        ).first()
        
        if already_booked:
            flash("Error: You have already booked a slot for this examination.")
            return redirect(url_for('book_slots'))
            
        # Execute the booking
        slot.available_seats -= 1
        if slot.available_seats == 0:
            slot.status = 'Full'
            
        new_booking = Booking(student_id=session['user_id'], slot_id=slot.id)
        db.session.add(new_booking)
        db.session.commit()
        
        flash(f"Successfully booked your slot for {exam.name}!")
        return redirect(url_for('student_dashboard'))
        
    # GET request: fetch all slots that aren't full
    open_slots = ExaminationSlot.query.filter(ExaminationSlot.available_seats > 0).all()
    return render_template('book_slots.html', slots=open_slots, current_time=current_time)
@app.route('/student/results')
@login_required(role='student')
def results():
    # Fetch only bookings that have been evaluated by an examiner
    evaluated_bookings = Booking.query.filter_by(student_id=session['user_id'], status='Evaluated').all()
    return render_template('results.html', results=evaluated_bookings)
@app.route('/student/my_bookings')
@login_required(role='student')
def my_bookings():
    # Fetch all bookings for the currently logged-in student
    bookings = Booking.query.filter_by(student_id=session['user_id']).all()
    return render_template('my_bookings.html', bookings=bookings)

# --- EXAMINER ROUTES ---

@app.route('/examiner_dashboard')
@login_required(role='examiner')
def examiner_dashboard():
    # We will query assigned exams and slots here later
    return render_template('examiner_dashboard.html')
@app.route('/examiner/manage_slots', methods=['GET', 'POST'])
@login_required(role='examiner')
def manage_slots():
    if request.method == 'POST':
        exam_id = request.form['exam_id']
        max_capacity = int(request.form['max_capacity'])
        
        # Parse slot times
        fmt = '%Y-%m-%dT%H:%M'
        try:
            start_time = datetime.strptime(request.form['start_time'], fmt)
            end_time = datetime.strptime(request.form['end_time'], fmt)
        except ValueError:
            flash("Error parsing dates.")
            return redirect(url_for('manage_slots'))
            
        exam = Examination.query.get(exam_id)
        current_time = datetime.now()
        
        # 1. Admin Window Validation: Check if the examiner is allowed to create slots right now
        if not (exam.slot_creation_start <= current_time <= exam.slot_creation_end):
            flash(f"Error: Slot creation for '{exam.name}' is currently closed. Allowed from {exam.slot_creation_start} to {exam.slot_creation_end}.")
            return redirect(url_for('manage_slots'))
            
        # 2. Chronological Validation: End time must be after start time
        if start_time >= end_time:
            flash("Error: End time must be after start time.")
            return redirect(url_for('manage_slots'))
            
        # 3. NEW: Prevent scheduling slots in the past
        if start_time < current_time:
            flash("Error: Examination slot cannot be scheduled in the past.")
            return redirect(url_for('manage_slots'))
            
        # 4. NEW: Ensure the slot happens AFTER the student booking window ends
        if start_time < exam.booking_end:
            flash(f"Error: Slot must be scheduled after the student booking window ends ({exam.booking_end}).")
            return redirect(url_for('manage_slots'))
            
        new_slot = ExaminationSlot(
            examination_id=exam.id,
            examiner_id=session['user_id'],
            start_time=start_time,
            end_time=end_time,
            max_capacity=max_capacity,
            available_seats=max_capacity # Seats initially equal max capacity
        )
        db.session.add(new_slot)
        db.session.commit()
        
        flash("Examination slot created successfully.")
        return redirect(url_for('manage_slots'))
        
    # GET request: fetch exams and the current examiner's slots
    exams = Examination.query.all()
    my_slots = ExaminationSlot.query.filter_by(examiner_id=session['user_id']).all()
    return render_template('manage_slots.html', exams=exams, my_slots=my_slots)
@app.route('/examiner/booked_students')
@login_required(role='examiner')
def booked_students():
    # Find all slots managed by this examiner
    my_slots = ExaminationSlot.query.filter_by(examiner_id=session['user_id']).all()
    slot_ids = [slot.id for slot in my_slots]
    
    # Fetch all bookings that belong to any of those slots
    bookings = Booking.query.filter(Booking.slot_id.in_(slot_ids)).all()
    return render_template('booked_students.html', bookings=bookings)
@app.route('/examiner/evaluate/<int:booking_id>', methods=['GET', 'POST'])
@login_required(role='examiner')
def evaluate(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    
    # Security Check: Ensure this booking belongs to a slot managed by THIS examiner
    if booking.slot.examiner_id != session['user_id']:
        flash("Unauthorized access: You do not manage this slot.")
        return redirect(url_for('booked_students'))
        
    if request.method == 'POST':
        marks = float(request.form['marks_obtained'])
        max_marks = booking.slot.examination.max_marks
        
        # Validation: Marks cannot exceed the max marks defined by the Admin
        if marks < 0 or marks > max_marks:
            flash(f"Error: Marks must be between 0 and {max_marks}.")
            return redirect(url_for('evaluate', booking_id=booking.id))
            
        booking.marks_obtained = marks
        booking.feedback = request.form['feedback'].strip()
        booking.status = 'Evaluated'
        db.session.commit()
        
        flash(f"Evaluation submitted for Student #{booking.student_id}.")
        return redirect(url_for('booked_students'))
        
    return render_template('evaluate.html', booking=booking)
# Run app
if __name__ == '__main__':
    app.run(debug=True)