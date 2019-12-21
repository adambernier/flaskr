from flask import (
    Blueprint, flash, g, json, redirect, render_template, request, url_for
)
from flask_login import (
    current_user,
    login_required,
    login_user,
    logout_user,
)
from psycopg2 import errors 
from slugify import slugify
from werkzeug.exceptions import abort, BadRequestKeyError

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
        
    if current_user.is_authenticated:
        g.user = current_user
        
    return render_template('blog/index.html',posts=posts,page=page,
        PAGINATION_SIZE=PAGINATION_SIZE,last_post=last_post)

@bp.route('/create', methods=('GET', 'POST',))
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
                'INSERT INTO post (title, body, author_id, thank_count)'
                ' VALUES (%s,%s,%s,%s) RETURNING id;',
                (title,body,g.user['id'],0)
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
            db.executemany(
                'INSERT INTO post_tag (post_id, tag_id)'
                ' VALUES (%s,%s);',
                list(zip([post_id]*len(tag_ids),tag_ids))
            )
            return redirect(url_for('blog.index'))

    return render_template('blog/create.html')
    
@bp.route('/create_comment', methods=('POST',))
@login_required
def create_comment():
    body = request.form['body']
    post_id = request.form['post_id']
    author_id = request.form['author_id']
    
    db = get_db()
    db.execute(
        'INSERT INTO post_comment (body, post_id, author_id)'
        ' VALUES (%s,%s,%s);',
        (body,post_id,author_id)
    )
    
    return redirect(url_for('blog.index'))

def get_post(id, check_author=True):
    get_db().execute("""
        SELECT p.id, title, body, created, author_id, username, 
            thank_count, pt.tags 
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
        
    get_db().execute("""
        SELECT c.id, body, created, username 
        FROM post_comment c
            LEFT JOIN usr u 
            ON u.id = c.author_id 
        WHERE c.post_id = %s;""", 
        (post['id'],)
    )
    comments = get_db().fetchall()

    return post, comments 
    
@bp.route('/<int:id>/thank', methods=('POST',))
def thank(id):
    if request.method == "POST":
        db = get_db()
        db.execute('''UPDATE post 
                      SET thank_count = thank_count + 1
                      WHERE id = %s;''',(id,))
        if db.rowcount == 1:
            db.execute('select thank_count from post where id = %s;',(id,))
            thank_count = db.fetchone()['thank_count']
            return json.dumps({'status': 'success', 'thank_count': thank_count})
        else:
            return json.dumps({'status': 'record not updated'})
        return redirect(url_for('blog.detail'))
    
@bp.route('/<int:id>/detail',methods=('GET',))
@login_required
def detail(id):
    post, comments = get_post(id)
    try:
        thank_count = request.args['thank_count']
    except BadRequestKeyError:
        thank_count = post['thank_count']
    return render_template('blog/detail.html', post=post, 
                           comments=comments, thank_count=thank_count)
    
@bp.route('/<int:id>/update', methods=('GET', 'POST'))
@login_required
def update(id):
    post, comments = get_post(id)

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
        SELECT p.id, title, body, created, author_id, username, 
               pt.tags, pt_addl.addl_tags
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
         LEFT JOIN (
            SELECT pt.post_id, string_agg(t.title, ' ') addl_tags
            FROM tag t
                JOIN post_tag pt
                ON pt.tag_id = t.id
            WHERE t.slug <> %s
            GROUP BY pt.post_id
         ) pt_addl
         ON pt_addl.post_id = p.id
         WHERE p.id <= %s
         ORDER BY created DESC
         FETCH FIRST %s ROWS ONLY;""",
        (tag_slug,tag_slug,page_from,PAGINATION_SIZE,)
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
    db = get_db()
    db.execute('DELETE FROM post_tag where post_id = %s;', (id,))
    db.execute('DELETE FROM post_comment where post_id = %s;', (id,))
    db.execute('DELETE FROM post WHERE id = %s;', (id,))
    return redirect(url_for('blog.index'))
    
@bp.route('/privacy_policy')
def privacy_policy():
    privacy_language = '''
The following policy is intended to explain how your personal information will be treated when you use our site. Personal information includes your name, e-mail addresses, click-through activity and any other personal information you may provide here.

Email and other private information

When you decide to go through registration process in order to obtain personal user account at mechanical-meat.com, you are proposed to fill registration form which asks for your email and name. Your email is needed for us to complete registration process and to restore your account password if you will ask about it. We will not send you any spam messages. Actually, you will get emails from Mechanical Meat only if you chose to - it can be used to notify you about private messages, sent to you by other users, or satisfaction of your request or appearance of new comments to your articles etc.

Please, do not use your email address as your user-name unless you are fully aware of fact that it will become visible to all visitors of the site.
'''
    return render_template('blog/privacy_policy.html',privacy_language=privacy_language)
