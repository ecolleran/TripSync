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
