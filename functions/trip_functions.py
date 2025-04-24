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









