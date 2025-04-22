from amadeus import Client, ResponseError

# Function to fetch flight data from Amadeus
def search_destinations(countryCode=None, keyword):
    amadeus = Client(
        client_id='nNLO5G7RCqJpv2vrkGiC59GddGRTFH0m',
        client_secret='F0Pfi1R7DG7VDORc'
    )

    params = {
        "keyword": keyword
    }

    if countryCode:
        params["countryCode"] = countryCode

    try:
        response = amadeus.shopping.flight_offers_search.get(**params)
        return response.data
    except ResponseError as error:
        print(error)


# Once flight data is fetched, parse data to what is needed for search page
def parse_destinations(data):

    destinations = {}

    destination_options = 0
    for i in data:
        if i["subType"] == "city":
            dest = {
                "city": i["name"]
                "iataCode": i["iataCode"],
                "countryCode": i["address"]["CountryCode"]   
            }

        destinations[destination_options] = dest
        destination_options += 1

    return destinations


