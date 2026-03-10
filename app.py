import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'niloy_mess_2026_secure'

# --- ডাটাবেজ কনফিগারেশন (Postgres Fix) ---
db_url = os.getenv("DATABASE_URL")
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url or 'sqlite:///mess.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- মডেলস ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(10), default='border')
    deposit = db.Column(db.Float, default=0.0)

class Meal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    morning = db.Column(db.Float, default=0.0)
    lunch = db.Column(db.Float, default=0.0)
    dinner = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default='approved')

class Bazar(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default='approved')

# --- অটোমেটিক টেবিল তৈরি (মেইন পার্ট) ---
with app.app_context():
    db.create_all()
    # অ্যাডমিন ইউজার চেক
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        db.session.add(User(
            username='admin', 
            password=generate_password_hash('admin123'), 
            role='admin'
        ))
        db.session.commit()

# --- রুটস ---
@app.route('/')
def index():
    if 'user_id' in session:
        return "লগইন সফল! আপনার অ্যাপ কাজ করছে।" # টেস্ট করার জন্য
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')
    user = User.query.filter_by(username=username).first()
    if user and check_password_hash(user.password, password):
        session['user_id'] = user.id
        session['role'] = user.role
        return redirect(url_for('index'))
    return "ইউজারনেম বা পাসওয়ার্ড ভুল!"

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
