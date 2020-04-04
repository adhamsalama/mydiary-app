import os
from flask import Flask, flash, jsonify, redirect, render_template, request, session, send_file, Blueprint
from flask_session import Session
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
import sqlite3
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

from helpers import apology, login_required, send_email, error_page, date_format, clean_markdown


from auth.routes import auth
from diary.routes import diary
from settings.routes import settings


app = Flask(__name__)


app.register_blueprint(auth)
app.register_blueprint(diary)
app.register_blueprint(settings)

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
engine = create_engine("sqlite:///tables.db?""check_same_thread=False")
db = scoped_session(sessionmaker(bind=engine))


app.jinja_env.filters['clean_markdown'] = clean_markdown
app.jinja_env.filters['date_format'] = date_format


@app.route("/")
@login_required
def index():
    """Display index page"""

    return render_template("index.html")



@app.route("/search", methods=["GET"])
@login_required
def search():
    """Search for something (Optional)"""
    q = request.args.get('q')
    if not q:
        return error_page('Please enter something to search.')
    q = q.strip()
    diaries = db.execute("SELECT * FROM diaries WHERE user_id = :id AND (title LIKE :q OR date LIKE :q OR rating LIKE :q OR diary LIKE :q) ORDER BY date DESC",
                          {"id": session["user_id"], "q": "%" + q + "%"}).fetchall()
    return render_template("results.html", diaries=diaries)



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
        

def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
