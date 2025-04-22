from amadeus import Client, ResponseError
import math

# Function to fetch flight data from Amadeus
def search_activities(countryCode, keyword, maxx, radius):
    amadeus = Client(
        client_id='nNLO5G7RCqJpv2vrkGiC59GddGRTFH0m',
        client_secret='F0Pfi1R7DG7VDORc'
    )

    city = city_search(amadeus, countryCode, keyword, maxx)
    long = city["geoCode"]["longitude"]
    lat = city["geoCode"]["latitude"]
    
    d_lat = radius/69.0
    d_long = radius / (math.cos(math.radians(lat)) * 69.0)

    params = {
        "north": lat+d_lat,
        "west": long-d_long,
        "south": lat-d_lat,
        "east": long+d_long
    }

    try:
        response = amadeus.shopping.activities.get(**params)
        return response.data
    except ResponseError as error:
        print(error)

def city_search(amadeus, countryCode=None, keyword, maxx=None):
    params = {
        "keyword": keyword,
        "include": None
    }
    
    if countryCode:
        params["countryCode"] = countryCode
    if maxx:
        params["max"] = maxx

    try:
        response = amadeus.locations.city_search.get(**params)
        return response.data
    except ResponseError as error:
        print(error)
        


# Once flight data is fetched, parse data to what is needed for search page
def parse_activities(data):

    activities = {}

    activity_options = 0
    for i in data:
        activity = {
            "type": i["type"],
            "name": i["name"],
            "description": i["shortDescription"],
            "rating": i["rating"]
            "bookingLink": i["bookingLink"],
            "currency": i["price"]["currencyCode"],
            "price": i["price"]["amount"]
            "pictures": {}
        }

        pic_num = 0
        for j in i["pictures"]:
            activity["pictures"][pic_num] = j
            pic_num += 1
        activities[activity_options] = activity
        activity_options += 1

    return activities


