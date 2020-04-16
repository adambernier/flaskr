from flask import (
    Blueprint, current_app, flash, g, json, jsonify, redirect, 
    render_template, request, url_for
)

bp = Blueprint('landing', __name__)

@bp.route('/')
def index():
    return render_template('landing/index.html')
