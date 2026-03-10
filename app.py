import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.secret_key = "niloy_mess_secret"

# ---------- DATABASE ----------
db_url = os.getenv("DATABASE_URL")

if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = db_url or "sqlite:///mess.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


# ---------- MODELS ----------

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(db.String(50), unique=True, nullable=False)

    password = db.Column(db.String(255), nullable=False)

    role = db.Column(db.String(10), default="border")

    deposit = db.Column(db.Float, default=0.0)


class Meal(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))

    date = db.Column(db.String(20))

    morning = db.Column(db.Float, default=0)

    lunch = db.Column(db.Float, default=0)

    dinner = db.Column(db.Float, default=0)

    is_off = db.Column(db.Boolean, default=False)

    status = db.Column(db.String(20), default="approved")


class Bazar(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))

    date = db.Column(db.String(20))

    amount = db.Column(db.Float, default=0)

    details = db.Column(db.Text)

    status = db.Column(db.String(20), default="approved")


class ExtraCost(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    description = db.Column(db.String(100))

    amount = db.Column(db.Float)


# ---------- STATS FUNCTION ----------

def get_stats():

    total_bazar = db.session.query(db.func.sum(Bazar.amount)).filter_by(status="approved").scalar() or 0

    total_meals = db.session.query(
        db.func.sum(Meal.morning + Meal.lunch + Meal.dinner)
    ).filter_by(is_off=False, status="approved").scalar() or 0

    meal_rate = total_bazar / total_meals if total_meals > 0 else 0

    total_extra = db.session.query(db.func.sum(ExtraCost.amount)).scalar() or 0

    users = User.query.filter_by(role="border").count()

    extra_per_head = total_extra / users if users > 0 else 0

    return total_bazar, total_meals, meal_rate, total_extra, extra_per_head


# ---------- CREATE TABLE ----------

with app.app_context():

    db.create_all()

    admin = User.query.filter_by(username="admin").first()

    if not admin:

        pw = generate_password_hash("admin123")

        db.session.add(User(username="admin", password=pw, role="admin"))

        db.session.commit()


# ---------- CONTEXT ----------

@app.context_processor
def inject_now():

    return {"now": datetime.now()}


# ---------- ROUTES ----------

@app.route("/")
def home():

    if "user_id" in session:

        if session["role"] == "admin":

            return redirect(url_for("admin"))

        else:

            return redirect(url_for("member_dashboard"))

    return render_template("login.html")


# ---------- LOGIN ----------

@app.route("/login", methods=["POST"])
def login():

    username = request.form.get("username")

    password = request.form.get("password")

    user = User.query.filter_by(username=username).first()

    if user and check_password_hash(user.password, password):

        session["user_id"] = user.id

        session["role"] = user.role

        session["username"] = user.username

        return redirect(url_for("home"))

    flash("Wrong username or password")

    return redirect(url_for("home"))


# ---------- ADMIN ----------

@app.route("/admin", methods=["GET", "POST"])
def admin():

    if session.get("role") != "admin":

        return redirect(url_for("home"))

    total_bazar, total_meals, meal_rate, total_extra, extra_per_head = get_stats()

    users = User.query.filter_by(role="border").all()

    if request.method == "POST":

        action = request.form.get("action")

        if action == "add_member":

            username = request.form["username"]

            password = generate_password_hash(request.form["password"])

            db.session.add(User(username=username, password=password))

        elif action == "add_deposit":

            uid = int(request.form["user_id"])

            amount = float(request.form["amount"])

            user = User.query.get(uid)

            user.deposit += amount

        elif action == "add_bazar":

            uid = int(request.form["user_id"])

            amount = float(request.form["amount"])

            db.session.add(

                Bazar(

                    user_id=uid,

                    amount=amount,

                    date=datetime.now().strftime("%Y-%m-%d"),

                )

            )

        elif action == "add_extra":

            desc = request.form["desc"]

            amount = float(request.form["amount"])

            db.session.add(ExtraCost(description=desc, amount=amount))

        db.session.commit()

        return redirect(url_for("admin"))

    return render_template(
        "admin.html",
        users=users,
        total_bazar=total_bazar,
        total_meals=total_meals,
        meal_rate=meal_rate,
        total_extra=total_extra,
        extra_per_head=extra_per_head,
    )


# ---------- MEMBER DASHBOARD ----------

@app.route("/member/dashboard")
def member_dashboard():

    if "user_id" not in session:

        return redirect(url_for("home"))

    user = User.query.get(session["user_id"])

    total_bazar, total_meals, meal_rate, total_extra, extra_per_head = get_stats()

    my_meals = db.session.query(

        db.func.sum(Meal.morning + Meal.lunch + Meal.dinner)

    ).filter_by(user_id=user.id, is_off=False, status="approved").scalar() or 0

    personal_cost = (my_meals * meal_rate) + extra_per_head

    balance = user.deposit - personal_cost

    days_left = 0

    if meal_rate > 0 and balance > 0:

        days_left = balance / (meal_rate * 1.5)

    return render_template(

        "member.html",

        user=user,

        my_meals=my_meals,

        meal_rate=meal_rate,

        personal_cost=personal_cost,

        balance=balance,

        days_left=days_left,

        extra_per_head=extra_per_head,

    )


# ---------- LOGOUT ----------

@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("home"))


# ---------- RUN ----------

if __name__ == "__main__":

    port = int(os.environ.get("PORT", 5000))

    app.run(host="0.0.0.0", port=port)
