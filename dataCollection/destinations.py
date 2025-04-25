from amadeus import Client, ResponseError

def search_destinations(keyword, country_code=None):
    amadeus = Client(
        client_id='nNLO5G7RCqJpv2vrkGiC59GddGRTFH0m',
        client_secret='F0Pfi1R7DG7VDORc'
    )

    try:
        # Build parameters dictionary
        params = {
            "keyword": keyword,
            "subType": ["CITY"]
        }
        
        # Only add countryCode if it's provided and valid (2 characters)
        if country_code and len(country_code) == 2:
            params["countryCode"] = country_code.upper()

        # Search for cities and airports
        response = amadeus.reference_data.locations.get(**params)
        return parse_destinations(response.data)
    except ResponseError as error:
        print(f"Error searching destinations: {error}")
        return {"error": str(error)}

def parse_destinations(data):
    destinations = {}
    destination_options = 0
    
    for item in data:
        # Only include items that have required fields
        if "name" in item and "iataCode" in item:
            dest = {
                "city": item.get("name", ""),
                "iataCode": item.get("iataCode", ""),
                "countryCode": item.get("address", {}).get("countryCode", ""),
                "type": item.get("subType", "").lower()
            }
            
            destinations[destination_options] = dest
            destination_options += 1

    return destinations
