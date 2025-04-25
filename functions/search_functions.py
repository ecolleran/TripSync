### IMPORTS ###
from flask import Flask, render_template, request, session, redirect, url_for, flash, jsonify, send_file
from login_required_wrapper import login_required
import hashlib
from sql_connection import get_connection
import cx_Oracle
import io
from dataCollection import destinations 

from werkzeug.utils import secure_filename
import os

### SQL SETUP ###
oracle_conn = get_connection()

### URL DEFINITIONS ###

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
def search_flights():
    """
    Handle flight search requests
    """
    if request.method == 'POST':
        try:
            # Get JSON data from request
            data = request.get_json()
            print("Received search request:", data)  # Debug print
            
            origin = data.get('origin')
            destination = data.get('destination')
            depart_date = data.get('departDate')
            return_date = data.get('returnDate')
            max_price = data.get('maxPrice')
            nonstop_only = data.get('nonstopOnly') == 'true'
     
            # Call the Amadeus API
            flight_data = flights.search_flights(
                originLocationCode=origin,
                destinationLocationCode=destination,
                departureDate=depart_date,
                returnDate=return_date if return_date else None,
                maxPrice=max_price if max_price else None,
                nonStop=nonstop_only
                 
            )
            
            print("Amadeus API response:", flight_data)  # Debug print
            
            # Parse the flight data
            parsed_flights = flights.parse_flights(flight_data)
            print("Parsed flights:", parsed_flights)  # Debug print
            
            return jsonify({'flights': parsed_flights})
            
        except Exception as e:
            print(f"Error searching flights: {str(e)}")  # Debug print
            return jsonify({'error': str(e)}), 500
            
    return jsonify({'error': 'Invalid request method'}), 400


def search_destinations_route():
    """Handle destination search requests"""
    keyword = request.form.get('keyword')
    country_code = request.form.get('countryCode')
    
    if not keyword:
        return jsonify({"error": "Keyword is required"}), 400
        
    try:
        results = destinations.search_destinations(keyword, country_code)
        
        if "error" in results:
            return jsonify({"error": results["error"]}), 500
            
        return jsonify({"destinations": results})
        
    except Exception as e:
        print(f"Unexpected error in search_destinations_route: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500
