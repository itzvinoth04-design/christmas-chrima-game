from flask import Flask, render_template, redirect, url_for, request
from flask_sqlalchemy import SQLAlchemy
from functools import wraps
from flask import abort
from flask_login import (
    LoginManager, UserMixin,
    login_user, login_required,
    logout_user, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
import random
import os
app = Flask(__name__)
app.secret_key = "christmas_secret_key"

# Database config
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
with app.app_context():
    db.create_all()
    print("✅ Supabase tables created")

# Login manager
login_manager = LoginManager(app)
login_manager.login_view = "login"

# ------------------ MODEL ------------------
class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    chrima_id = db.Column(db.Integer, db.ForeignKey("users.id"))


class Task(db.Model):
    __tablename__ = "tasks"

    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    giver_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    receiver_id = db.Column(db.Integer, db.ForeignKey("users.id"))


class GameState(db.Model):
    __tablename__ = "GameState"
    id = db.Column(db.Integer, primary_key=True)
    reveal_enabled = db.Column(db.Boolean, default=False)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ------------------ ROUTES ------------------
@app.route("/")
def welcome():
    return render_template("welcome.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        if User.query.filter_by(username=username).first():
            return "User already exists"

        hashed = generate_password_hash(password)
        is_first_user = User.query.count() == 0

        user = User(
            username=username,
            password=hashed,
            is_admin=is_first_user
        )


        db.session.add(user)
        db.session.commit()

        return redirect(url_for("login"))

    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for("dashboard"))

        return "Invalid credentials"

    return render_template("login.html")

@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

@app.route("/admin")
@login_required
@admin_required
def admin():
    return render_template("admin.html")

@app.route("/assign-chrima", methods=["POST"])
@login_required
@admin_required
def assign_chrima():
    users = User.query.all()

    if len(users) < 2:
        return "Not enough users"

    giver_ids = [u.id for u in users]
    receiver_ids = giver_ids[:]

    while True:
        random.shuffle(receiver_ids)
        if all(g != r for g, r in zip(giver_ids, receiver_ids)):
            break

    for giver_id, receiver_id in zip(giver_ids, receiver_ids):
        giver = User.query.get(giver_id)
        giver.chrima_id = receiver_id

    db.session.commit()
    return "🎁 Chrima assigned successfully!"


@app.route("/my-chrima")
@login_required
def my_chrima():
    if current_user.chrima_id is None:
        return "Chrima not assigned yet"

    chrima_user = User.query.get(current_user.chrima_id)
    return f"🎄 Your Chrima is: {chrima_user.username}"


@app.route("/debug-db")
def debug_db():
    users = User.query.all()
    return "<br>".join([u.username for u in users]) or "No users yet"




@app.route("/view-task")
@login_required
def view_task():
    tasks = Task.query.filter_by(receiver_id=current_user.id).all()
    return render_template("view_task.html", tasks=tasks)


@app.route("/give-task", methods=["GET", "POST"])
@login_required
def give_task():
    if current_user.chrima_id is None:
        return "Chrima not assigned yet"

    if request.method == "POST":
        task_text = request.form["task"]

        task = Task(
            sender_id=current_user.id,
            receiver_id=current_user.chrima_id,
            content=task_text
        )

        db.session.add(task)
        db.session.commit()
        return "✅ Task sent anonymously!"

    return render_template("give_task.html")

@app.route("/reveal")
@login_required
@admin_required
def reveal():
    users = User.query.all()
    reveal_data = []

    for u in users:
        if u.chrima_id:
            receiver = User.query.get(u.chrima_id)
            reveal_data.append({
                "giver": u.username,
                "receiver": receiver.username
            })

    return render_template("reveal.html", reveal_data=reveal_data)

@app.route("/enable-reveal", methods=["POST"])
@login_required
@admin_required
def enable_reveal():
    state = GameState.query.first()
    state.reveal_enabled = True
    db.session.commit()
    return redirect(url_for("admin"))

@app.route("/view-my-chrima")
@login_required
def view_my_chrima():
    state = GameState.query.first()

    if not state.reveal_enabled:
        return "⛔ Reveal not enabled yet"

    if current_user.chrima_id is None:
        return "Chrima not assigned"

    chrima_user = User.query.get(current_user.chrima_id)
    return render_template("my_chrima.html", chrima=chrima_user.username)

# ------------------ INIT DB ------------------

with app.app_context():
    db.drop_all()
    db.create_all()
    print("✅ Tables recreated")


# ------------------ RUN ------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0",port=5000,debug=False)
