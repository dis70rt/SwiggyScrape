import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from django.shortcuts import render
from .scraper import SwiggyScrape, Restaurant

def fetch_restaurant_data(restaurant_id):
    try:
        restaurant = Restaurant(restaurant_id)
        data = restaurant.get()
    except Exception as e:
        data = None
    return data

def home(request):
    query = request.GET.get('q', '')
    restaurant_details = []
    error_message = None

    # Metrics variables
    total_open = 0
    total_closed = 0
    all_ratings = []
    fastest_delivery = 999

    if query:
        swiggy = SwiggyScrape()
        try:
            restaurants = swiggy.getResturants(query)
        except Exception as e:
            error_message = f"Failed to fetch restaurants: {str(e)}"
            restaurants = []
        if restaurants:
            # Use ThreadPoolExecutor to fetch data concurrently
            with ThreadPoolExecutor(max_workers=16) as executor:
                future_to_rest = {
                    executor.submit(fetch_restaurant_data, rest["id"]): rest["id"]
                    for rest in restaurants
                }
                for future in as_completed(future_to_rest):
                    data = future.result()
                    if data and data.get("info",{"deliveryTime":999}):
                        info = data["info"]

                        # Metrics calculations
                        if info["delivery"].get("opened"):
                            total_open += 1
                        else:
                            total_closed += 1
                        try:
                            rating = float(info.get("avgRating", 0))
                        except (ValueError, TypeError):
                            rating = 0
                        all_ratings.append(rating)
                        delivery_time = info["delivery"].get("deliveryTime", 999)
                        if delivery_time < fastest_delivery:
                            fastest_delivery = delivery_time
                        restaurant_details.append(data)

    # Compute aggregate metrics
    restaurants_count = len(restaurant_details)
    average_rating = round(sum(all_ratings) / len(all_ratings), 1) if all_ratings else 0
    fastest_delivery = fastest_delivery if fastest_delivery != 999 else 0
    restaurant_details.sort(key=lambda data: data["info"].get("bayesianScore", 0), reverse=True)
    
    context = {
        "query": query,
        "error": error_message,
        "restaurants_count": restaurants_count,
        "average_rating": average_rating,
        "fastest_delivery": fastest_delivery,
        "restaurant_details": restaurant_details,
    }
    return render(request, 'swiggy_app/home.html', context)
