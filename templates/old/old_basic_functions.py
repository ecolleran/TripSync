### IMPORTS ###
from flask import Flask, render_template, request, session, redirect, url_for, flash, jsonify
from login_required_wrapper import login_required
import hashlib
from sql_connection import get_connection
import cx_Oracle

from werkzeug.utils import secure_filename
import os

### SQL SETUP ###
oracle_conn = get_connection()

### URL DEFINITIONS ###

@login_required
def logout():
    session.pop('logged_in', None)
    session.pop('username', None)
    session.pop('first_name', None)
    session.pop('user_id', None)
    session.pop('search_mode', None)

    flash('You were just logged out :(')
    return redirect(url_for('login'))


def login():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        cursor = oracle_conn.cursor()
        cursor.execute("SELECT password FROM users WHERE username = :username", {'username': username})
        result = cursor.fetchone()

        if result:
            hashpass = hashlib.md5(password.encode('utf-8')).hexdigest()
            if hashpass == result[0]:
                cursor.execute("SELECT first_name, active, user_id FROM users WHERE username = :username", {'username': username})
                vals = cursor.fetchone()
                if vals[1] == 1:
                    session['logged_in'] = True
                    session['username'] = username
                    session['user_id'] = vals[2]
                    session['first_name'] = vals[0]
                    flash('Logged in successfully!')
                    return redirect(url_for('dashboard'))
        error = 'Invalid credentials'
        cursor.close()

    return render_template('login.html', error=error)



def register():
    error = None
    if request.method == 'POST':
        # get info from user
        username   = request.form['username'].strip()
        password   = request.form['password'].strip()
        first_name = request.form['first_name'].strip()
        last_name  = request.form['last_name'].strip()
        email = request.form['email'].strip()
        repeat_password = request.form['repeatPassword'].strip()
        active = 1

        try:
            with open('static/images/default-profile.png', 'rb') as file:
                default_profile_pic = file.read()
        except FileNotFoundError:
            error = 'Default profile picture not found'
            return render_template('register.html', error=error)

	# Validate input
        if not all([username, first_name, last_name, email, password]):
            error = 'All fields are required'
            return render_template('register.html', error=error)

        # Validate email format
        import re
        email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
        if not email_pattern.match(email):
            error = 'Please enter a valid email address'
            return render_template('register.html', error=error)

        # Validate username length
        if len(username) > 30:
            error = 'Username must be less than 30 characters'
            return render_template('register.html', error=error)

        # Validate passwords match
        if password != repeat_password:
            error = 'Passwords do not match'
            return render_template('register.html', error=error)

        # Check if username already exists
        cursor = oracle_conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users WHERE username = :username", {'username': username})
        result = cursor.fetchone()

        if result[0] > 0:
            error = 'Username already exists. Please choose another username.'
            cursor.close()
            return render_template('register.html', error=error)

        # Get current timestamp for date_joined
        from datetime import datetime
        date_joined = datetime.now()

        # try to insert into database (hopefully throws an error if username already exists)
        cursor = oracle_conn.cursor()
        try:
            cursor.execute("SELECT user_seq.NEXTVAL FROM DUAL")
            user_id = cursor.fetchone()[0]
            cursor.execute("""
                INSERT INTO users 
                (user_id, username, first_name, last_name, active, email, date_joined, password, profile_picture) 
                VALUES (:user_id, :username, :first_name, :last_name, :active, :email, :date_joined, :password, :default_profile_pic)
            """, {
                'user_id': user_id,
                'username': username,
                'first_name': first_name,
                'last_name': last_name,
                'active': active,
                'email': email,
                'date_joined': date_joined,
                'password': hashlib.md5(password.encode('utf-8')).hexdigest(),  # hashing password before insertion
                'default_profile_pic': default_profile_pic
            }) 
            oracle_conn.commit()
            flash('Account created successfully! Please sign in.')
            return redirect(url_for('login'))

        except oracle_conn.DatabaseError as e:
            error = f"An error occurred while creating your account. Please try again. {e} {e.args}"
            print(f"DatabaseError: {e}")
            print("Error details:", e.args)
        except Exception as e:
            error = 'An unexpected error occurred. Please try again.'
            print(f"Unexpected Error: {e}")
        finally:
            cursor.close()

    return render_template('register.html', error=error)

@login_required
def dashboard():
    cursor = oracle_conn.cursor()
    
    # Fetch user's groups
    cursor.execute("""
        SELECT g.group_id, g.group_name, g.group_photo, g.group_description,
        (SELECT COUNT(*) FROM group_members WHERE group_members.group_id = g.group_id) as member_count
        FROM groups g
        JOIN group_members gm ON g.group_id = gm.group_id
        WHERE gm.user_id = :user_id
        ORDER BY g.created_at DESC
    """, {'user_id': session['user_id']})
    groups = cursor.fetchall()
    
    # Your existing dashboard queries...
    
    cursor.close()
    return render_template('dashboard.html', groups=groups)

@login_required
def account():
    error = None
    if request.method == 'POST':
        password = request.form['password']
        cursor = oracle_conn.cursor()
        cursor.execute("SELECT password FROM users WHERE username = :username", {'username': session['username']})
        dbPass = cursor.fetchone()
        hashpass = hashlib.md5(password.encode('utf-8')).hexdigest()

        if hashpass == dbPass['password']:
            cursor.execute("UPDATE users SET active = 0 WHERE username = :username", {'username': session['username']})
            oracle_conn.commit()
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
        cursor = oracle_conn.cursor()
        cursor.execute("SELECT destination_name, image_url, description, trip_id FROM trips WHERE destination_name LIKE %s", ['%' + keyword + '%'])
        trips = cursor.fetchall()
        oracle_conn.commit()
        cursor.close()

    return render_template('explore.html', trips=trips)

@login_required
def trip_details():
    trip_id = request.form['trip_id']

    cursor = oracle_conn.cursor()
    cursor.execute("SELECT destination_name, image_url, description FROM trips WHERE trip_id = %s", [trip_id])
    trip = cursor.fetchone()

    cursor.execute("SELECT step_number, detail FROM itinerary_steps WHERE trip_id = %s ORDER BY step_number", [trip_id])
    itinerary = cursor.fetchall()

    oracle_conn.commit()
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
    cursor = oracle_conn.cursor()
    cursor.execute("SELECT group_name FROM groups WHERE group_id = %s", [id])
    group = cursor.fetchone()

    cursor.execute("SELECT username FROM users JOIN user_groups ON users.id = user_groups.user_id WHERE group_id = %s", [id])
    members = cursor.fetchall()

    cursor.execute("SELECT trip_id, destination_name FROM trips WHERE group_id = %s", [id])
    trips = cursor.fetchall()

    oracle_conn.commit()
    cursor.close()

    return render_template('group_details.html', group=group, members=members, trips=trips)









def landing():
    """Landing page route"""
    return render_template('landing.html')



@login_required
def settings():
    error = None
    success = None
    
    # Get current user info
    cursor = oracle_conn.cursor()
    cursor.execute("""
        SELECT first_name, last_name, email
        FROM users 
        WHERE user_id = :user_id
    """, {'user_id': session['user_id']})
    user = cursor.fetchone()
    
    if request.method == 'POST':
        try:
            # Get form data
            first_name = request.form['first_name']
            last_name = request.form['last_name']
            email = request.form['email']
            new_password = request.form['new_password']
            confirm_password = request.form['confirm_password']
            
            # Handle profile picture upload
            if 'profile_picture' in request.files:
                file = request.files['profile_picture']
                if file and file.filename != '':
                    # Save the file
                    filename = secure_filename(file.filename)
                    file_path = os.path.join('./static/images/profiles/', f'user_{session["user_id"]}_{filename}')
                    file.save(file_path)
                    session['profile_picture'] = '/' + file_path

            # Update user info
            if first_name:
                cursor.execute(
                    "UPDATE users SET first_name = :first_name WHERE user_id = :user_id",
                    {'first_name': first_name, 'user_id': session['user_id']}
                )
            else:
                first_name = session['first_name']
            
            if last_name:
                cursor.execute(
                    "UPDATE users SET last_name = :last_name WHERE user_id = :user_id",
                    {'last_name': last_name, 'user_id': session['user_id']}
                )
            
            if email:
                cursor.execute(
                    "UPDATE users SET email = :email WHERE user_id = :user_id",
                    {'email': email, 'user_id': session['user_id']}
                )
            
            # Update password if provided
            if new_password:
                if new_password != confirm_password:
                    error = "Passwords do not match"
                else:
                    cursor.execute(
                        "UPDATE users SET password = :new_password WHERE user_id = :user_id",
                        {'new_password': hashlib.md5(new_password.encode('utf-8')).hexdigest(), 'user_id': session['user_id']}
                    )
            
            oracle_conn.commit()
            
            # Update session
            session['first_name'] = first_name
            
            success = "Settings updated successfully!"
            
        except Exception as e:
            error = f"An error occurred: {str(e)}"
            oracle_conn.rollback()
        finally:
            cursor.close()
            
        return render_template('settings.html', user=user, error=error, success=success)
    
    return render_template('settings.html', user=user)

@login_required
def delete_account():
    try:
        cursor = oracle_conn.cursor()
        cursor.execute("DELETE FROM users WHERE user_id = :user_id", {'user_id': session['user_id']})
        oracle_conn.commit()
        session.clear()
        flash("Your account has been deleted successfully.")
        return redirect(url_for('login'))
    except Exception as e:
        flash(f"An error occurred while deleting your account: {str(e)}")
        return redirect(url_for('settings'))


@login_required
def trip_search():
    """
    Render the trip search page
    """
    cursor = oracle_conn.cursor()
    try:
        # You can add any initial data loading here if needed
        # For example, loading popular destinations or recent searches
        
        if request.method == 'POST':
            location = request.form.get('location')
            dates_start = request.form.get('dates_start')
            dates_end = request.form.get('dates_end')
            
            # Example query - modify according to your database schema
            cursor.execute("""
                SELECT destination_name, description, image_url, destination_type, rating 
                FROM destinations 
                WHERE LOWER(destination_name) LIKE LOWER(:location)
            """, {'location': f'%{location}%'})
            
            destinations = [{
                'name': row[0],
                'description': row[1],
                'image_url': row[2],
                'type': row[3],
                'rating': row[4]
            } for row in cursor.fetchall()]
            
            return render_template('trip_search.html', destinations=destinations)
            
        return render_template('trip_search.html')
        
    except Exception as e:
        flash(f'An error occurred: {str(e)}', 'error')
        return redirect(url_for('dashboard'))
    finally:
        cursor.close()


@login_required
def create_new_group():
    """
    Redirects to the create group page from dashboard
    This function is called when clicking the 'Create Group' button on dashboard
    """
    return redirect(url_for('create_new_group'))


@login_required
def create_new_trip():
    """
    Redirects to the create trip page from dashboard
    This function is called when clicking the 'Create Trip' button on dashboard
    """
    return redirect(url_for('create_new_trip'))

@login_required
def search_users():
    """
    Search for users by username
    """
    query = request.args.get('query', '').strip()
    
    if not query:
        return jsonify({'users': []})
    
    try:
        cursor = oracle_conn.cursor()
        # Search for users excluding the current user
        cursor.execute("""
            SELECT user_id, username, first_name, last_name 
            FROM users 
            WHERE LOWER(username) LIKE LOWER(:query) 
            AND user_id != :current_user_id
            AND active = 1
            AND user_id NOT IN (
                SELECT user2_id 
                FROM friends 
                WHERE user1_id = :current_user_id
                UNION
                SELECT user1_id 
                FROM friends 
                WHERE user2_id = :current_user_id
            )
        """, {
            'query': f'%{query}%',
            'current_user_id': session['user_id']
        })
        
        users = [{
            'user_id': row[0],
            'username': row[1],
            'full_name': f"{row[2]} {row[3]}"
        } for row in cursor.fetchall()]
        
        return jsonify({'users': users})
        
    except Exception as e:
        print(f"Error in search_users: {str(e)}")
        return jsonify({'error': 'An error occurred while searching users'}), 500
    finally:
        cursor.close()

@login_required
def add_friend():
    """
    Add a new friend relationship
    """
    try:
        data = request.get_json()
        friend_id = data.get('friend_id')
        
        if not friend_id:
            return jsonify({'success': False, 'message': 'Friend ID is required'}), 400
            
        cursor = oracle_conn.cursor()
        
        # Check if friendship already exists
        cursor.execute("""
            SELECT COUNT(*) FROM friends 
            WHERE (user1_id = :user1_id AND user2_id = :user2_id)
            OR (user1_id = :user2_id AND user2_id = :user1_id)
        """, {
            'user1_id': session['user_id'],
            'user2_id': friend_id
        })
        
        if cursor.fetchone()[0] > 0:
            return jsonify({'success': False, 'message': 'Already friends'}), 400
            
        # Get new friend_id from sequence
        cursor.execute("SELECT friend_seq.NEXTVAL FROM DUAL")
        new_friend_id = cursor.fetchone()[0]
        
        # Add friendship
        cursor.execute("""
            INSERT INTO friends (friend_id, user1_id, user2_id, created_at)
            VALUES (:friend_id, :user1_id, :user2_id, CURRENT_TIMESTAMP)
        """, {
            'friend_id': new_friend_id,
            'user1_id': session['user_id'],
            'user2_id': friend_id
        })
        
        oracle_conn.commit()
        return jsonify({'success': True, 'message': 'Friend added successfully'})
        
    except Exception as e:
        oracle_conn.rollback()
        print(f"Error in add_friend: {str(e)}")
        return jsonify({'success': False, 'message': 'An error occurred while adding friend'}), 500
    finally:
        cursor.close()
















