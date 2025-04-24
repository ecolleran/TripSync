from flask import Flask
from flask import render_template, request, session, redirect, url_for, flash
from functools import wraps
### IMPORTS ###
from basic_functions import *
from login_required_wrapper import login_required
import hashlib
from sql_connection import get_app
import basic_functions as bf
import functions.user_functions as uf
import functions.main_page_functions as mf
import functions.search_functions as sf
import functions.group_functions as gf
import functions.trip_functions as tf
import functions.friend_functions as ff
import logging

logging.basicConfig(level=logging.DEBUG)

# Gets app from sql_connection
app = get_app()

### URL ROUTES ####

app.add_url_rule('/', view_func=mf.landing)  # Default = landing page
app.add_url_rule('/register', view_func=uf.register, methods=['GET', 'POST'])
app.add_url_rule('/login', view_func=uf.login, methods=['GET', 'POST'])
app.add_url_rule('/logout', view_func=uf.logout)
app.add_url_rule('/settings', view_func=uf.settings, methods=['GET', 'POST'])
app.add_url_rule('/delete_account', view_func=uf.delete_account, methods=['POST'])
app.add_url_rule('/dashboard', view_func=mf.dashboard)
app.add_url_rule('/trip_search', view_func=sf.trip_search, methods=['GET', 'POST'])
app.add_url_rule('/create_group', view_func=gf.create_new_group, methods=['GET'])
app.add_url_rule('/dashboard', view_func=gf.create_group, methods=['GET', 'POST'])
app.add_url_rule('/create_trip', view_func=tf.create_new_trip, methods=['GET', 'POST'])
app.add_url_rule('/create_trip/submit', view_func=tf.create_trip, methods=['POST'])
#app.add_url_rule('/dashboard', view_func=tf.create_trip, methods=['GET', 'POST'])
app.add_url_rule('/search_users', view_func=ff.search_users, methods=['GET'])
app.add_url_rule('/add_friend', view_func=ff.add_friend, methods=['POST'])
app.add_url_rule('/group/<int:group_id>', view_func=gf.group_details, methods=['GET'])
app.add_url_rule('/trip/<int:trip_id>', view_func=tf.trip_details, methods=['GET'])
app.add_url_rule('/search_users_for_group', view_func=gf.search_users_for_group, methods=['GET'])
app.add_url_rule('/add_group_member', view_func=gf.add_group_member, methods=['POST'])








### MAIN ###
if __name__ == '__main__':
    app.debug=True
    app.run(host='172.22.132.66', port=8007, debug=True)
    #app.run(host='db8.cse.nd.edu', port=5012)
