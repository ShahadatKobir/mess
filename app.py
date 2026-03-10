import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'niloy_mess_secret_2026'

# --- PostgreSQL / SQLite Configuration ---
# Render-এ DATABASE_URL এনভায়রনমেন্ট ভেরিয়েবল থেকে লিঙ্ক নেবে
uri = os.getenv("DATABASE_URL")
if uri and uri.startswith("postgres://"):
    # SQLAlchemy 1.4+ এর জন্য postgres:// কে postgresql:// করতে হয়
    uri = uri.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = uri or 'sqlite:///master_niloy_mess.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- Database Models ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(10), default='border') # admin or border
    deposit = db.Column(db.Float, default=0.0)

class BazarSchedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(20))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    user = db.relationship('User', backref='schedules')

class Meal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    date = db.Column(db.String(20))
    morning = db.Column(db.Float, default=0.0)
    lunch = db.Column(db.Float, default=0.0)
    dinner = db.Column(db.Float, default=0.0)
    is_off = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(20), default='approved')

class Bazar(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    date = db.Column(db.String(20))
    amount = db.Column(db.Float, default=0.0)
    details = db.Column(db.Text)
    status = db.Column(db.String(20), default='pending')

class ExtraCost(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(100))
    amount = db.Column(db.Float)

# --- Calculation Logic ---
def get_all_stats():
    total_bazar = db.session.query(db.func.sum(Bazar.amount)).filter_by(status='approved').scalar() or 0
    total_meals = db.session.query(db.func.sum(Meal.morning + Meal.lunch + Meal.dinner)).filter_by(is_off=False, status='approved').scalar() or 0
    meal_rate = total_bazar / total_meals if total_meals > 0 else 0
    total_extra = db.session.query(db.func.sum(ExtraCost.amount)).scalar() or 0
    num_users = User.query.filter_by(role='border').count()
    extra_per_head = total_extra / num_users if num_users > 0 else 0
    return total_bazar, total_meals, meal_rate, total_extra, extra_per_head

# --- App Logic ---
@app.context_processor
def inject_now():
    return {'now': datetime.now()}

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('admin' if session['role'] == 'admin' else 'member_dashboard'))
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')
    user = User.query.filter_by(username=username).first()
    if user and check_password_hash(user.password, password):
        session.update({'user_id': user.id, 'role': user.role, 'username': user.username})
        return redirect(url_for('index'))
    flash('ইউজারনেম বা পাসওয়ার্ড ভুল!', 'danger')
    return redirect(url_for('index'))

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if session.get('role') != 'admin': return redirect(url_for('index'))
    b_cost, t_meals, m_rate, t_extra, e_head = get_all_stats()
    users = User.query.filter_by(role='border').all()
    pending_bazars = Bazar.query.filter_by(status='pending').all()
    
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add_member':
            pw = generate_password_hash(request.form['password'])
            db.session.add(User(username=request.form['username'], password=pw))
        elif action == 'add_extra':
            db.session.add(ExtraCost(description=request.form['desc'], amount=float(request.form['amount'])))
        elif action == 'set_schedule':
            db.session.add(BazarSchedule(date=request.form['date'], user_id=request.form['user_id']))
        db.session.commit()
        return redirect(url_for('admin'))
    return render_template('admin.html', **locals())

@app.route('/member/dashboard')
def member_dashboard():
    if 'user_id' not in session: return redirect(url_for('index'))
    user = User.query.get(session['user_id'])
    b_cost, t_meals, m_rate, t_extra, e_head = get_all_stats()
    my_meals = db.session.query(db.func.sum(Meal.morning + Meal.lunch + Meal.dinner)).filter_by(user_id=user.id, is_off=False, status='approved').scalar() or 0
    personal_cost = (my_meals * m_rate) + e_head
    balance = user.deposit - personal_cost
    days_left = balance / (m_rate * 1.0) if balance > 0 and m_rate > 0 else 0
    return render_template('member.html', **locals())

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# --- Server Start & Table Creation ---
if __name__ == '__main__':
    with app.app_context():
        # এটি ডাটাবেজে সব টেবিল তৈরি করবে
        db.create_all()
        # চেক করবে অ্যাডমিন ইউজার আছে কি না, না থাকলে তৈরি করবে
        admin_check = User.query.filter_by(username='admin').first()
        if not admin_check:
            hashed_pw = generate_password_hash('admin123')
            new_admin = User(username='admin', password=hashed_pw, role='admin')
            db.session.add(new_admin)
            db.session.commit()
            print("Admin account created: user=admin, pass=admin123")
    
    # Render-এর জন্য পোর্ট সেট করা
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
