import os
from flask import Blueprint, request, render_template, flash, url_for
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from helpers import *
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker


settings = Blueprint('settings', __name__)

engine = create_engine(os.getenv('DATABASE_URL'))
db = scoped_session(sessionmaker(bind=engine))

@settings.route("/settings/change_visibility")
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
    return redirect(url_for('profile', username=session['username']))

@settings.route("/settings/change_password", methods=["GET", "POST"])
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


@settings.route("/settings/change_email", methods=["GET", "POST"])
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


@settings.route("/settings/add_email", methods=["GET", "POST"])
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


@settings.route("/feedback", methods=["GET", "POST"])
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


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    settings.errorhandler(code)(errorhandler)