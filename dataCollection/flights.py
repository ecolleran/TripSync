from amadeus import Client, ResponseError
from collections import defaultdict

def search_flights(originLocationCode, destinationLocationCode, departureDate, returnDate=None, adults=1, children=0, infants=0, travelClass='ECONOMY', includedAirlineCodes=None, excludedAirlineCodes=None, nonStop=None, currencyCode='USD', maxPrice=None):
    amadeus = Client(
        client_id='nNLO5G7RCqJpv2vrkGiC59GddGRTFH0m',
        client_secret='F0Pfi1R7DG7VDORc'
    )

    params = {
        "originLocationCode": originLocationCode,
        "destinationLocationCode": destinationLocationCode,
        "departureDate": departureDate,
        "adults": adults,
        "currencyCode": currencyCode,
        "travelClass": travelClass
    }

    if returnDate:
        params["returnDate"] = returnDate
    if children:
        params["children"] = children
    if infants:
        params["infants"] = infants
    if includedAirlineCodes:
        params["includedAirlineCodes"] = includedAirlineCodes
    if excludedAirlineCodes:
        params["excludedAirlineCodes"] = excludedAirlineCodes
    if nonStop is not None:
        params["nonStop"] = nonStop
    if maxPrice:
        params["maxPrice"] = maxPrice    

    try:
        print("Sending request to Amadeus with params:", params)  # Debug print
        response = amadeus.shopping.flight_offers_search.get(**params)
        return response.data
    except ResponseError as error:
        print(f"Amadeus API error: {error.code} - {error.description}")  # Debug print
        return []

def parse_flights(data):
    if not data:  # Handle case where data is None or empty
        return []
        
    flights = []
    
    for i in data:
        try:
            # Initialize flight dictionary with common data
            flight = {
                "id": i["id"],
                "oneWay": i["oneWay"],
                "numberofBookableSeats": i.get("numberofBookableSeats", None),
                "price": i["price"]["grandTotal"],
                "currency": i["price"]["currency"],
                "segments": {}
            }

            total_stops = 0
            total_duration = "PT0H"  # Initialize with zero duration
            segment_num = 1

            # Process all itineraries (outbound and return if exists)
            for itinerary in i["itineraries"]:
                # Add segments for this itinerary
                for segment in itinerary["segments"]:
                    s = {
                        "duration": segment["duration"],
                        "departure_airport": segment["departure"]["iataCode"],
                        "departure_time": segment["departure"]["at"],
                        "arrival_airport": segment["arrival"]["iataCode"],
                        "arrival_time": segment["arrival"]["at"],
                        "airline": segment["carrierCode"],
                        "flight_number": segment["number"]
                    }
                    flight["segments"][segment_num] = s
                    segment_num += 1
                
                # Add to total stops and duration
                total_stops += len(itinerary["segments"]) - 1
                # Add duration (you might want to implement proper duration addition)
                total_duration = itinerary["duration"]  # This is simplified, might need proper duration addition

            # Set the main flight details using the first and last segments
            first_segment = i["itineraries"][0]["segments"][0]
            last_segment_outbound = i["itineraries"][0]["segments"][-1]
            
            flight.update({
                "duration": total_duration,
                "stops": total_stops,
                "departure_airport": first_segment["departure"]["iataCode"],
                "departure_time": first_segment["departure"]["at"],
                "arrival_airport": last_segment_outbound["arrival"]["iataCode"],
                "arrival_time": last_segment_outbound["arrival"]["at"],
                "airline": first_segment["carrierCode"]
            })

            # If there's a return flight, add return journey details
            if len(i["itineraries"]) > 1:
                first_segment_return = i["itineraries"][1]["segments"][0]
                last_segment_return = i["itineraries"][1]["segments"][-1]
                
                flight.update({
                    "return_departure_airport": first_segment_return["departure"]["iataCode"],
                    "return_departure_time": first_segment_return["departure"]["at"],
                    "return_arrival_airport": last_segment_return["arrival"]["iataCode"],
                    "return_arrival_time": last_segment_return["arrival"]["at"],
                    "return_airline": first_segment_return["carrierCode"],
                    "is_round_trip": True
                })
            else:
                flight["is_round_trip"] = False

            flights.append(flight)
        except (KeyError, IndexError) as e:
            print(f"Error parsing flight data: {e}")
            continue
    
    return flights
