from flask import Flask, render_template, request, session, redirect, url_for, flash
from functools import wraps
from flask_mysqldb import MySQL
import hashlib
import os

### FLASK SETUP ###

app = Flask(__name__)
app.secret_key='wearechefs'

### SQL SETUP ###
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = os.environ['SQL_PASS']
app.config['MYSQL_DB'] = 'culinarycanvas'

mysql = MySQL(app)


### FUNCTIONS ###
def get_connection():
    print("connected to sql")
    return mysql

def get_app():
    return app
