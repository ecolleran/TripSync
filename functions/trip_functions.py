### IMPORTS ###
from flask import Flask, render_template, request, session, redirect, url_for, flash, jsonify, send_file
from login_required_wrapper import login_required
import hashlib
from sql_connection import get_connection
import cx_Oracle
import io
import dataCollection.flights as flights
from amadeus import ResponseError
from dataCollection import destinations

from werkzeug.utils import secure_filename
import os

### SQL SETUP ###
oracle_conn = get_connection()

### URL DEFINITIONS ###

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
        
        # Get trip information including group name, using Oracle's TO_CHAR for date formatting
        cursor.execute("""
            SELECT t.trip_id, t.trip_name, t.trip_description, t.trip_photo,
                   t.status, t.start_date, t.end_date, 
                   TO_CHAR(t.created_at, 'Month DD, YYYY') as created_at,
                   g.group_name, g.group_id, t.created_by,
                   TO_CHAR(t.start_date, 'Month DD, YYYY') as formatted_start_date,
                   TO_CHAR(t.end_date, 'Month DD, YYYY') as formatted_end_date,
                   TO_CHAR(t.start_date, 'YYYY-MM-DD HH24:MI:SS') as countdown_date
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
            
        trip = {
            'id': trip_data[0],
            'name': trip_data[1],
            'description': trip_data[2],
            'photo': trip_photo_b64,
            'status': trip_data[4],
            'start_date': trip_data[11],  # Using Oracle formatted date
            'end_date': trip_data[12],    # Using Oracle formatted date
            'created_at': trip_data[7],   # Using Oracle formatted date
            'group_name': trip_data[8],
            'group_id': trip_data[9],
            'created_by': trip_data[10],
            'countdown': trip_data[13] if trip_data[5] else None  # Using countdown formatted date
        }
        
        # Get trip participants (members of the group)
        cursor.execute("""
            SELECT u.user_id, u.first_name, u.last_name, u.profile_picture
            FROM users u
            JOIN group_members gm ON u.user_id = gm.user_id
            WHERE gm.group_id = :group_id
        """, {'group_id': trip_data[9]})
        
        participants = []
        for row in cursor.fetchall():
            profile_picture_b64 = None
            if row[3]:
                import base64
                photo_data = row[3].read()
                profile_picture_b64 = base64.b64encode(photo_data).decode('utf-8')
                
            participants.append({
                'id': row[0],
                'name': f"{row[1]} {row[2]}",
                'profile_picture': profile_picture_b64
            })
        
        return render_template('trip_details.html', 
                             trip=trip,
                             participants=participants)
                             
    except Exception as e:
        print(f"Error in trip_details: {str(e)}")
        flash(f'Error loading trip details: {str(e)}', 'error')
        return redirect(url_for('dashboard'))
    finally:
        cursor.close()


@login_required
def edit_trip(trip_id):
    """
    Edit trip details
    """
    try:
        cursor = oracle_conn.cursor()
        
        # First check if user has permission to edit this trip
        cursor.execute("""
            SELECT t.trip_id, t.trip_name, t.trip_description, t.trip_photo,
                   TO_CHAR(t.start_date, 'YYYY-MM-DD') as start_date,
                   TO_CHAR(t.end_date, 'YYYY-MM-DD') as end_date,
                   t.created_by
            FROM trips t
            WHERE t.trip_id = :trip_id
        """, {'trip_id': trip_id})
        
        trip_data = cursor.fetchone()
        if not trip_data:
            flash('Trip not found', 'error')
            return redirect(url_for('dashboard'))
            
        # Check if user is the trip creator
        if trip_data[6] != session['user_id']:
            flash('You do not have permission to edit this trip', 'error')
            return redirect(url_for('trip_details', trip_id=trip_id))
        
        if request.method == 'POST':
            trip_name = request.form.get('trip_name')
            trip_description = request.form.get('trip_description')
            start_date = request.form.get('start_date')
            end_date = request.form.get('end_date')
            
            # Handle photo upload
            trip_photo = None
            if 'trip_photo' in request.files and request.files['trip_photo'].filename:
                photo_file = request.files['trip_photo']
                if photo_file and allowed_file(photo_file.filename):
                    trip_photo = photo_file.read()
            
            # Update trip details
            if trip_photo:
                cursor.execute("""
                    UPDATE trips 
                    SET trip_name = :trip_name,
                        trip_description = :trip_description,
                        trip_photo = :trip_photo,
                        start_date = TO_DATE(:start_date, 'YYYY-MM-DD'),
                        end_date = TO_DATE(:end_date, 'YYYY-MM-DD')
                    WHERE trip_id = :trip_id
                """, {
                    'trip_name': trip_name,
                    'trip_description': trip_description,
                    'trip_photo': trip_photo,
                    'start_date': start_date,
                    'end_date': end_date,
                    'trip_id': trip_id
                })
            else:
                cursor.execute("""
                    UPDATE trips 
                    SET trip_name = :trip_name,
                        trip_description = :trip_description,
                        start_date = TO_DATE(:start_date, 'YYYY-MM-DD'),
                        end_date = TO_DATE(:end_date, 'YYYY-MM-DD')
                    WHERE trip_id = :trip_id
                """, {
                    'trip_name': trip_name,
                    'trip_description': trip_description,
                    'start_date': start_date,
                    'end_date': end_date,
                    'trip_id': trip_id
                })
            
            oracle_conn.commit()
            flash('Trip updated successfully', 'success')
            return redirect(url_for('trip_details', trip_id=trip_id))
        
        # For GET request, prepare trip data for the template
        trip = {
            'id': trip_data[0],
            'name': trip_data[1],
            'description': trip_data[2],
            'photo': None,
            'start_date': trip_data[4],
            'end_date': trip_data[5]
        }
        
        # Convert photo to base64 if it exists
        if trip_data[3]:
            import base64
            photo_data = trip_data[3].read()
            trip['photo'] = base64.b64encode(photo_data).decode('utf-8')
        
        return render_template('edit_trip.html', trip=trip)
        
    except Exception as e:
        print(f"Error in edit_trip: {str(e)}")
        flash(f'Error updating trip: {str(e)}', 'error')
        return redirect(url_for('trip_details', trip_id=trip_id))
    finally:
        cursor.close()

@login_required
def delete_trip(trip_id):
    """
    Delete a trip
    """
    try:
        cursor = oracle_conn.cursor()
        
        # Check if user has permission to delete this trip
        cursor.execute("""
            SELECT created_by
            FROM trips
            WHERE trip_id = :trip_id
        """, {'trip_id': trip_id})
        
        trip_data = cursor.fetchone()
        if not trip_data:
            flash('Trip not found', 'error')
            return redirect(url_for('dashboard'))
            
        # Check if user is the trip creator
        if trip_data[0] != session['user_id']:
            flash('You do not have permission to delete this trip', 'error')
            return redirect(url_for('trip_details', trip_id=trip_id))
        
        # Delete the trip
        cursor.execute("""
            DELETE FROM trips
            WHERE trip_id = :trip_id
        """, {'trip_id': trip_id})
        
        oracle_conn.commit()
        flash('Trip deleted successfully', 'success')
        return redirect(url_for('dashboard'))
        
    except Exception as e:
        print(f"Error in delete_trip: {str(e)}")
        flash(f'Error deleting trip: {str(e)}', 'error')
        return redirect(url_for('trip_details', trip_id=trip_id))
    finally:
        cursor.close()

@login_required
def search_flights():
    """
    Handle flight search requests
    """
    if request.method == 'POST':
        try:
            # Get form data from request
            origin = request.form.get('origin')
            destination = request.form.get('destination')
            depart_date = request.form.get('departDate')
            return_date = request.form.get('returnDate')
            
            print(f"Received search request - Origin: {origin}, Destination: {destination}, Departure: {depart_date}, Return: {return_date}")
            
            # Call the Amadeus API
            flight_data = flights.search_flights(
                originLocationCode=origin,
                destinationLocationCode=destination,
                departureDate=depart_date,
                returnDate=return_date if return_date else None
            )
            
            print("Amadeus API response received")
            
            # Parse the flight data
            parsed_flights = flights.parse_flights(flight_data)
            print(f"Found {len(parsed_flights)} flights")
            
            return jsonify({'flights': parsed_flights})
            
        except Exception as e:
            print(f"Error searching flights: {str(e)}")
            return jsonify({'error': str(e), 'flights': []}), 500
            
    return jsonify({'error': 'Invalid request method', 'flights': []}), 400


@login_required
def add_flight_to_trip():
    """Add a flight to a trip in the database"""
    try:
        data = request.get_json()
        trip_id = data.get('trip_id')
        flight_data = data.get('flight_data')

        if not trip_id or not flight_data:
            return jsonify({"success": False, "error": "Missing required data"}), 400

        cursor = oracle_conn.cursor()

        # Get the next trip_flight_number for this trip
        cursor.execute("""
            SELECT NVL(MAX(trip_flight_number), 0) + 1
            FROM flights
            WHERE trip_id = :trip_id
        """, {'trip_id': trip_id})
        trip_flight_number = cursor.fetchone()[0]

        # Process outbound segments
        outbound_segments = []
        return_segments = []
        
        # Separate segments into outbound and return
        for segment_num, segment in flight_data['segments'].items():
            if int(segment_num) <= flight_data['stops'] + 1:
                outbound_segments.append(segment)
            else:
                return_segments.append(segment)

        # Insert outbound segments
        for segment in outbound_segments:
            cursor.execute("SELECT flight_id.NEXTVAL FROM dual")
            flight_id = cursor.fetchone()[0]
            
            cursor.execute("""
                INSERT INTO flights (
                    flight_id, 
                    trip_id, 
                    trip_flight_number,
                    flight_number,
                    airline,
                    currency_code,
                    departure_airport,
                    arrival_airport,
                    departure_time,
                    arrival_time,
                    price,
                    votes,
                    booking_status,
                    sync_status,
                    added_by,
                    added_at
                ) VALUES (
                    :flight_id,
                    :trip_id,
                    :trip_flight_number,
                    :flight_number,
                    :airline,
                    :currency_code,
                    :departure_airport,
                    :arrival_airport,
                    TO_TIMESTAMP(:departure_time, 'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
                    TO_TIMESTAMP(:arrival_time, 'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
                    :price,
                    0,
                    'PENDING',
                    'PENDING',
                    :added_by,
                    CURRENT_TIMESTAMP
                )
            """, {
                'flight_id': flight_id,
                'trip_id': trip_id,
                'trip_flight_number': trip_flight_number,
                'flight_number': int(segment.get('flight_number', 0)),
                'airline': segment['airline'],
                'currency_code': flight_data.get('currency', 'USD'),
                'departure_airport': segment['departure_airport'],
                'arrival_airport': segment['arrival_airport'],
                'departure_time': segment['departure_time'],
                'arrival_time': segment['arrival_time'],
                'price': float(flight_data['price']) / (2 if return_segments else 1),  # Split price for round trips
                'added_by': session['user_id']
            })

        # Insert return segments if they exist
        if return_segments:
            trip_flight_number += 1
            for segment in return_segments:
                cursor.execute("SELECT flight_id.NEXTVAL FROM dual")
                flight_id = cursor.fetchone()[0]
                
                cursor.execute("""
                    INSERT INTO flights (
                        flight_id, 
                        trip_id, 
                        trip_flight_number,
                        flight_number,
                        airline,
                        currency_code,
                        departure_airport,
                        arrival_airport,
                        departure_time,
                        arrival_time,
                        price,
                        votes,
                        booking_status,
                        sync_status,
                        added_by,
                        added_at
                    ) VALUES (
                        :flight_id,
                        :trip_id,
                        :trip_flight_number,
                        :flight_number,
                        :airline,
                        :currency_code,
                        :departure_airport,
                        :arrival_airport,
                        TO_TIMESTAMP(:departure_time, 'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
                        TO_TIMESTAMP(:arrival_time, 'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
                        :price,
                        0,
                        'PENDING',
                        'PENDING',
                        :added_by,
                        CURRENT_TIMESTAMP
                    )
                """, {
                    'flight_id': flight_id,
                    'trip_id': trip_id,
                    'trip_flight_number': trip_flight_number,
                    'flight_number': int(segment.get('flight_number', 0)),
                    'airline': segment['airline'],
                    'currency_code': flight_data.get('currency', 'USD'),
                    'departure_airport': segment['departure_airport'],
                    'arrival_airport': segment['arrival_airport'],
                    'departure_time': segment['departure_time'],
                    'arrival_time': segment['arrival_time'],
                    'price': float(flight_data['price']) / 2,  # Split price for round trips
                    'added_by': session['user_id']
                })

        # Commit the transaction
        oracle_conn.commit()
        return jsonify({"success": True, "message": "Flight added successfully"})

    except Exception as e:
        oracle_conn.rollback()
        print(f"Error adding flight to trip: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

    finally:
        if 'cursor' in locals():
            cursor.close()

def add_destination_to_trip(trip_id, destination_data):
    try:
        # Get the next destination number for this trip
        cursor = oracle_con.cursor()
        cursor.execute("""
            SELECT MAX(destination_number)
            FROM destinations
            WHERE trip_id = :trip_id
        """, trip_id=trip_id)
        
        max_num = cursor.fetchone()[0]
        next_num = 1 if max_num is None else max_num + 1
        
        # Insert the new destination
        cursor.execute("""
            INSERT INTO destinations (
                trip_id,
                destination_number,
                destination_city,
                destination_country,
                votes,
                added_by,
                added_at
            ) VALUES (
                :trip_id,
                :destination_number,
                :destination_city,
                :destination_country,
                0,
                :added_by,
                CURRENT_TIMESTAMP
            )
        """, {
            'trip_id': trip_id,
            'destination_number': next_num,
            'destination_city': destination_data['city'],
            'destination_country': destination_data['countryCode'],
            'added_by': session.get('user_id')
        })
        
        oracle_conn.commit()
        return {"success": True}
        
    except Exception as e:
        print(f"Error adding destination: {e}")
        oracle_conn.rollback()
        return {"error": str(e)}

def add_destination_to_trip():
    """Handle adding a destination to a trip"""
    data = request.get_json()
    
    if not data or 'trip_id' not in data or 'destination_data' not in data:
        return jsonify({"error": "Missing required data"}), 400
        
    try:
        cursor = oracle_conn.cursor()
        
        # Get the next destination number for this trip
        cursor.execute("""
            SELECT MAX(destination_number)
            FROM destinations
            WHERE trip_id = :trip_id
        """, trip_id=data['trip_id'])
        
        max_num = cursor.fetchone()[0]
        next_num = 1 if max_num is None else max_num + 1
        
        # Insert the new destination
        cursor.execute("""
            INSERT INTO destinations (
                destination_id,
                trip_id,
                destination_number,
                destination_city,
                destination_country,
                votes,
                added_by,
                added_at
            ) VALUES (
                destination_id.NEXTVAL,
                :trip_id,
                :destination_number,
                :destination_city,
                :destination_country,
                0,
                :added_by,
                CURRENT_TIMESTAMP
            )
        """, {
            'trip_id': data['trip_id'],
            'destination_number': next_num,
            'destination_city': data['destination_data']['city'],
            'destination_country': data['destination_data']['countryCode'],
            'added_by': session.get('user_id')
        })
        
        oracle_conn.commit()
        return jsonify({"success": True})
        
    except cx_Oracle.Error as e:
        print(f"Database error: {e}")
        if 'connection' in locals():
            connection.rollback()
        return jsonify({"error": "Database error occurred"}), 500
    except Exception as e:
        print(f"Unexpected error: {e}")
        if 'connection' in locals():
            connection.rollback()
        return jsonify({"error": "An unexpected error occurred"}), 500
    finally:
        if 'connection' in locals():
            connection.close()








