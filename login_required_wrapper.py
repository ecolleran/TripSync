from flask import Flask, render_template, request, session, redirect, url_for, flash
from functools import wraps
import hashlib

### FUNCTIONS ###

# This function serves as a wrapper to require a login for some pages
def login_required(f):
    @wraps(f)
    def wrap(*args, **kwds):
        if 'logged_in' in session:
            return f(*args, **kwds)
        else:
            flash('You need to login first')
            return redirect(url_for('login'))
    return wrap
