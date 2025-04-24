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
def dashboard():
    cursor = oracle_conn.cursor()
    try:
        # Fetch user's groups with member count (existing code)
        cursor.execute("""
            SELECT g.group_id, g.group_name, g.group_description, 
                   CASE 
                       WHEN g.group_photo IS NOT NULL THEN g.group_photo 
                       ELSE NULL 
                   END as group_photo,
                   (SELECT COUNT(*) 
                    FROM group_members gm2 
                    WHERE gm2.group_id = g.group_id) as member_count
            FROM groups g
            JOIN group_members gm ON g.group_id = gm.group_id
            WHERE gm.user_id = :user_id
            ORDER BY g.created_at DESC
        """, {'user_id': session['user_id']})
        
        groups_raw = cursor.fetchall()
        
        # Process the groups to handle image data
        groups = []
        for group in groups_raw:
            group_data = list(group)
            if group[3]:  # If there's image data
                import base64
                # Convert BLOB to base64
                group_data[3] = base64.b64encode(group[3].read()).decode('utf-8')
            groups.append(group_data)

        # Fetch user's trips
        cursor.execute("""
            SELECT t.trip_id, t.trip_name, t.start_date, t.trip_photo,
                   g.group_name
            FROM trips t
            JOIN groups g ON t.group_id = g.group_id
            JOIN group_members gm ON g.group_id = gm.group_id
            WHERE gm.user_id = :user_id
            ORDER BY t.created_at DESC
        """, {'user_id': session['user_id']})

        trips = []
        for row in cursor.fetchall():
            trip_photo = None
            if row[3]:  # If there's a photo
                import base64
                trip_photo = base64.b64encode(row[3].read()).decode('utf-8')

            trips.append({
                'id': row[0],
                'destination': row[1],  # Using trip_name as destination
                'start_date': row[2],
                'photo': trip_photo,
                'group_name': row[4]
            })

	# New friends fetch
        cursor.execute("""
            SELECT u.user_id, u.username, u.first_name, u.last_name, u.profile_picture,
                   (SELECT COUNT(DISTINCT t.trip_id)
                    FROM trips t
                    JOIN group_members gm1 ON t.group_id = gm1.group_id
                    JOIN group_members gm2 ON t.group_id = gm2.group_id
                    WHERE gm1.user_id = :user_id
                    AND gm2.user_id = u.user_id) as trips_together
            FROM users u
            JOIN friends f ON (u.user_id = f.user2_id AND f.user1_id = :user_id)
                         OR (u.user_id = f.user1_id AND f.user2_id = :user_id)
            ORDER BY trips_together DESC
        """, {'user_id': session['user_id']})

        friends = []
        for row in cursor.fetchall():
            profile_picture = None
            if row[4]:  # If there's a profile picture
                import base64
                profile_picture = base64.b64encode(row[4].read()).decode('utf-8')

            friends.append({
                'id': row[0],
                'username': row[1],
                'full_name': f"{row[2]} {row[3]}",
                'profile_picture': profile_picture,
                'trips_together': row[5]
            })

        return render_template('dashboard.html', groups=groups, trips=trips, friends=friends)
        
    except Exception as e:
        print(f"Error in dashboard: {str(e)}")
        flash('Error loading dashboard', 'error')
        return render_template('dashboard.html', groups=[], trips=[])
    finally:
        cursor.close()

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


@login_required
def trip_search():
    """
    Render the trip search page with user's trips
    """
    cursor = oracle_conn.cursor()
    try:
        # Fetch all trips the user is associated with through their groups
        cursor.execute("""
            SELECT DISTINCT 
                t.trip_id,
                t.trip_name,
                t.trip_description,
                t.status,
                t.start_date,
                t.end_date,
                t.created_at,
                g.group_name,
                g.group_id,
                (SELECT COUNT(*)
                 FROM group_members gm2
                 WHERE gm2.group_id = g.group_id) as member_count
            FROM trips t
            JOIN groups g ON t.group_id = g.group_id
            JOIN group_members gm ON g.group_id = gm.group_id
            JOIN users u ON gm.user_id = u.user_id
            WHERE u.user_id = :user_id
            ORDER BY 
                CASE 
                    WHEN t.start_date IS NULL THEN t.created_at
                    ELSE t.start_date
                END DESC
        """, {'user_id': session['user_id']})
        
        trips = [{
            'id': row[0],
            'name': row[1],
            'description': row[2],
            'status': row[3],
            'start_date': row[4].strftime('%B %d, %Y') if row[4] else None,
            'end_date': row[5].strftime('%B %d, %Y') if row[5] else None,
            'created_at': row[6],
            'group_name': row[7],
            'group_id': row[8],
            'member_count': row[9],
            'display_name': f"{row[1]} ({row[7]})"
        } for row in cursor.fetchall()]
        
        return render_template('trip_search.html', trips=trips)
        
    except Exception as e:
        print(f"Error in trip_search: {str(e)}")
        flash('Error loading trips', 'error')
        return render_template('trip_search.html', trips=[])
    finally:
        cursor.close()


@login_required
def create_new_group():
    """
    Redirects to the create group page from dashboard
    This function is called when clicking the 'Create Group' button on dashboard
    """
    return render_template('create_group.html')

@login_required
def create_group():
    """
    Handle group creation functionality
    """
    print("Starting create_group function")  # Debug log
    
    if request.method == 'POST':
        print("Processing POST request")  # Debug log
        
        # Get form data
        group_name = request.form.get('group_name')
        group_description = request.form.get('group_description', '')  # Optional field
        created_by = session['user_id']
        
        print(f"Form data received - Name: {group_name}, Description: {group_description}")  # Debug log
        
        cursor = oracle_conn.cursor()
        try:
            # Get new group_id from sequence
            cursor.execute("SELECT group_id.NEXTVAL FROM DUAL")
            group_id = cursor.fetchone()[0]
            print(f"Generated group_id: {group_id}")  # Debug log
            
            # Handle photo upload
            photo_data = None
            if 'group_photo' in request.files:
                photo = request.files['group_photo']
                if photo and photo.filename != '':
                    photo_data = photo.read()
            
            if not photo_data:
                # Use default photo
                try:
                    with open('static/images/default-group.png', 'rb') as f:
                        photo_data = f.read()
                except FileNotFoundError:
                    # Create default group image directory if it doesn't exist
                    import os
                    os.makedirs('static/images', exist_ok=True)
                    
                    # Create a simple default image using PIL
                    from PIL import Image, ImageDraw
                    img = Image.new('RGB', (200, 200), color='#f8f9fa')
                    d = ImageDraw.Draw(img)
                    d.text((100, 100), "Group", fill='#495057', anchor="mm")
                    img.save('static/images/default-group.png')
                    
                    with open('static/images/default-group.png', 'rb') as f:
                        photo_data = f.read()

            # Insert into groups table
            cursor.execute("""
                INSERT INTO groups (
                    group_id,
                    group_name,
                    group_description,
                    group_photo,
                    created_by,
                    created_at
                ) VALUES (
                    :1, :2, :3, :4, :5, CURRENT_TIMESTAMP
                )
            """, (group_id, group_name, group_description, photo_data, created_by))
            
            print("Group inserted into database")  # Debug log
            
            # First get the next member_id from a sequence
            cursor.execute("SELECT member_id.NEXTVAL FROM DUAL")
            member_id = cursor.fetchone()[0]

            # Then insert into group_members with the correct structure
            cursor.execute("""
                INSERT INTO group_members (
                    member_id,
                    group_id,
                    user_id,
                    joined_at
                ) VALUES (
                    :1, :2, :3, CURRENT_TIMESTAMP
                )
            """, (member_id, group_id, created_by))
            
            print("Group member entry created")  # Debug log
            
            # Commit the transaction
            oracle_conn.commit()
            print("Transaction committed successfully")  # Debug log
            
            flash('Group created successfully!', 'success')
            return redirect(url_for('dashboard'))
            
        except Exception as e:
            oracle_conn.rollback()
            print(f"Error occurred: {str(e)}")  # Debug log
            flash(f'Error creating group: {str(e)}', 'error')
            return render_template('create_group.html')
            
        finally:
            cursor.close()
            
    # GET request
    return render_template('create_group.html')

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
        cursor.execute("SELECT friend_id.NEXTVAL FROM DUAL")
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


@login_required
def group_details(group_id):
    """
    Display group details page
    """
    try:
        cursor = oracle_conn.cursor()
        
        # Get group information
        cursor.execute("""
            SELECT g.group_id, g.group_name, g.group_description, g.group_photo
            FROM groups g
            WHERE g.group_id = :group_id
        """, {'group_id': group_id})
        
        group_data = cursor.fetchone()
        if not group_data:
            flash('Group not found', 'error')
            return redirect(url_for('dashboard'))
        
        # Convert group photo to base64 if it exists
        group_photo_b64 = None
        if group_data[3]:  # if group_photo exists
            import base64
            # Read the LOB object
            photo_data = group_data[3].read()
            group_photo_b64 = base64.b64encode(photo_data).decode('utf-8')
            
        group = {
            'id': group_data[0],
            'name': group_data[1],
            'description': group_data[2],
            'photo': group_photo_b64
        }
        
        # Get group trips
        cursor.execute("""
            SELECT t.trip_id, t.trip_name, t.start_date, t.end_date
            FROM trips t
            WHERE t.group_id = :group_id
            ORDER BY t.start_date DESC
        """, {'group_id': group_id})
        
        trips = [{
            'trip_id': row[0],
            'name': row[1],
            'start_date': row[2].strftime('%B %d, %Y') if row[2] else None,
            'end_date': row[3].strftime('%B %d, %Y') if row[3] else None,
            'image_url': url_for('static', filename='images/default-trip.png')
        } for row in cursor.fetchall()]
        
        # Get group members with their profile pictures
        cursor.execute("""
            SELECT u.user_id, u.first_name, u.last_name, u.profile_picture
            FROM users u
            JOIN group_members gm ON u.user_id = gm.user_id
            WHERE gm.group_id = :group_id
        """, {'group_id': group_id})
        
        members = []
        for row in cursor.fetchall():
            profile_picture_b64 = None
            if row[3]:  # if profile_picture exists
                import base64
                # Read the LOB object
                photo_data = row[3].read()
                profile_picture_b64 = base64.b64encode(photo_data).decode('utf-8')
                
            members.append({
                'id': row[0],
                'name': f"{row[1]} {row[2]}",
                'profile_picture': profile_picture_b64,
                'role': 'Member'
            })
        
        return render_template('group_details.html', 
                             group=group,
                             trips=trips,
                             members=members)
                             
    except Exception as e:
        print(f"Error in group_details: {str(e)}")  # Add this for debugging
        flash(f'Error loading group details: {str(e)}', 'error')
        return redirect(url_for('dashboard'))
    finally:
        cursor.close()




@login_required
def create_trip():
    """
    Handle trip creation functionality
    """
    print("Starting create_trip function")  # Debug log
    
    if request.method == 'POST':
        print("Processing POST request")  # Debug log
        
        # Get form data
        trip_name = request.form.get('trip_name')
        group_id = request.form.get('group_id')
        trip_description = request.form.get('trip_description', '')  # Optional field
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        created_by = session['user_id']
        
        print(f"Form data received - Name: {trip_name}, Group: {group_id}, Start: {start_date}, End: {end_date}")  # Debug log
        
        cursor = oracle_conn.cursor()
        try:
            # Get new trip_id from sequence
            cursor.execute("SELECT trip_id.NEXTVAL FROM DUAL")
            trip_id = cursor.fetchone()[0]
            print(f"Generated trip_id: {trip_id}")  # Debug log
            
            # Insert into trips table
            cursor.execute("""
                INSERT INTO trips (
                    trip_id,
                    trip_name,
                    trip_description,
                    start_date,
                    end_date,
                    created_by,
                    group_id,
                    created_at
                ) VALUES (
                    :1, :2, :3, TO_DATE(:4, 'YYYY-MM-DD'), TO_DATE(:5, 'YYYY-MM-DD'), :6, :7, CURRENT_TIMESTAMP
                )
            """, (trip_id, trip_name, trip_description, start_date, end_date, created_by, group_id))
            
            print("Trip inserted into database")  # Debug log
            
            # Commit the transaction
            oracle_conn.commit()
            print("Transaction committed successfully")  # Debug log
            
            flash('Trip created successfully!', 'success')
            return redirect(url_for('group_details', group_id=group_id))
            
        except Exception as e:
            oracle_conn.rollback()
            print(f"Error occurred: {str(e)}")  # Debug log
            flash(f'Error creating trip: {str(e)}', 'error')
            return render_template('create_trip.html')
            
        finally:
            cursor.close()
    
@login_required
def create_new_trip():
    """
    Redirects to the create trip page from dashboard
    This function is called when clicking the 'Create Trip' button on dashboard
    """

    group_id = request.args.get('group_id')

    # For GET request, fetch the groups the user is a member of
    cursor = oracle_conn.cursor()
    try:
        cursor.execute("""
            SELECT g.group_id, g.group_name
            FROM groups g
            JOIN group_members gm ON g.group_id = gm.group_id
            WHERE gm.user_id = :user_id
            ORDER BY g.group_name
        """, {'user_id': session['user_id']})
    
        groups = [{
            'group_id': row[0],
            'group_name': row[1]
        } for row in cursor.fetchall()]
    
        return render_template('create_trip.html', groups=groups, selected_group_id=group_id)
    
    except Exception as e:
        print(f"Error loading create trip page: {str(e)}")
        flash('Error loading create trip page', 'error')
        return redirect(url_for('dashboard'))
    finally:
        cursor.close()

@login_required
def trip_details(trip_id):
    """
    Display trip details page
    """
    try:
        cursor = oracle_conn.cursor()
        
        # Get trip information including group name
        cursor.execute("""
            SELECT t.trip_id, t.trip_name, t.trip_description, t.trip_photo,
                   t.status, t.start_date, t.end_date, t.created_at,
                   g.group_name, g.group_id
            FROM trips t
            JOIN groups g ON t.group_id = g.group_id
            WHERE t.trip_id = :trip_id
        """, {'trip_id': trip_id})
        
        trip_data = cursor.fetchone()
        if not trip_data:
            flash('Trip not found', 'error')
            return redirect(url_for('dashboard'))
        
        # Convert trip photo to base64 if it exists
        trip_photo_b64 = None
        if trip_data[3]:  # if trip_photo exists
            import base64
            # Read the LOB object
            photo_data = trip_data[3].read()
            trip_photo_b64 = base64.b64encode(photo_data).decode('utf-8')
        
        # Calculate countdown if start date exists
        countdown = None
        if trip_data[5]:  # if start_date exists
            from datetime import datetime
            today = datetime.now()
            start_date = trip_data[5]
            delta = start_date - today
            if delta.days > 0:
                countdown = f"{delta.days} days {delta.seconds // 3600} hours {(delta.seconds // 60) % 60} mins"
            elif delta.days == 0:
                countdown = f"{delta.seconds // 3600} hours {(delta.seconds // 60) % 60} mins"
            
        trip = {
            'id': trip_data[0],
            'name': trip_data[1],
            'description': trip_data[2],
            'photo': trip_photo_b64,
            'status': trip_data[4],
            'start_date': trip_data[5].strftime('%B %d, %Y') if trip_data[5] else None,
            'end_date': trip_data[6].strftime('%B %d, %Y') if trip_data[6] else None,
            'created_at': trip_data[7].strftime('%B %d, %Y'),
            'group_name': trip_data[8],
            'group_id': trip_data[9],
            'countdown': countdown
        }
        
        # Get trip participants (members of the group who are part of this trip)
        cursor.execute("""
            SELECT u.user_id, u.first_name, u.last_name, u.profile_picture
            FROM users u
            JOIN group_members gm ON u.user_id = gm.user_id
            WHERE gm.group_id = :group_id
        """, {'group_id': trip_data[9]})  # Using the group_id from trip data
        
        participants = []
        for row in cursor.fetchall():
            profile_picture_b64 = None
            if row[3]:  # if profile_picture exists
                import base64
                # Read the LOB object
                photo_data = row[3].read()
                profile_picture_b64 = base64.b64encode(photo_data).decode('utf-8')
                
            participants.append({
                'id': row[0],
                'name': f"{row[1]} {row[2]}",
                'profile_picture': profile_picture_b64
            })
        
        # Get flights associated with this trip
        cursor.execute("""
            SELECT f.flight_id, f.airline, f.flight_number, 
                   f.departure_time, f.arrival_time, f.price,
                   f.status
            FROM flights f
            WHERE f.trip_id = :trip_id
            GROUP BY f.flight_id, f.airline, f.flight_number, 
                     f.departure_time, f.arrival_time, f.price, f.status
            ORDER BY vote_count DESC
        """, {'trip_id': trip_id})
        
        flights = []
        final_flight = None
        
        for row in cursor.fetchall():
            flight = {
                'flight_id': row[0],
                'airline': row[1],
                'flight_number': row[2],
                'departure_time': row[3].strftime('%I:%M %p') if row[3] else None,
                'arrival_time': row[4].strftime('%I:%M %p') if row[4] else None,
                'price': row[5],
                'votes': row[6],
                'status': row[7]
            }
            
            if row[7] == 'CONFIRMED':
                final_flight = flight
            else:
                flights.append(flight)
        
        return render_template('trip_details.html', 
                             trip=trip,
                             participants=participants,
                             flights_to_vote=flights,
                             final_flight=final_flight)
                             
    except Exception as e:
        print(f"Error in trip_details: {str(e)}")
        flash(f'Error loading trip details: {str(e)}', 'error')
        return redirect(url_for('dashboard'))
    finally:
        cursor.close()

@login_required
def search_users_for_group():
    """
    Search for users to add to a group
    """
    query = request.args.get('query', '')
    group_id = request.args.get('group_id')
    
    if not query or not group_id:
        return jsonify({'users': []})
    
    cursor = oracle_conn.cursor()
    try:
        # Search for users that match the query and are not already in the group
        cursor.execute("""
            SELECT u.user_id, u.username, u.first_name || ' ' || u.last_name as full_name
            FROM users u
            WHERE (LOWER(u.username) LIKE LOWER(:query) 
                  OR LOWER(u.first_name || ' ' || u.last_name) LIKE LOWER(:query))
            AND u.user_id NOT IN (
                SELECT user_id 
                FROM group_members 
                WHERE group_id = :group_id
            )
            AND u.user_id != :current_user_id
            AND ROWNUM <= 5
        """, {
            'query': f'%{query}%',
            'group_id': group_id,
            'current_user_id': session['user_id']
        })
        
        users = [{
            'user_id': row[0],
            'username': row[1],
            'full_name': row[2]
        } for row in cursor.fetchall()]
        
        return jsonify({'users': users})
        
    except Exception as e:
        print(f"Error searching users: {str(e)}")
        return jsonify({'error': 'An error occurred while searching users'}), 500
    finally:
        cursor.close()

@login_required
def add_group_member():
    """
    Add a new member to a group
    """
    data = request.get_json()
    user_id = data.get('user_id')
    group_id = data.get('group_id')
    
    if not user_id or not group_id:
        return jsonify({'success': False, 'message': 'Missing required data'})
    
    cursor = oracle_conn.cursor()
    try:
        # Check if current user is the group creator (first member)
        cursor.execute("""
            SELECT user_id 
            FROM group_members 
            WHERE group_id = :group_id 
            ORDER BY joined_at ASC
            FETCH FIRST 1 ROW ONLY
        """, {'group_id': group_id})
        
        creator = cursor.fetchone()
        if not creator or creator[0] != session['user_id']:
            return jsonify({'success': False, 'message': 'You do not have permission to add members to this group'})
        
        # Check if user is already a member
        cursor.execute("""
            SELECT 1 FROM group_members 
            WHERE group_id = :group_id AND user_id = :user_id
        """, {'group_id': group_id, 'user_id': user_id})
        
        if cursor.fetchone():
            return jsonify({'success': False, 'message': 'User is already a member of this group'})
        
        # Get next member_id
        cursor.execute("SELECT NVL(MAX(member_id), 0) + 1 FROM group_members")
        member_id = cursor.fetchone()[0]
        
        # Add user to group
        cursor.execute("""
            INSERT INTO group_members (member_id, group_id, user_id, joined_at)
            VALUES (:member_id, :group_id, :user_id, CURRENT_TIMESTAMP)
        """, {
            'member_id': member_id,
            'group_id': group_id,
            'user_id': user_id
        })
        
        oracle_conn.commit()
        return jsonify({'success': True})
        
    except Exception as e:
        oracle_conn.rollback()
        print(f"Error adding group member: {str(e)}")
        return jsonify({'success': False, 'message': 'An error occurred while adding member'})
    finally:
        cursor.close()













