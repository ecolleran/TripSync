from amadeus import Client, ResponseError


# Function to fetch flight data from Amadeus
def search_flights(originLocationCode, destinationLocationCode, departureDate, returnDate=None, adults=1, children=0, infants=0, travelClass=None, includedAirlineCodes=None, excludedAirlineCodes=None, nonStop=False, currencyCode='USD', maxPrice=None):
    amadeus = Client(
        client_id='nNLO5G7RCqJpv2vrkGiC59GddGRTFH0m',
        client_secret='F0Pfi1R7DG7VDORc'
    )

    params = {
        "originLocationCode": originLocationCode,
        "destinationLocationCode": destinationLocationCode,
        "departureDate": departureDate,
        "adults": adults,
        "travelClass": travelClass,
        "currencyCode": currencyCode,
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
        response = amadeus.shopping.flight_offers_search.get(**params)
        return response.data
    except ResponseError as error:
        print(error)


# Once flight data is fetched, parse data to what is needed for search page
def parse_flights(data):

    flights = {}

    flight_options = 0
    for i in data:
        flight = {
            "id": i["id"],
            "oneWay": i["oneWay"],
            "numberofBookableSeats": i["numberofBookableSeats"],
            "duration": i["itineraries"][0]["duration"],
            "stops": len(i["itineraries"][0]["segments"]),
            "flights": {},
            "currency": i["price"]["currency"],
            "total": i["price"]["grandTotal"]
        }

        flight_num = 0
        for j in i["itineraries"][0]["segments"]:
            flight["flights"][flight_num] = {
                "departure_airport": j["departure"]["iataCode"],
                "departure_time": j["departure"]["at"],
                "arrival_airport": j["arrival"]["iataCode"],
                "arrival_time": j["arrival"]["at"],
                "airline": j["carrierCode"]
                "flight_number": j["number"]
                "duration": j["duration"]
            flight_num += 1

        flights[flight_options] = flight
        flight_options += 1

    return flights


