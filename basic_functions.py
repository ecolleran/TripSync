### IMPORTS ###
from flask import Flask, render_template, request, session, redirect, url_for, flash, jsonify
from login_required_wrapper import login_required
import hashlib
from sql_connection import get_connection

### SQL SETUP ###
mysql = get_connection()

### URL DEFINITIONS ###

@login_required
def logout():
    session.pop('logged_in', None)
    session.pop('username', None)
    session.pop('first_name', None)
    session.pop('id', None)
    session.pop('search_mode', None)

    flash('You were just logged out :(')
    return redirect(url_for('login'))


def welcome():
    return render_template('welcome.html')

@login_required
def home():
    if 'username' in session:
        username = session['username']
    else:
        username = "admin"

    # favorites table
    user = session['id']
    cursor = mysql.connection.cursor()
    cursor.execute("select distinct recipe_name, recipe_photo, clean_recipes.recipeID  from clean_recipes, favorites  where favorites.valid = 1 and clean_recipes.recipeID = favorites.recipeID and userID = %s", [user])
    recipes = cursor.fetchall()
 
    recipes = list(recipes)
    recipes.reverse()


    mysql.connection.commit()
    cursor.close()

    data = [session['first_name'], recipes]

    # return 
    return render_template('index.html', data=data)



def login():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        cursor = mysql.connection.cursor()
        cursor.execute("SELECT password FROM users WHERE username = %s", [username])
        result = cursor.fetchone()

        if result:
            hashpass = hashlib.md5(password.encode('utf-8')).hexdigest()
            if hashpass == result['password']:
                cursor.execute("SELECT first_name, active, id FROM users WHERE username = %s", [username])
                vals = cursor.fetchone()
                if vals['active'] == 1:
                    session['logged_in'] = True
                    session['username'] = username
                    session['id'] = vals['id']
                    session['first_name'] = vals['first_name']
                    flash('Logged in successfully!')
                    return redirect(url_for('dashboard'))
        error = 'Invalid credentials'
        cursor.close()

    return render_template('login.html', error=error)



def register():
    error = None
    if request.method == 'POST':
        # get info from user
        username   = request.form['username']
        password   = request.form['password']
        first_name = request.form['first_name']
        last_name  = request.form['last_name']

        # try to insert into database (hopefully throws an error if username already exists)
        cursor = mysql.connection.cursor()
        try:
            cursor.execute("INSERT INTO users(username, password, active, first_name, last_name) VALUES (%s, MD5(%s), %s, %s, %s)", [username, password, 1, first_name, last_name])
            mysql.connection.commit()
            flash('Account created!')
        #except:
        #error = 'Username already in use. Please use another username'
        except MySQLdb.IntegrityError as e:
            error = 'Username already in use. Please use another username'
            print(f"IntegrityError: {e}")
        except MySQLdb.Error as e:
            error = 'An error occurred. Please try again.'
            print(f"MySQLdb Error: {e}")
        except Exception as e:
            error = 'An unexpected error occurred. Please try again.'
            print(f"Unexpected Error: {e}")

        # close connection
        cursor.close()
    return render_template('register.html', error=error)

@login_required
def dashboard():
    print("Rendering dashboard for", session['username'])

    user_id = session['id']
    cursor = mysql.connection.cursor()

    cursor.execute("SELECT group_id, group_name FROM user_groups WHERE user_id = %s", [user_id])
    groups = cursor.fetchall()

    mysql.connection.commit()
    cursor.close()

    return render_template('dashboard.html', groups=groups, name=session['first_name'])

@login_required
def account():
    error = None
    if request.method == 'POST':
        password = request.form['password']
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT password FROM users WHERE username = %s", [session['username']])
        dbPass = cursor.fetchone()
        hashpass = hashlib.md5(password.encode('utf-8')).hexdigest()

        if hashpass == dbPass['password']:
            cursor.execute("UPDATE users SET active = 0 WHERE username = %s", [session['username']])
            mysql.connection.commit()
            cursor.close()
            session.clear()
            flash('Your account has been deleted.')
            return redirect(url_for('login'))

    return render_template('account.html', error=error)


@login_required
def explore_destinations():
    trips = []

    if request.method == 'POST':
        keyword = request.form['keyword']
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT destination_name, image_url, description, trip_id FROM trips WHERE destination_name LIKE %s", ['%' + keyword + '%'])
        trips = cursor.fetchall()
        mysql.connection.commit()
        cursor.close()

    return render_template('explore.html', trips=trips)

@login_required
def trip_details():
    trip_id = request.form['trip_id']

    cursor = mysql.connection.cursor()
    cursor.execute("SELECT destination_name, image_url, description FROM trips WHERE trip_id = %s", [trip_id])
    trip = cursor.fetchone()

    cursor.execute("SELECT step_number, detail FROM itinerary_steps WHERE trip_id = %s ORDER BY step_number", [trip_id])
    itinerary = cursor.fetchall()

    mysql.connection.commit()
    cursor.close()

    return render_template('trip_details.html', trip=trip, itinerary=itinerary)

@login_required
def generate_recommendations():
    name_list = request.form['name_list']
    trip_names = pull_data(name_list)  # reuse your UMAP logic
    coords, labels = embedd_and_umap(trip_names)
    graphJSON = plot(coords, labels)
    trip_data = graph_recipes(trip_names)

    return render_template('recommendations.html', graphJSON=graphJSON, data=trip_data)

@login_required
def group_details(id):
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT group_name FROM groups WHERE group_id = %s", [id])
    group = cursor.fetchone()

    cursor.execute("SELECT username FROM users JOIN user_groups ON users.id = user_groups.user_id WHERE group_id = %s", [id])
    members = cursor.fetchall()

    cursor.execute("SELECT trip_id, destination_name FROM trips WHERE group_id = %s", [id])
    trips = cursor.fetchall()

    mysql.connection.commit()
    cursor.close()

    return render_template('group_details.html', group=group, members=members, trips=trips)
