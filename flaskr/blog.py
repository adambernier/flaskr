from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for
)
from psycopg2 import errors 
from slugify import slugify
from werkzeug.exceptions import abort

from flaskr.auth import login_required
from flaskr.db import get_db

bp = Blueprint('blog', __name__)

@bp.route('/')
@bp.route('/',defaults={'page':1})
@bp.route('/page/<int:page>')
def index(page=None):
    if not page:
        page = 1
    PAGINATION_SIZE = 3
    db = get_db()
    db.execute(
        'SELECT count(p.id) row_count, min(p.id) min_id FROM post p'
        )
    result = db.fetchone()
    count, min_id = result['row_count'], result['min_id']
    page_from = count - ((page - 1) * PAGINATION_SIZE)
    db.execute("""
        SELECT p.id, title, body, created, author_id, username, pt.tags
         FROM post p
         JOIN usr u ON p.author_id = u.id
         LEFT JOIN (
            SELECT pt.post_id, string_agg(t.title, ' ') tags
            FROM tag t
                JOIN post_tag pt
                ON pt.tag_id = t.id
            GROUP BY pt.post_id
         ) pt
         ON pt.post_id = p.id
         WHERE p.id <= %s
         ORDER BY created DESC
         FETCH FIRST %s ROWS ONLY;""",
        (page_from,PAGINATION_SIZE,)
    )
    posts = db.fetchall()
    try:
        if posts[-1]['id'] == min_id:
            last_post = True
        else:
            last_post = False
    except IndexError:
        last_post = True
    return render_template('blog/index.html',posts=posts,page=page,
        PAGINATION_SIZE=PAGINATION_SIZE,last_post=last_post)

@bp.route('/create', methods=('GET', 'POST'))
@login_required
def create():
    if request.method == 'POST':
        title = request.form['title']
        body = request.form['body']
        tags = request.form['tags']
        tags = tags.split(' ') # expand to allow other delimiters?
        tag_slugs = [slugify(tag) for tag in tags]
        error = None

        if not title:
            error = 'Title is required.'

        if error is not None:
            flash(error)
        else:
            db = get_db()
            db.execute(
                'INSERT INTO post (title, body, author_id)'
                ' VALUES (%s,%s,%s) RETURNING id;',
                (title,body,g.user['id'],)
            )
            post_id = db.fetchone()['id']
            tag_ids = []
            for tag,tag_slug in zip(tags,tag_slugs):
                try:                 
                    db.execute(
                        'INSERT INTO tag (title, slug)'
                        ' VALUES (%s,%s) RETURNING id;',
                        (tag, tag_slug,)
                    )
                    tag_ids.append(db.fetchone()['id'])
                except errors.UniqueViolation:
                    db.execute(
                        'SELECT id FROM tag WHERE slug = %s;',
                        (tag_slug,)
                    )
                    tag_ids.append(db.fetchone()['id'])
            print(tag_ids)
            db.executemany(
                'INSERT INTO post_tag (post_id, tag_id)'
                ' VALUES (%s,%s);',
                list(zip([post_id]*len(tag_ids),tag_ids))
            )
            return redirect(url_for('blog.index'))

    return render_template('blog/create.html')

def get_post(id, check_author=True):
    get_db().execute("""
        SELECT p.id, title, body, created, author_id, username, pt.tags
         FROM post p JOIN usr u ON p.author_id = u.id
         LEFT JOIN (
            SELECT pt.post_id, string_agg(t.title, ' ') tags
            FROM tag t
                JOIN post_tag pt
                ON pt.tag_id = t.id
            GROUP BY pt.post_id
         ) pt
         ON pt.post_id = p.id
         WHERE p.id = %s;""",
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
    db.execute("""
        SELECT p.id, title, body, created, author_id, username, pt.tags
         FROM post p JOIN usr u ON p.author_id = u.id
         LEFT JOIN (
             SELECT pt.post_id, string_agg(t.title, ' ') tags
             FROM tag t
             JOIN post_tag pt
             ON pt.tag_id = t.id
             GROUP BY pt.post_id 
         ) pt
         ON pt.post_id = p.id
         WHERE p.id = %s
         ORDER BY created DESC;""",
        (id,)
    )
    post = db.fetchone()
    print(post)
    return render_template('blog/detail.html', post=post)
    
@bp.route('/<int:id>/update', methods=('GET', 'POST'))
@login_required
def update(id):
    post = get_post(id)

    if request.method == 'POST':
        title = request.form['title']
        body = request.form['body']
        tags = request.form['tags']
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
            return redirect(url_for('blog.index'))

    return render_template('blog/update.html', post=post)
    
@bp.route('/tag/<tag_slug>/page/<int:page>')
def tag(page=None,tag_slug=None):
    if not page:
        page = 1
    PAGINATION_SIZE = 3
    db = get_db()
    db.execute(
        'SELECT count(p.id) row_count, min(p.id) min_id FROM post p'
        )
    result = db.fetchone()
    count, min_id = result['row_count'], result['min_id']
    page_from = count - ((page - 1) * PAGINATION_SIZE)
    db.execute("""
        SELECT p.id, title, body, created, author_id, username, pt.tags
         FROM post p
         JOIN usr u ON p.author_id = u.id
         JOIN (
            SELECT pt.post_id, string_agg(t.title, ' ') tags
            FROM tag t
                JOIN post_tag pt
                ON pt.tag_id = t.id
            WHERE t.slug = %s
            GROUP BY pt.post_id
         ) pt
         ON pt.post_id = p.id
         WHERE p.id <= %s
         ORDER BY created DESC
         FETCH FIRST %s ROWS ONLY;""",
        (tag_slug,page_from,PAGINATION_SIZE,)
    )
    posts = db.fetchall()
    try:
        if posts[-1]['id'] == min_id:
            last_post = True
        else:
            last_post = False
    except IndexError:
        last_post = True
    return render_template('blog/index.html',posts=posts,page=page,
        PAGINATION_SIZE=PAGINATION_SIZE,last_post=last_post)

@bp.route('/<int:id>/delete', methods=('POST',))
@login_required
def delete(id):
    get_post(id)
    db = get_db()
    db.execute('DELETE FROM post_tag where post_id = %s;', (id,))
    db.execute('DELETE FROM post WHERE id = %s;', (id,))
    #db.commit()
    return redirect(url_for('blog.index'))
