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

