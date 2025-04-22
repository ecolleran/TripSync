from flask import Flask
from flask import render_template, request, session, redirect, url_for, flash
from functools import wraps
### IMPORTS ###
from basic_functions import *
from login_required_wrapper import login_required
import hashlib
from sql_connection import get_app
import basic_functions as bf


# Gets app from sql_connection
app = get_app()

### URL ROUTES ####
app.add_url_rule('/', view_func=bf.login, methods=['GET', 'POST'])  # Default = login
app.add_url_rule('/login', view_func=bf.login, methods=['GET', 'POST'])
app.add_url_rule('/register', view_func=bf.register, methods=['GET', 'POST'])
app.add_url_rule('/logout', view_func=bf.logout)

app.add_url_rule('/dashboard', view_func=bf.dashboard)
app.add_url_rule('/explore', view_func=bf.explore_destinations, methods=['GET', 'POST'])
app.add_url_rule('/trip_details', view_func=bf.trip_details, methods=['POST'])
app.add_url_rule('/recommendations', view_func=bf.generate_recommendations, methods=['POST'])
app.add_url_rule('/group/<int:id>', view_func=bf.group_details)
app.add_url_rule('/account', view_func=bf.account, methods=['GET', 'POST'])


### MAIN ###
if __name__ == '__main__':
    app.debug=True
    app.run()
    #app.run(host='db8.cse.nd.edu', port=5012)
