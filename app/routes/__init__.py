from flask import Blueprint, render_template

main = Blueprint('main', __name__)

from app.routes import api

@main.route('/')
def index():
    return render_template('index.html')
