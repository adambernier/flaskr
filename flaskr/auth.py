import functools, json, os
import requests

from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for
)
from flask_login import (
    UserMixin,
    LoginManager,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from oauthlib.oauth2 import WebApplicationClient
from werkzeug.security import check_password_hash, generate_password_hash

from flaskr.db import get_db

from psycopg2.errors import UndefinedFunction
from slugify import slugify

bp = Blueprint('auth', __name__, url_prefix='/auth')

# Configuration
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", None)
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", None)
GOOGLE_DISCOVERY_URL = (
    "https://accounts.google.com/.well-known/openid-configuration"
)
# OAuth 2 client setup
client = WebApplicationClient(GOOGLE_CLIENT_ID)

def get_google_provider_cfg():
    return requests.get(GOOGLE_DISCOVERY_URL).json()

# ~ @bp.route('/register', methods=('GET', 'POST'))
# ~ def register():
    # ~ if request.method == 'POST':
        # ~ username = request.form['username']
        # ~ password = request.form['password']
        # ~ db = get_db()
        # ~ error = None

        # ~ db.execute(
            # ~ 'SELECT id FROM usr WHERE username = %s', (username,)
        # ~ )
        # ~ if not username:
            # ~ error = 'Username is required.'
        # ~ elif not password:
            # ~ error = 'Password is required.'
        # ~ elif db.fetchone() is not None:
            # ~ error = 'User {} is already registered.'.format(username)

        # ~ if error is None:
            # ~ db.execute(
                # ~ 'INSERT INTO usr (username, pass) VALUES (%s, %s)',
                # ~ (username, generate_password_hash(password))
            # ~ )
            # ~ #db.commit()
            # ~ return redirect(url_for('auth.login'))

        # ~ flash(error)

    # ~ return render_template('auth/register.html')
    
# ~ @bp.route('/login', methods=('GET', 'POST'))
# ~ def login():
    # ~ if request.method == 'POST':
        # ~ username = request.form['username']
        # ~ password = request.form['password']
        # ~ db = get_db()
        # ~ error = None
        # ~ db.execute(
            # ~ 'SELECT * FROM usr WHERE username = %s', (username,)
        # ~ )
        # ~ user = db.fetchone()

        # ~ if user is None:
            # ~ error = 'Incorrect username.'
        # ~ elif not check_password_hash(user['pass'], password):
            # ~ error = 'Incorrect password.'

        # ~ if error is None:
            # ~ session.clear()
            # ~ session['user_id'] = user['id']
            # ~ return redirect(url_for('index'))

        # ~ flash(error)

    # ~ return render_template('auth/login.html')
    
@bp.route("/login")
def login():
    # Find out what URL to hit for Google login
    google_provider_cfg = get_google_provider_cfg()
    authorization_endpoint = google_provider_cfg["authorization_endpoint"]

    # Use library to construct the request for Google login and provide
    # scopes that let you retrieve user's profile from Google
    request_uri = client.prepare_request_uri(
        authorization_endpoint,
        redirect_uri=request.base_url + "/callback",
        scope=["openid", "email", "profile"],
    )
    return redirect(request_uri)

@bp.route("/login/callback")
def callback():
    # Get authorization code Google sent back to you
    code = request.args.get("code")
    
    # Find out what URL to hit to get tokens that allow you to ask for
    # things on behalf of a user
    google_provider_cfg = get_google_provider_cfg()
    token_endpoint = google_provider_cfg["token_endpoint"]
    
    # Prepare and send a request to get tokens! Yay tokens!
    token_url, headers, body = client.prepare_token_request(
        token_endpoint,
        authorization_response=request.url,
        redirect_url=request.base_url,
        code=code
    )
    token_response = requests.post(
        token_url,
        headers=headers,
        data=body,
        auth=(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET),
    )

    # Parse the tokens!
    client.parse_request_body_response(json.dumps(token_response.json()))
    
    # Now that you have tokens (yay) let's find and hit the URL
    # from Google that gives you the user's profile information,
    # including their Google profile image and email
    userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
    uri, headers, body = client.add_token(userinfo_endpoint)
    userinfo_response = requests.get(uri, headers=headers, data=body)
    
    # You want to make sure their email is verified.
    # The user authenticated with Google, authorized your
    # app, and now you've verified their email through Google!
    if userinfo_response.json().get("email_verified"):
        unique_id = userinfo_response.json()["sub"]
        users_email = userinfo_response.json()["email"]
        picture = userinfo_response.json()["picture"]
        users_name = userinfo_response.json()["given_name"]
        family_name = userinfo_response.json()["family_name"]
    else:
        return "User email not available or not verified by Google.", 400
        
    # Create a user in your db with the information provided
    # by Google
    user = User(
        id_=unique_id, username=users_name, email=users_email, 
        profile_pic=picture, family_name
    )

    # Doesn't exist? Add it to the database.
    if not User.get(unique_id):
        User.create(unique_id, users_name, users_email, picture, family_name)

    # Begin user session by logging the user in
    login_user(user)
    
    # send email each time a new user logs in
    mailgun_api_key = os.environ.get('MAILGUN_API_KEY',None)
    mailgun_domain = os.environ.get('MAILGUN_DOMAIN',None)
    requests.post(
        f"https://api.mailgun.net/v3/{mailgun_domain}/messages",
        auth=("api", mailgun_api_key),
        data={"from": "User <mailgun@sandbox826abd175eca4480bb33dd7076ab4f5b.mailgun.org>",
            "to": [os.environ.get('ADMIN_EMAIL')],
            "subject": "Hello",
            "text": f"User {users_name} just logged on!"})

    # Send user back to homepage
    return redirect(url_for("index"))

@bp.before_app_request
def load_logged_in_user():
    user_id = session.get('user_id')

    if user_id is None:
        g.user = None
    else:
        try:
            get_db().execute(
                'SELECT * FROM usr WHERE id = %s;', (user_id,)
            )
        except UndefinedFunction:
            get_db().execute(
                'SELECT * FROM usr WHERE id = %s;', (str(user_id),)
            )
        g.user = get_db().fetchone()

# ~ @bp.route('/logout')
# ~ def logout():
    # ~ session.clear()
    # ~ return redirect(url_for('index'))

def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for('auth.login'))

        return view(**kwargs)

    return wrapped_view

@bp.route("/logout")
@login_required
def logout():
    logout_user()
    
    # send email each time a new user logs out 
    mailgun_api_key = os.environ.get('MAILGUN_API_KEY',None)
    mailgun_domain = os.environ.get('MAILGUN_DOMAIN',None)
    requests.post(
        f"https://api.mailgun.net/v3/{mailgun_domain}/messages",
        auth=("api", mailgun_api_key),
        data={"from": "User <mailgun@sandbox826abd175eca4480bb33dd7076ab4f5b.mailgun.org>",
            "to": [os.environ.get('ADMIN_EMAIL')],
            "subject": "Hello",
            "text": f"A user just logged off!"})
    
    return redirect(url_for("index"))

class User(UserMixin):
    def __init__(self, id_, username, email, profile_pic, familyname):
        self.id = id_
        self.username = username
        self.email = email
        self.profile_pic = profile_pic
        self.familyname = familyname

    @staticmethod
    def get(user_id):
        db = get_db()
        try:
            db.execute(
                "SELECT * FROM usr WHERE id = %s;", (user_id,)
            )
        except UndefinedFunction:
            db.execute(
                "SELECT * FROM usr WHERE id = %s;", (str(user_id),)
            )
        user = db.fetchone()
        if not user:
            return None

        user = User(
            id_=user['id'], 
            username=user['username'], 
            email=user['email'], 
            profile_pic=user['profile_pic']
            familyname=user['familyname']
        )
        return user

    @staticmethod
    def create(id_, username, email, profile_pic, familyname):
        username_slug = slugify(username)
        
        db = get_db()
        db.execute("""
            INSERT INTO usr 
                (id, username, email, profile_pic, username_slug, familyname) 
            VALUES (%s,%s,%s,%s,%s,%s);""",
            (id_, username, email, profile_pic, username_slug, familyname),
        )
