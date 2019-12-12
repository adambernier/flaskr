from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for
)
from werkzeug.exceptions import abort

from unicodedata import normalize 

from flaskr.auth import login_required
from flaskr.db import get_db

bp = Blueprint('blog', __name__)

#@bp.route('/')
@bp.route('/', defaults={'page':1})
@bp.route('/page/<int:page>')
def index():
    db = get_db()
    db.execute(
        'SELECT p.id, title, body, created, author_id, username'
        ' FROM post p JOIN usr u ON p.author_id = u.id'
        ' ORDER BY created DESC;'
    )
    posts = db.fetchall()
    return render_template('blog/index.html', posts=posts)

@bp.route('/create', methods=('GET', 'POST'))
@login_required
def create():
    if request.method == 'POST':
        title = request.form['title']
        body = request.form['body']
        error = None

        if not title:
            error = 'Title is required.'

        if error is not None:
            flash(error)
        else:
            db = get_db()
            db.execute(
                'INSERT INTO post (title, body, author_id)'
                ' VALUES (%s,%s,%s);',
                (title, body, g.user['id'])
            )
            #db.commit()
            return redirect(url_for('blog.index'))

    return render_template('blog/create.html')

def get_post(id, check_author=True):
    get_db().execute(
        'SELECT p.id, title, body, created, author_id, username'
        ' FROM post p JOIN usr u ON p.author_id = u.id'
        ' WHERE p.id = %s;',
        (id,)
    )
    post = get_db().fetchone()

    if post is None:
        abort(404, "Post id {0} doesn't exist.".format(id))

    if check_author and post['author_id'] != g.user['id']:
        abort(403)

    return post
    
@bp.route('/<int:id>/detail',methods=('GET',))
@login_required
def detail(id):
    post = get_post(id)
    db = get_db()
    db.execute(
        'SELECT p.id, title, body, created, author_id, username'
        ' FROM post p JOIN usr u ON p.author_id = u.id'
        ' WHERE p.id = %s'
        ' ORDER BY created DESC;',
        (id,)
    )
    post = db.fetchone()
    return render_template('blog/detail.html', post=post)
    
@bp.route('/<int:id>/update', methods=('GET', 'POST'))
@login_required
def update(id):
    post = get_post(id)

    if request.method == 'POST':
        title = request.form['title']
        body = request.form['body']
        error = None

        if not title:
            error = 'Title is required.'

        if error is not None:
            flash(error)
        else:
            db = get_db()
            db.execute(
                'UPDATE post SET title = %s, body = %s'
                ' WHERE id = %s;',
                (title, body, id)
            )
            #db.commit()
            return redirect(url_for('blog.index'))

    return render_template('blog/update.html', post=post)

@bp.route('/<int:id>/delete', methods=('POST',))
@login_required
def delete(id):
    get_post(id)
    db = get_db()
    db.execute('DELETE FROM post WHERE id = %s;', (id,))
    #db.commit()
    return redirect(url_for('blog.index'))
