import os
from flask import Flask, flash, jsonify, redirect, render_template, request, session, send_file
from flask_session import Session
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
import sqlite3
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

from helpers import apology, login_required, send_email, error_page, date_format, clean_markdown

app = Flask(__name__)


# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine(os.getenv('DATABASE_URL'))
db = scoped_session(sessionmaker(bind=engine))


app.jinja_env.filters['clean_markdown'] = clean_markdown
app.jinja_env.filters['date_format'] = date_format


@app.route("/")
@login_required
def index():
    """Display index page"""

    return render_template("index.html")


@app.route('/add_diary', methods=['POST'])
@login_required
def add_diary():
    diary = request.form.get('diary')
    date = request.form.get('today_date')
    rating = request.form.get('rating')
    title = request.form.get('title')
    if not (diary and date and rating):
        return apology('please fill the form')
    if not title:
        title = 'Untitled'
    diaries_dates = db.execute('SELECT date FROM diaries WHERE user_id = :id AND date >= :date',
                               {'id': session['user_id'], 'date': date}).fetchall()
    if diaries_dates:
        return error_page('You already wrote a diary for today.')
    db.execute('INSERT INTO diaries (user_id, diary, date, title, rating) VALUES (:id, :diary, :date, :title, :rating)',
               {'id': session['user_id'], 'diary': diary, 'date': date, 'title': title, 'rating': rating})
    db.commit()
    flash('Diary Added!')
    return redirect(f"/diaries/{session['username']}/{date}")


@app.route('/diaries/<username>/<date>')
@login_required
def diary_page(username, date):
    """Shows a diary"""

    if username == session['username']:
        diary = db.execute('SELECT * FROM diaries WHERE user_id = :id AND date = :date', {'id': session['user_id'], 'date': date}).fetchone()
        if diary:
            return render_template('diary_page.html', diary=diary, username=session['username'])
        else:
            return error_page("Diary doesn't exist")
    else:
        visibility = db.execute('SELECT visibility FROM users WHERE username = :username', {'username': username}).fetchone()
        if not visibility or visibility[0] == '0':
            return error_page("Access denied or user doesn't exist.")
        else:
            diary = db.execute("""SELECT * FROM diaries JOIN users ON diaries.user_id = users.id WHERE users.username = :username AND date = :date""", 
                                {'username': session['username'], 'date': date}).fetchone()
            return render_template('diary_page.html', diary=diary, username=username)
    

@app.route('/download', methods=['POST'])
@login_required
def download_diary():
    username = request.form.get('username')
    date = request.form.get('date')
    if not (username and date):
        return apology('something went wrong')
    info = db.execute('SELECT id, visibility FROM users WHERE username = :username', {'username': username}).fetchone()
    if not info:
        return error_page("User doesn't exist")
    if username != session['username'] and info['visibility'] == '0':
        return error_page("This user's diaries are private or user doesn't exist")
    diary = db.execute('SELECT * FROM diaries WHERE user_id = :id AND date = :date', {'id': info['id'], 'date': date}).fetchone()
    if not diary:
        return error_page("Diary doesn't exist")
    with open('diary.md', 'w') as d:
        header = f"{diary['title']}\nby {username}.\n{diary['date']}\nThat day was {diary['rating']}.\n"
        d.write(header)
        d.write(diary['diary'])
    return send_file('diary.md', as_attachment=True)


@app.route("/search", methods=["GET"])
@login_required
def search():
    """Search for something (Optional)"""
    q = request.args.get('q')
    if not q:
        return error_page('Please enter something to search.')
    q = q.strip()
    diaries = db.execute("SELECT * FROM diaries WHERE user_id = :id AND (title ILIKE :q OR date ILIKE :q OR rating ILIKE :q OR diary ILIKE :q) ORDER BY date DESC",
                          {"id": session["user_id"], "q": "%" + q + "%"}).fetchall()
    return render_template("results.html", diaries=diaries)


@app.route('/public_diaries')
@login_required
def public_diaries():
    diaries = db.execute("""SELECT title, rating, diary, date, username 
                            FROM diaries JOIN users ON diaries.user_id = users.id
                            WHERE users.visibility = '1' ORDER BY date DESC""").fetchall()
    print(diaries)
    return render_template('public_diaries.html', diaries=diaries)


@app.route("/users/<username>")
@login_required
def profile(username):
    """Display user profile"""

    if not username:
        return apology('something went wrong')
    info = db.execute('SELECT * FROM users WHERE username = :username', {'username': username}).fetchone()
    if not info:
            return error_page("User doesn't exist")
    if info['id'] != session['user_id'] and info['visibility'] == '0':
        return error_page("This user's profile is private.")
    diaries = db.execute('SELECT * FROM diaries WHERE user_id = :id ORDER BY date DESC', {'id': info['id']}).fetchall()
    return render_template("profile.html", info=info, diaries=diaries)
        

@app.route("/feedback", methods=["GET", "POST"])
def feedback():
    """Get user feedback"""

    if request.method == "GET":
        return render_template("feedback.html")
    else:
        feedback_type = request.form.get("type")
        email = request.form.get("email")
        feedback = request.form.get("feedback")
        if not (feedback_type or email or feedback):
            return apology("please fill the form")
        db.execute("INSERT INTO feedback (user_id, email, feedback, feedback_type) VALUES(:id, :email, :feedback, :type)",
                   {"id": session["user_id"], "email": email, "feedback": feedback, "type": feedback_type})
        db.commit()
        flash("Feedback submitted! Thanks for your feedback!")
        return redirect("/")


@app.route("/check", methods=["GET"])
def check():
    """Check if username or email is taken"""

    email = request.args.get("email")
    username = request.args.get("username")
    email = request.args.get("email")
    verify_username = db.execute("SELECT username FROM users WHERE username = :username", {"username": username}).fetchone()
    if email:
        verify_email = db.execute("SELECT email FROM users WHERE email = :email", {"email": email}).fetchone()
        if verify_email and verify_username:
            return jsonify("Username and email already taken.")
        if verify_username:
            return jsonify("Username already taken.")
        if verify_email:
            return jsonify("Email already taken.")
    if verify_username:
        return jsonify("Username already taken.")
    return jsonify(True)


@app.route("/settings/change_visibility")
@login_required
def change_visibility():
    visibility = db.execute('SELECT visibility FROM users WHERE id = :id', {'id': session['user_id']}).fetchone()[0]
    if visibility == '0':
        visibility = '1'
    else:
        visibility = '0'
    db.execute('UPDATE users SET visibility = :visibility WHERE id = :id', {'id': session['user_id'], 'visibility': visibility})
    db.commit()
    flash('Visibility Changed!')
    return profile(session['username'])

@app.route("/settings/change_password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "GET":
        return render_template("change_password.html")
    else:
        password = request.form.get("password")
        new_password = request.form.get("new_password")
        confirmation = request.form.get("confirmation")
        pw_hash = db.execute("SELECT hash FROM users WHERE id = :id", {"id": session["user_id"]}).fetchone()["hash"]
        if not password or not new_password or new_password != confirmation:
            return apology("please fill the form correctly")
        elif password == new_password:
            return apology("new and old password can't be the same")
        elif not check_password_hash(pw_hash, password):
            return apology("incorrect password")
        else:
            # Specifications for password
            # password length
            if len(new_password) < 6:
                return apology("password must be longer than 6 characters")
            capital = None
            lower = None
            for c in new_password:
                if c.isupper():
                    capital = True
                if c.islower():
                    lower = True
            if not capital and not lower:
                return apology("password must contain atleast 1 uppercase and lowercase letter")
            # password must contain numbers
            if new_password.isalpha():
                return apology("password must contain numbers")
            # password must contain letters
            if new_password.isdigit():
                return apology("password must contain letters")
            db.execute("UPDATE users SET hash = :new_password WHERE id = :id",
                       {"new_password": generate_password_hash(new_password), "id": session["user_id"]})
            db.commit()
            flash("Password updated!")
            return redirect("/")


@app.route("/settings/change_email", methods=["GET", "POST"])
@login_required
def change_email():
    if request.method == "GET":
        return render_template("change_email.html")
    else:
        email = request.form.get("email")
        new_email = request.form.get("new_email")
        if not email or not new_email:
            return apology("please fill the form")
        emails = db.execute("SELECT email FROM users WHERE email = :email", {"email": new_email}).fetchone()
        if email != session["email"]:
            return apology("wrong email")
        if emails:
            return apology("email already taken")
        else:
            db.execute("UPDATE users SET email = :new_email WHERE id = :id",
                       {"new_email": new_email, "id": session["user_id"]})
            db.commit()
            session["email"] = new_email
            flash("Email updated!")
            return redirect("/")


@app.route("/settings/add_email", methods=["GET", "POST"])
@login_required
def add_email():
    if request.method == "GET":
        return render_template("add_email.html")
    else:
        email = request.form.get("email")
        if not email:
            return apology("please enter an email")
        q = db.execute("SELECT email FROM users WHERE email = :email", {"email": email}).fetchone()
        if q:
            return apology("this email already exists")
        db.execute("UPDATE users SET email = :new_email WHERE id = :id",
                   {"new_email": email, "id": session["user_id"]})
        db.commit()
        session["email"] = email
        flash("Email added!")
        return redirect("/")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          {"username": request.form.get("username")}).fetchone()

        # Ensure username exists and password is correct
        if not rows or not check_password_hash(rows["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows["id"]
        session["username"] = rows["username"]
        session["email"] = rows["email"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@login_required
@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "GET":
        return render_template("register.html")
    else:
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")
        email = request.form.get("email")
        if not (username or password or confirmation or email) or password != confirmation:
            return apology("please fill the form correctly to register.")
    # Checking for username
    c = db.execute("SELECT username FROM users WHERE username = :username", {"username": username}).fetchall()
    if c:
        return apology("username already taken")

    # Specifications for password

    # password length
    if len(password) < 6:
        return apology("password must be longer than 6 characters")
    # password must contain numbers
    if password.isalpha():
        return apology("password must contain numbers")
    # password must contain letters
    if password.isdigit():
        return apology("password must contain letters")

    for c in username:
        if not c.isalpha() and not c.isdigit() and c != "_":
            return apology("Please enter a valid username.")
    if len(username) < 1:
        return apology("please enter a username with more than 1 character.")
    hash_pw = generate_password_hash(password)
    from datetime import date
    time = date.today()
    try:
        q = db.execute("SELECT email FROM users WHERE email = :email", {"email": email}).fetchone()
        if q:
            return apology("this email already exists")
        db.execute("""INSERT INTO users(username, hash, email, registeration) VALUES(:username, :hash_pw, :email, :time)""",
                   {"username": username, "hash_pw": hash_pw, "email": email, "time": time})
        db.commit()
    except Exception as x:
        return apology(x)
    rows = db.execute("SELECT id, username, email FROM users WHERE username = :username",
                      {"username": username}).fetchone()
    session["user_id"] = rows["id"]
    session["username"] = rows["username"]
    session["email"] = rows["email"]
    flash("You're now registered!")
    return redirect("/")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
