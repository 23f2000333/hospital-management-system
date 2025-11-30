from flask import Flask, render_template, request, redirect, url_for, flash 
from flask_sqlalchemy import SQLAlchemy 
from flask_login import ( 
    LoginManager, 
    UserMixin,
    login_user,
    login_required,
    logout_user,
    current_user,
)
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date, timedelta, time
import os 
from sqlalchemy import or_  

app = Flask(__name__) 


app.config["SECRET_KEY"] = "change-this-secret-key"

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///hospital.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"

# MODELS#

class User(UserMixin, db.Model):
    """Common user table for admin, doctor, patient."""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)  
    is_active = db.Column(db.Boolean, default=True)

    patient = db.relationship("PatientProfile", backref="user", uselist=False)
    doctor = db.relationship("DoctorProfile", backref="user", uselist=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class PatientProfile(db.Model):
    """ information for patients"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    full_name = db.Column(db.String(120), nullable=False)
    age = db.Column(db.Integer)
    gender = db.Column(db.String(20))
    phone = db.Column(db.String(20))
    address = db.Column(db.Text)

    is_blacklisted = db.Column(db.Boolean, default=False)

    appointments = db.relationship("Appointment", backref="patient", lazy=True)


class Department(db.Model):
    """ department,specialization."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    description = db.Column(db.Text)

    doctors = db.relationship("DoctorProfile", backref="department", lazy=True)


class DoctorProfile(db.Model):
    """information for doctors"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    full_name = db.Column(db.String(120), nullable=False)
    specialization = db.Column(db.String(120), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey("department.id"))
    years_experience = db.Column(db.Integer)
    bio = db.Column(db.Text)

    is_active = db.Column(db.Boolean, default=True)
    is_blacklisted = db.Column(db.Boolean, default=False)

    appointments = db.relationship("Appointment", backref="doctor", lazy=True)
    slots = db.relationship("DoctorAvailability", backref="doctor", lazy=True)


class Appointment(db.Model):
    """Appointment between patient and doctor."""
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patient_profile.id"), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey("doctor_profile.id"), nullable=False)

    date = db.Column(db.Date, nullable=False)
    time = db.Column(db.Time, nullable=False)
    status = db.Column(db.String(20), default="booked")  

    reason = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    treatment = db.relationship("TreatmentRecord", backref="appointment", uselist=False)

    __table_args__ = (
        
        db.UniqueConstraint("doctor_id", "date", "time", name="uq_doctor_datetime"),
    )


class TreatmentRecord(db.Model):
    """Diagnosis and prescription for appointment."""
    id = db.Column(db.Integer, primary_key=True)
    appointment_id = db.Column(db.Integer, db.ForeignKey("appointment.id"), nullable=False)

    diagnosis = db.Column(db.Text)
    prescription = db.Column(db.Text)
    notes = db.Column(db.Text)


class DoctorAvailability(db.Model):
    """Available slots for a doctor."""
    id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey("doctor_profile.id"), nullable=False)

    date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    is_booked = db.Column(db.Boolean, default=False)

    __table_args__ = (
        db.UniqueConstraint("doctor_id", "date", "start_time", name="uq_doctor_slot"),
    )

# LOGIN  #

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# DB INIT  #

def init_db():
    """Creates tables and a default admin if not present."""
    db.create_all()

    
    admin = User.query.filter_by(role="admin").first()
    if not admin:
        admin = User(
            username="admin",
            email="admin@hospital.com",
            role="admin",
            is_active=True,
        )
        admin.set_password("admin123")   
        db.session.add(admin)

    
    if Department.query.count() == 0:
        d1 = Department(name="Cardiology", description="Heart related problems")
        d2 = Department(name="Oncology", description="Cancer treatment")
        d3 = Department(name="Neurology", description="Brain and nerves")
        db.session.add_all([d1, d2, d3])

    db.session.commit()

with app.app_context():
    init_db()

# ROUTES #

@app.route("/")
def home():
    
    return redirect(url_for("login"))

@app.route("/register", methods=["GET", "POST"])
def register():
    """Patient self-registration."""
    if request.method == "POST":
        username = request.form.get("username").strip()
        email = request.form.get("email").strip().lower()
        password = request.form.get("password")
        full_name = request.form.get("full_name").strip()
        phone = request.form.get("phone")
        age = request.form.get("age")
        gender = request.form.get("gender")
        address = request.form.get("address")

        
        if not username or not email or not password or not full_name:
            flash("Please fill all required fields.", "danger")
            return render_template("register.html")

        # check if already exists
        existing = User.query.filter(
            (User.username == username) | (User.email == email)
        ).first()
        if existing:
            flash("Username or email already taken.", "danger")
            return render_template("register.html")

        user = User(username=username, email=email, role="patient")
        user.set_password(password)
        db.session.add(user)
        db.session.flush()  

        patient = PatientProfile(
            user_id=user.id,
            full_name=full_name,
            phone=phone,
            age=int(age) if age else None,
            gender=gender,
            address=address,
        )
        db.session.add(patient)
        db.session.commit()

        flash("Registration successful. Please login.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Login for all roles."""
    if request.method == "POST":
        username_or_email = request.form.get("username")
        password = request.form.get("password")

        user = User.query.filter(
            (User.username == username_or_email) | (User.email == username_or_email)
        ).first()

        if not user or not user.check_password(password):
            flash("Invalid username/email or password.", "danger")
            return render_template("login.html")

        if not user.is_active:
            flash("Your account is deactivated. Contact admin.", "warning")
            return render_template("login.html")

        login_user(user)
        flash("Logged in successfully.", "success")

        
        if user.role == "admin":
            return redirect(url_for("admin_dashboard"))
        elif user.role == "doctor":
            return redirect(url_for("doctor_dashboard"))
        else:
            return redirect(url_for("patient_dashboard"))

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))

# DASHBOARDS  #

@app.route("/admin")
@login_required
def admin_dashboard():
    """Admin overview page."""
    if current_user.role != "admin":
        return redirect(url_for("login"))

    total_doctors = DoctorProfile.query.count()
    total_patients = PatientProfile.query.count()
    total_appointments = Appointment.query.count()

    return render_template(
        "admin_dashboard.html",
        total_doctors=total_doctors,
        total_patients=total_patients,
        total_appointments=total_appointments,
    )

@app.route("/admin/doctors", methods=["GET"])
@login_required
def admin_doctors():
    """Admin: view and search doctors."""
    if current_user.role != "admin":
        return redirect(url_for("login"))

    q = request.args.get("q", "").strip()

    query = DoctorProfile.query
    if q:
        # search by doctor name or specialization
        query = query.filter(
            or_(
                DoctorProfile.full_name.ilike(f"%{q}%"),
                DoctorProfile.specialization.ilike(f"%{q}%"),
            )
        )

    doctors = query.all()
    departments = Department.query.all()

    return render_template(
        "admin_doctors.html",
        doctors=doctors,
        departments=departments,
        search_query=q,
    )


@app.route("/admin/doctors/add", methods=["GET", "POST"])
@login_required
def add_doctor():
    """Admin: add a new doctor (user + profile)."""
    if current_user.role != "admin":
        return redirect(url_for("login"))

    if request.method == "POST":
        username = request.form.get("username").strip()
        email = request.form.get("email").strip().lower()
        password = request.form.get("password")
        full_name = request.form.get("full_name").strip()
        specialization = request.form.get("specialization").strip()
        department_id = request.form.get("department_id")
        years_experience = request.form.get("years_experience") or None
        bio = request.form.get("bio")

        
        if not username or not email or not password or not full_name or not specialization:
            flash("Please fill all required fields.", "danger")
            return redirect(url_for("add_doctor"))

        # check if username/email already used
        existing = User.query.filter(
            (User.username == username) | (User.email == email)
        ).first()
        if existing:
            flash("Username or email already exists.", "danger")
            return redirect(url_for("add_doctor"))

        # create user account
        user = User(username=username, email=email, role="doctor")
        user.set_password(password)
        db.session.add(user)
        db.session.flush()  # get user.id

        # create doctor profile
        doctor = DoctorProfile(
            user_id=user.id,
            full_name=full_name,
            specialization=specialization,
            department_id=int(department_id) if department_id else None,
            years_experience=int(years_experience) if years_experience else None,
            bio=bio,
            is_active=True,
            is_blacklisted=False,
        )
        db.session.add(doctor)
        db.session.commit()

        flash("Doctor added successfully.", "success")
        return redirect(url_for("admin_doctors"))

    departments = Department.query.all()
    return render_template("admin_doctor_form.html", departments=departments, doctor=None)


@app.route("/admin/doctors/edit/<int:doctor_id>", methods=["GET", "POST"])
@login_required
def edit_doctor(doctor_id):
    """Admin: edit an existing doctor profile."""
    if current_user.role != "admin":
        return redirect(url_for("login"))

    doctor = DoctorProfile.query.get_or_404(doctor_id)
    user = doctor.user

    if request.method == "POST":
        user.username = request.form.get("username").strip()
        user.email = request.form.get("email").strip().lower()

        full_name = request.form.get("full_name").strip()
        specialization = request.form.get("specialization").strip()
        department_id = request.form.get("department_id")
        years_experience = request.form.get("years_experience") or None
        bio = request.form.get("bio")
        is_active = bool(request.form.get("is_active"))
        is_blacklisted = bool(request.form.get("is_blacklisted"))

        if not user.username or not user.email or not full_name or not specialization:
            flash("Please fill all required fields.", "danger")
            return redirect(url_for("edit_doctor", doctor_id=doctor.id))

        doctor.full_name = full_name
        doctor.specialization = specialization
        doctor.department_id = int(department_id) if department_id else None
        doctor.years_experience = int(years_experience) if years_experience else None
        doctor.bio = bio
        doctor.is_active = is_active
        doctor.is_blacklisted = is_blacklisted

        # allow admin to reset password
        new_password = request.form.get("password")  
        if new_password:
            user.set_password(new_password)

        db.session.commit()
        flash("Doctor updated successfully.", "success")
        return redirect(url_for("admin_doctors"))

    departments = Department.query.all()
    return render_template(
        "admin_doctor_form.html",
        departments=departments,
        doctor=doctor,
    )


@app.route("/admin/doctors/delete/<int:doctor_id>", methods=["POST"])
@login_required
def delete_doctor(doctor_id):
    """Admin: delete a doctor (and user)."""
    if current_user.role != "admin":
        return redirect(url_for("login"))

    doctor = DoctorProfile.query.get_or_404(doctor_id)
    user = doctor.user

    
    db.session.delete(doctor)
    db.session.delete(user)
    db.session.commit()

    flash("Doctor deleted successfully.", "info")
    return redirect(url_for("admin_doctors"))

@app.route("/admin/appointments")
@login_required
def admin_appointments():
    """Admin: see all appointments."""
    if current_user.role != "admin":
        return redirect(url_for("login"))

    status_filter = request.args.get("status", "").strip()  

    query = Appointment.query.order_by(Appointment.date.desc(), Appointment.time.desc())
    if status_filter:
        query = query.filter(Appointment.status == status_filter)

    appointments = query.all()
    return render_template(
        "admin_appointments.html",
        appointments=appointments,
        status_filter=status_filter,
    )
@app.route("/admin/patients")
@login_required
def admin_patients():
    """Admin: view/search patients."""
    if current_user.role != "admin":
        return redirect(url_for("login"))

    q = request.args.get("q", "").strip()

    query = PatientProfile.query
    if q:
        query = query.filter(
            or_(
                PatientProfile.full_name.ilike(f"%{q}%"),
                PatientProfile.phone.ilike(f"%{q}%"),
            )
        )

    patients = query.all()
    return render_template("admin_patients.html", patients=patients, search_query=q)


@app.route("/admin/patients/edit/<int:patient_id>", methods=["GET", "POST"])
@login_required
def edit_patient(patient_id):
    """Admin: edit patient info and blacklist."""
    if current_user.role != "admin":
        return redirect(url_for("login"))

    patient = PatientProfile.query.get_or_404(patient_id)
    user = patient.user

    if request.method == "POST":
        patient.full_name = request.form.get("full_name")
        patient.age = request.form.get("age") or None
        patient.gender = request.form.get("gender")
        patient.phone = request.form.get("phone")
        patient.address = request.form.get("address")
        patient.is_blacklisted = bool(request.form.get("is_blacklisted"))

        user.email = request.form.get("email")
        user.username = request.form.get("username")

        db.session.commit()
        flash("Patient updated.", "success")
        return redirect(url_for("admin_patients"))

    return render_template("admin_patient_form.html", patient=patient)

@app.route("/doctor")
@login_required
def doctor_dashboard():
    """Doctor dashboard showing upcoming and past appointments."""
    if current_user.role != "doctor":
        return redirect(url_for("login"))

    doctor = DoctorProfile.query.filter_by(user_id=current_user.id).first()
    today = date.today()

    upcoming = []
    past = []

    if doctor:
        # booked appointments today onwards
        upcoming = Appointment.query.filter(
            Appointment.doctor_id == doctor.id,
            Appointment.date >= today,
            Appointment.status == "booked",
        ).order_by(Appointment.date, Appointment.time).all()

        # completed/cancelled appointment before today
        past = Appointment.query.filter(
            Appointment.doctor_id == doctor.id,
            or_(Appointment.date < today, Appointment.status != "booked"),
        ).order_by(Appointment.date.desc(), Appointment.time.desc()).all()

    return render_template(
        "doctor_dashboard.html",
        doctor=doctor,
        upcoming_appointments=upcoming,
        past_appointments=past,
    )

@app.route("/doctor/appointments/status/<int:appointment_id>", methods=["POST"])
@login_required
def update_appointment_status(appointment_id):
    """Doctor can change status of their appointment."""
    if current_user.role != "doctor":
        return redirect(url_for("login"))

    doctor = DoctorProfile.query.filter_by(user_id=current_user.id).first()
    appt = Appointment.query.get_or_404(appointment_id)

    if not doctor or appt.doctor_id != doctor.id:
        return redirect(url_for("doctor_dashboard"))

    new_status = request.form.get("status")  # booked / completed / cancelled
    if new_status not in ["booked", "completed", "cancelled"]:
        flash("Invalid status.", "danger")
        return redirect(url_for("doctor_dashboard"))

    appt.status = new_status
    db.session.commit()
    flash("Appointment status updated.", "success")
    return redirect(url_for("doctor_dashboard"))


@app.route("/doctor/appointments/treatment/<int:appointment_id>", methods=["GET", "POST"])
@login_required
def edit_treatment(appointment_id):
    """Doctor can add/update treatment details."""
    if current_user.role != "doctor":
        return redirect(url_for("login"))

    doctor = DoctorProfile.query.filter_by(user_id=current_user.id).first()
    appt = Appointment.query.get_or_404(appointment_id)

    if not doctor or appt.doctor_id != doctor.id:
        return redirect(url_for("doctor_dashboard"))

    treatment = appt.treatment  

    if request.method == "POST":
        diagnosis = request.form.get("diagnosis")
        prescription = request.form.get("prescription")
        notes = request.form.get("notes")

        if treatment is None:
            treatment = TreatmentRecord(
                appointment_id=appt.id,
                diagnosis=diagnosis,
                prescription=prescription,
                notes=notes,
            )
            db.session.add(treatment)
        else:
            treatment.diagnosis = diagnosis
            treatment.prescription = prescription
            treatment.notes = notes

        
        appt.status = "completed"

        db.session.commit()
        flash("Treatment details saved.", "success")
        return redirect(url_for("doctor_dashboard"))

    return render_template("doctor_treatment.html", appointment=appt, treatment=treatment)

@app.route("/doctor/availability", methods=["GET", "POST"])
@login_required
def doctor_availability():
    """Doctor can add and view availability slots (next 7 days only)."""
    if current_user.role != "doctor":
        return redirect(url_for("login"))

    doctor = DoctorProfile.query.filter_by(user_id=current_user.id).first()
    if not doctor:
        flash("Doctor profile not found.", "danger")
        return redirect(url_for("doctor_dashboard"))

    today = date.today()
    week_later = today + timedelta(days=7)

    if request.method == "POST":
        date_str = request.form.get("date")
        start_str = request.form.get("start_time")
        end_str = request.form.get("end_time")

        if not date_str or not start_str or not end_str:
            flash("Please fill all fields.", "danger")
            return redirect(url_for("doctor_availability"))

        try:
            slot_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            start_time = datetime.strptime(start_str, "%H:%M").time()
            end_time = datetime.strptime(end_str, "%H:%M").time()
        except ValueError:
            flash("Invalid date or time format.", "danger")
            return redirect(url_for("doctor_availability"))

        # only till next 7 days 
        if slot_date < today or slot_date > week_later:
            flash("Please select a date within the next 7 days.", "danger")
            return redirect(url_for("doctor_availability"))

        if end_time <= start_time:
            flash("End time must be after start time.", "danger")
            return redirect(url_for("doctor_availability"))

        slot = DoctorAvailability(
            doctor_id=doctor.id,
            date=slot_date,
            start_time=start_time,
            end_time=end_time,
        )
        try:
            db.session.add(slot)
            db.session.commit()
            flash("Availability slot added.", "success")
        except Exception:
            db.session.rollback()
            flash("Slot already exists or error occurred.", "danger")

        return redirect(url_for("doctor_availability"))


    slots = DoctorAvailability.query.filter(
        DoctorAvailability.doctor_id == doctor.id,
        DoctorAvailability.date >= today,
        DoctorAvailability.date <= week_later,
    ).order_by(DoctorAvailability.date, DoctorAvailability.start_time).all()

    return render_template("doctor_availability.html", doctor=doctor, slots=slots)


@app.route("/doctor/availability/delete/<int:slot_id>", methods=["POST"])
@login_required
def delete_availability(slot_id):
    """Doctor can delete a free slot."""
    if current_user.role != "doctor":
        return redirect(url_for("login"))

    doctor = DoctorProfile.query.filter_by(user_id=current_user.id).first()
    slot = DoctorAvailability.query.get_or_404(slot_id)

    
    if not doctor or slot.doctor_id != doctor.id:
        return redirect(url_for("doctor_availability"))

    if slot.is_booked:
        flash("Cannot delete a booked slot.", "warning")
    else:
        db.session.delete(slot)
        db.session.commit()
        flash("Slot deleted.", "info")

    return redirect(url_for("doctor_availability"))

@app.route("/doctor/patient/<int:patient_id>/history")
@login_required
def patient_history(patient_id):
    """Doctor: view full history of one patient (with this doctor)."""
    if current_user.role != "doctor":
        return redirect(url_for("login"))

    doctor = DoctorProfile.query.filter_by(user_id=current_user.id).first()
    if not doctor:
        flash("Doctor profile not found.", "danger")
        return redirect(url_for("doctor_dashboard"))

    patient = PatientProfile.query.get_or_404(patient_id)

    
    appointments = Appointment.query.filter_by(
        doctor_id=doctor.id,
        patient_id=patient.id,
    ).order_by(Appointment.date.desc(), Appointment.time.desc()).all()

    return render_template(
        "doctor_patient_history.html",
        patient=patient,
        appointments=appointments,
    )

@app.route("/patient")
@login_required
def patient_dashboard():
    if current_user.role != "patient":
        return redirect(url_for("login"))

    patient = PatientProfile.query.filter_by(user_id=current_user.id).first()
    today = date.today()

    
    upcoming = []
    past = []

    if patient:
        upcoming = Appointment.query.filter(
            Appointment.patient_id == patient.id,
            Appointment.date >= today,
            Appointment.status == "booked",
        ).order_by(Appointment.date, Appointment.time).all()

        
        past = Appointment.query.filter(
            Appointment.patient_id == patient.id,
            or_(Appointment.date < today, Appointment.status != "booked"),
        ).order_by(Appointment.date.desc(), Appointment.time.desc()).all()

    departments = Department.query.all()

    #  doctor search 
    q = request.args.get("q", "").strip()
    doctors_query = DoctorProfile.query.filter(
        DoctorProfile.is_active == True,
        DoctorProfile.is_blacklisted == False,
    )
    if q:
        doctors_query = doctors_query.filter(
            or_(
                DoctorProfile.full_name.ilike(f"%{q}%"),
                DoctorProfile.specialization.ilike(f"%{q}%"),
            )
        )
    doctors = doctors_query.all()

    return render_template(
        "patient_dashboard.html",
        patient=patient,
        upcoming_appointments=upcoming,
        past_appointments=past,
        departments=departments,
        doctors=doctors,
        search_query=q,
    )

@app.route("/patient/doctor/<int:doctor_id>/availability")
@login_required
def view_doctor_availability(doctor_id):
    """Patient can see free slots for one doctor."""
    if current_user.role != "patient":
        return redirect(url_for("login"))

    doctor = DoctorProfile.query.get_or_404(doctor_id)

    # do not show availability for blacklisted or inactive doctors
    if doctor.is_blacklisted or not doctor.is_active:
        flash("This doctor is not available for booking.", "warning")
        return redirect(url_for("patient_dashboard"))

    today = date.today()
    week_later = today + timedelta(days=7)

    slots = DoctorAvailability.query.filter(
        DoctorAvailability.doctor_id == doctor.id,
        DoctorAvailability.date >= today,
        DoctorAvailability.date <= week_later,
        DoctorAvailability.is_booked == False,
    ).order_by(DoctorAvailability.date, DoctorAvailability.start_time).all()

    return render_template(
        "patient_doctor_availability.html",
        doctor=doctor,
        slots=slots,
    )

@app.route("/patient/book/<int:slot_id>", methods=["POST"])
@login_required
def book_appointment(slot_id):
    """Create appointment for selected slot."""
    if current_user.role != "patient":
        return redirect(url_for("login"))

    patient = PatientProfile.query.filter_by(user_id=current_user.id).first()
    if not patient:
        flash("Patient profile not found.", "danger")
        return redirect(url_for("patient_dashboard"))

    # blacklisted patients cannot book
    if patient.is_blacklisted:
        flash("You are not allowed to book new appointments. Please contact hospital staff.", "danger")
        return redirect(url_for("patient_dashboard"))

    slot = DoctorAvailability.query.get_or_404(slot_id)
    doctor = DoctorProfile.query.get(slot.doctor_id)

    # do not allow bookings for blacklisted/inactive doctors
    if doctor.is_blacklisted or not doctor.is_active:
        flash("This doctor is not available for booking.", "warning")
        return redirect(url_for("patient_dashboard"))

    if slot.is_booked:
        flash("This slot is already booked.", "warning")
        return redirect(url_for("view_doctor_availability", doctor_id=slot.doctor_id))

    appt = Appointment(
        patient_id=patient.id,
        doctor_id=slot.doctor_id,
        date=slot.date,
        time=slot.start_time,
        status="booked",
    )
    slot.is_booked = True
    db.session.add(appt)
    db.session.commit()

    flash("Appointment booked successfully.", "success")
    return redirect(url_for("patient_dashboard"))

@app.route("/patient/appointments/cancel/<int:appointment_id>", methods=["POST"])
@login_required
def cancel_appointment(appointment_id):
    """Patient can cancel a booked appointment."""
    if current_user.role != "patient":
        return redirect(url_for("login"))

    patient = PatientProfile.query.filter_by(user_id=current_user.id).first()
    appt = Appointment.query.get_or_404(appointment_id)

    if not patient or appt.patient_id != patient.id:
        return redirect(url_for("patient_dashboard"))

    if appt.status == "cancelled":
        flash("Appointment already cancelled.", "info")
        return redirect(url_for("patient_dashboard"))

    appt.status = "cancelled"

    # free the matching slot (same doctor,date,time)
    slot = DoctorAvailability.query.filter_by(
        doctor_id=appt.doctor_id,
        date=appt.date,
        start_time=appt.time,
    ).first()
    if slot:
        slot.is_booked = False

    db.session.commit()
    flash("Appointment cancelled.", "info")
    return redirect(url_for("patient_dashboard"))

@app.route("/patient/profile", methods=["GET", "POST"])
@login_required
def patient_profile():
    """Patient can edit their own profile."""
    if current_user.role != "patient":
        return redirect(url_for("login"))

    patient = PatientProfile.query.filter_by(user_id=current_user.id).first()
    user = current_user

    if request.method == "POST":
        patient.full_name = request.form.get("full_name")
        patient.age = request.form.get("age") or None
        patient.gender = request.form.get("gender")
        patient.phone = request.form.get("phone")
        patient.address = request.form.get("address")

        user.email = request.form.get("email")

        db.session.commit()
        flash("Profile updated.", "success")
        return redirect(url_for("patient_dashboard"))

    return render_template("patient_profile.html", patient=patient, user=user)


if __name__ == "__main__":
    app.run(debug=True)
