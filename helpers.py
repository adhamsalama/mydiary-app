import os
import smtplib
from flask import redirect, render_template, request, session
from functools import wraps
import bleach
from markdown import markdown



def apology(message, code=400):
    """Render message as an apology to user."""
    def escape(s):
        """
        Escape special characters.

        https://github.com/jacebrowning/memegen#special-characters
        """
        for old, new in [("-", "--"), (" ", "-"), ("_", "__"), ("?", "~q"),
                         ("%", "~p"), ("#", "~h"), ("/", "~s"), ("\"", "''")]:
            s = s.replace(old, new)
        return s
    return render_template("apology.html", top=code, bottom=escape(message)), code


def error_page(message="Something went wrong"):
    """Render an error page"""

    return render_template('error.html', message=message)

def login_required(f):
    """
    Decorate routes to require login.

    http://flask.pocoo.org/docs/1.0/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function


def send_email(receiver, name, subject, message):
    """Sends an email"""
    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()
    server.login(os.getenv("email"), os.getenv("password"))
    server.sendmail(os.getenv("email"), receiver, f"To: {receiver}\nSubject: {subject}\nHello {name},\n {message}")


def date_format(date_):
    """Formats a date"""

    return date_.strftime("%A %b %d %Y")



def clean_markdown(note):
    """Cleans a markdown text then turns it into html"""

    return markdown(bleach.clean(note))
