import os
from flask import Blueprint, request, redirect, session, render_template, flash, send_file
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from helpers import apology, login_required, error_page
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

diary = Blueprint('diary', __name__)


engine = create_engine(os.getenv('DATABASE_URL'))
db = scoped_session(sessionmaker(bind=engine))


@diary.route('/add_diary', methods=['POST'])
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


@diary.route('/diaries/<username>/<date>')
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
    

@diary.route('/download', methods=['POST'])
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


@diary.route('/public_diaries')
@login_required
def public_diaries():
    diaries = db.execute("""SELECT title, rating, diary, date, username 
                            FROM diaries JOIN users ON diaries.user_id = users.id
                            WHERE users.visibility = '1' ORDER BY date DESC""").fetchall()
    return render_template('public_diaries.html', diaries=diaries)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    diary.errorhandler(code)(errorhandler)
