from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for
)

from werkzeug.exceptions import abort

from flaskr.auth import login_required
from flaskr.db import get_db

from psycopg2.errors import UndefinedFunction

bp = Blueprint('about', __name__, url_prefix='/about')

def get_user(id, check_user=True):
    try:
        get_db().execute("""
            SELECT id, username, username_slug, profile_pic, about
             FROM usr  
             WHERE id = %s;""",
            (id,)
        )
    except UndefinedFunction:
        get_db().execute("""
            SELECT id, username, username_slug, profile_pic, about
             FROM usr  
             WHERE id = %s;""",
            (str(id),)
        )
    user = get_db().fetchone()

    if user is None:
        abort(404, "User id {0} doesn't exist.".format(id))

    if check_user and user['id'] != g.user['id']:
        abort(403)

    return user
    
@bp.route('/me/<int:id>/')
def me(id):
    user = get_user(id)
    
    if user is None:
        abort(404, "User id {0} doesn't exist.".format(id))
    
    return render_template('about/me.html',user=user)
    
@bp.route('/create', methods=('GET','POST',))
@login_required
def create():
    if request.method == 'POST':
        about = request.form['about']
        author_id = request.form['author_id']
        
        db = get_db()
        db.execute(
            'UPDATE usr SET about = %s '
            ' WHERE id = %s;',
            (about,g.user['id'],)
        )
        
        return redirect(url_for('blog.index'))
    
    return render_template('about/create.html')

@bp.route('/<id>/update', methods=('GET', 'POST'))
@login_required
def update(id):
    user = get_user(id)

    if request.method == 'POST':
        about = request.form['about']
        
        db = get_db()
        db.execute(
            'UPDATE usr SET about = %s '
            ' WHERE id = %s;',
            (about, id)
        )
        
        return redirect(url_for('index'))
        
    return render_template('about/update.html', user=user)

@bp.route('/<int:id>/delete', methods=('POST',))
@login_required
def delete(id):
    db = get_db()
    db.execute('DELETE FROM usr WHERE id = %s;', (id,))
    return redirect(url_for('blog.index'))
