import requests

def find_restaurants(location, radius=10, categories=None, language_code='en', country_code=None, price=None, open_now=None, open_at=None, attributes=None, sort_by=None, device_platform=None, reservation_date=None, reservation_time=None, reservation_covers=None, limit=20, offset=None):
    API_KEY = "FLJRZN1d9udwu9xqxZS_YDzGrkyva59c3_HZKWqhOBWSSMasYVU6DhG4P-yRsb3DZVMsv226RCMVKMBNilzieXwUgGDtDPt1c_aRuwqs1DA6L6b7hpdqpq2A_nj-Z3Yx"

    headers = {
        "Authorization": f"Bearer {API_KEY}"
    }

    params = {
        "term": "restaurants",
        "location": location,
        "radius": radius*1609
        "limit": limit
    }

    if categories:
        params["categories"] = categories
    if country_code:
        params["locale"] = f"{language_code}_{country_code}"
    if price:
        params["price"] = price
    if open_now:
        params["open_now"] = open_now
    if open_at:
        params["open_at"] = open_at
    if attributes:
        params["attributes"] = attributes
    if sort_by:
        params["sort_by"] = sort_by
    if device_platform:
        params["device_platform"] = device_platform
    if reservation_date:
        params["reservation_date"] = reservation_date
    if reservation_time:
        params["reservation_time"] = reservation_time
    if reservation_covers:
        params["reservation_covers"] = reservation_covers
    if matches_party_size_param:
        params["matches_party_size_param"] = matches_party_size_param
    if offset:
        params["offset"] = offset

    response = requests.get("https://api.yelp.com/v3/businesses/search", headers=headers, params=params)
    
    return response.json()
