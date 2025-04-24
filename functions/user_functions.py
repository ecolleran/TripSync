### IMPORTS ###
from flask import Flask, render_template, request, session, redirect, url_for, flash, jsonify, send_file
from login_required_wrapper import login_required
import hashlib
from sql_connection import get_connection
import cx_Oracle
import io

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
        try:
            cursor.execute("""
                SELECT u.password, u.first_name, u.active, u.user_id, u.profile_picture 
                FROM users u 
                WHERE u.username = :username
            """, {'username': username})
            
            result = cursor.fetchone()
            if result:
                hashpass = hashlib.md5(password.encode('utf-8')).hexdigest()
                if hashpass == result[0] and result[2] == 1:  # Check password and active status
                    session['logged_in'] = True
                    session['username'] = username
                    session['user_id'] = result[3]
                    session['first_name'] = result[1]
                    
                    # Handle profile picture
                    if result[4] is not None:
                        try:
                            # Convert hex string to bytes and then to base64
                            import binascii
                            import base64
                            # Remove any whitespace and newlines from the hex string
                            hex_string = ''.join(result[4].split())
                            # Convert hex to bytes
                            profile_pic_bytes = binascii.unhexlify(hex_string)
                            # Convert bytes to base64
                            session['profile_picture'] = base64.b64encode(profile_pic_bytes).decode('utf-8')
                        except Exception as e:
                            print(f"Error processing profile picture: {str(e)}")
                            session['profile_picture'] = None
                    else:
                        session['profile_picture'] = None
                    
                    flash('Logged in successfully!', 'success')
                    return redirect(url_for('dashboard'))
                    
            error = 'Invalid credentials'
            
        except Exception as e:
            print(f"Error in login: {str(e)}")
            error = 'An error occurred during login'
        finally:
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
            cursor.execute("SELECT user_id.NEXTVAL FROM DUAL")
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
                    # Read the file data
                    file_data = file.read()
                    
                    # Convert to base64 for display
                    import base64
                    profile_picture_b64 = base64.b64encode(file_data).decode('utf-8')
                    
                    # Update profile picture in database
                    cursor.execute("""
                        UPDATE users 
                        SET profile_picture = :profile_picture 
                        WHERE user_id = :user_id
                    """, {
                        'profile_picture': file_data,
                        'user_id': session['user_id']
                    }) 

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
