from amadeus import Client, ResponseError

def search_accomodations(cityCode, radius=5, radiusUnit='MILE', chainCodes=None, amenities=None, ratings=None, hotelSource='ALL', adults=1, checkInDate, checkOutDate, countryofResidence='USA', roomQuantity=1, priceRange, currency='USD', paymentPolicy=None, boardType, includeClosed=False, bestRateOnly=True, lang='en'):
    amadeus = Client(
        client_id='nNLO5G7RCqJpv2vrkGiC59GddGRTFH0m',
        client_secret='F0Pfi1R7DG7VDORc'
    )

    params = {
        "cityCode": cityCode,
        "radius": radius,
        "radiusUnit": radiusUnit,
        "hotelSource": hotelSource        
    }

    if chainCodes:
        params["chainCodes"] = chainCodes
    if amenities:
        params["amenities"] = amenities
    if ratings:
        params["ratings"] = ratings

    try:
        response = amadeus.shopping.hotel_list.get(**params)
        hotels = []
        hotelIDs = []
        for hotel in response.data:
            hotelIds.append(hotel['hotelId'])
        return get_pricing(amadeus, hotelIds, adults, checkInDate, checkOutDate, countryOfResidence,roomQuantity, priceRange, currency, paymentPolicy, boardType, includeClosed, bestRateOnly, lang)
    except ResponseError as error:
        print(error)


def get_pricing(amadeus, hotelIds, adults, checkInDate, checkOutDate, countryOfResidence,roomQuantity, priceRange, currency, paymentPolicy, boardType, includeClosed, bestRateOnly, lang):
    params = {
        "hotelIds": hotelIds,
        "adults": adults,    
        "countryofResidence": countryofResidence
        "roomQuantity": roomQuantity
        "currency": currency
        "includeClosed": includeClosed
        "bestRateOnly": bestRateOnly
        "lang": lang
    }

    if checkInDate:
        params["checkInDate"] = checkInDate
    if checkOutDate:
        params["checkOutDate"] = checkOutDate
    if priceRange:
        params["priceRange"] = priceRange
    if paymentPolicy:
        params["paymentPolicy"] = paymentPolicy
    if boardType:
        params["boardType"]: = boardType
    

    try:
        response = amadeus.shopping.hotel_offers.get(**params)
        return response.data
    except ResponseError as error:
        print(error)

def parse_accomodations(data):
     
    hotels = {}

    hotel_num = 0

    for i in data:
        hotel = {
            "accomodation_name": i["hotel"]["name"],
            "accomodation_type": i["hotel"]["type"],
            "city": i["hotel"]["cityCode"],
            "offers": {}
        }
        offer_num = 0
        for j in i["offers"]:
            offer = {
                "check_in_date": j["checkInDate"],
                "check_out_date": j["checkOutDate"],
                "beds": j["room"]["typeEstimated"]["beds"],
                "bed_type": j["room"]["typeEstimated"]["bedType"],
                "adults": j[0]["guests"]["adults"]
                "price": j["price"]["total"]
                "currency": j["price"]["currency"]
            }
            hotel["offers"][offer_num] = offer
            offer_num += 1

        hotels[hotel_num] = hotel
        hotel_num += 1
        
        

