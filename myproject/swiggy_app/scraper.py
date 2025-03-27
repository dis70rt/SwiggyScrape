# swiggy_app/scraper.py

import requests
import json

class SwiggyScrape:
    def __init__(self):
        self.lan, self.lng = self.currentLocation()

    def currentLocation(self):
        try:
            response = requests.get("https://ipinfo.io/loc", timeout=5)
            response.raise_for_status()
            return map(float, response.text.strip().split(','))
        except (requests.RequestException, ValueError):
            return (25.3167,83.0104)

    def getHeaders(self, referer: str):
        return {
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:136.0) Gecko/20100101 Firefox/136.0",
            "Connection": "keep-alive",
            "content-type": "application/json",
            "Referer": referer,
            "Cookie": f"userLocation=%7B%22lat%22%3A{self.lan}%2C%22lng%22%3A{self.lng}%7D"
        }

    def get(self):
        try:
            response = requests.get(
                "https://www.swiggy.com/dapi/restaurants/list/v5",
                headers=self.getHeaders("https://www.swiggy.com/restaurants"),
                params={
                    "lat": self.lan,
                    "lng": self.lng,
                    "is-seo-homepage-enabled": "true",
                    "page_type": "DESKTOP_WEB_LISTING",
                },
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException:
            return {}

    def getResturants(self, query: str):
        try:
            response = requests.get(
                "https://www.swiggy.com/dapi/restaurants/search/v3",
                headers=self.getHeaders(f"https://www.swiggy.com/search?query={query}"),
                params={
                    "lat": self.lan,
                    "lng": self.lng,
                    "str": query,
                    "submitAction": "ENTER",
                    "selectedPLTab": "RESTAURANT",
                },
                timeout=10
            )
            response.raise_for_status()
            return self.parseRestaurants(response.json())
        except (requests.RequestException, json.JSONDecodeError):
            return []

    def parseRestaurants(self, response_data):
        restaurants = []
        for card in response_data.get("data", {}).get("cards", []):
            try:
                for restaurant in card["groupedCard"]["cardGroupMap"]["RESTAURANT"]["cards"]:
                    info = restaurant["card"]["card"]["info"]
                    restaurants.append({
                        "id": info.get("id"),
                        "name": info.get("name"),
                        "city": info.get("city"),
                        "address": info.get("address"),
                        "avgRating": info.get("avgRating", 0),
                        "totalRatings": self.parse_ratings(info.get("totalRatingsString", "0"))
                    })
            except (KeyError, TypeError):
                continue
        return restaurants

    def parse_ratings(self, rating_str):
        try:
            clean_str = rating_str.replace('K+', '').replace(',', '')
            return float(clean_str) * 1000 if 'K' in rating_str else float(clean_str)
        except (ValueError, TypeError):
            return 0.0

class Restaurant:
    def __init__(self, ID, start_avg=3, weight=100):
        self.id = ID
        self.lan, self.lng = SwiggyScrape().currentLocation()
        self.start_avg = start_avg
        self.weight = weight

    def bayesianScore(self, ratings, noOfRatings):
        return round(((self.start_avg * self.weight) + (ratings * noOfRatings)) / (self.weight + noOfRatings), 2)

    def parse_ratings(self, rating_str):
        try:
            clean_str = rating_str.replace('K+ ratings', '').replace(',', '')
            return float(clean_str) * 1000 if 'K' in rating_str else float(clean_str)
        except Exception:
            clean_str = rating_str.replace(' ratings', '').replace(',', '')
            return float(clean_str) * 1000 if 'K' in rating_str else float(clean_str)

    def get(self):
        try:
            response = requests.get(
                "https://www.swiggy.com/dapi/menu/pl",
                headers=self.getHeaders(),
                params={
                    "page-type": "REGULAR_MENU",
                    "lat": self.lan,
                    "lng": self.lng,
                    "restaurantId": self.id,
                    "submitAction": "ENTER",
                },
                timeout=10
            )
            response.raise_for_status()
            return self.restaurants(response.json())
        except requests.RequestException:
            return {"info": {}, "dishes": {}}

    def getHeaders(self):
        return {
            "Accept": "*/*",
            "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:136.0) Gecko/20100101 Firefox/136.0",
            "Referer": f"https://www.swiggy.com/restaurant/{self.id}",
            "Cookie": f"userLocation=%7B%22lat%22%3A{self.lan}%2C%22lng%22%3A{self.lng}%7D"
        }

    def restaurants(self, response_data):
        try:
            cards = response_data["data"]["cards"]
            return {
                "info": self.restaurant_info(cards),
                "dishes": self.getDishes(cards)
            }
        except (KeyError, IndexError):
            return {"info": {}, "dishes": {}}

    def restaurant_info(self, cards):
        try:
            info = cards[2]["card"]["card"]["info"]
            return {
                "id": info.get("id"),
                "name": info.get("name"),
                "city": info.get("city"),
                "latLong": list(map(float, str(info.get("latLong")).strip().split(","))),
                "address": info.get("labels")[1]['message'] if len(info.get("labels", [])) > 1 else "Address not available",
                "bayesianScore": self.bayesianScore(info.get("avgRating", 0), self.parse_ratings(info.get("totalRatingsString", "0"))),
                "avgRating": info.get("avgRating", 0),
                "totalRatings": self.parse_ratings(info.get("totalRatingsString", "0")),
                "cuisines": info.get("cuisines", []),
                "delivery": {
                    "deliveryTime": info["sla"].get("deliveryTime"),
                    "minDeliveryTime": info["sla"].get("minDeliveryTime"),
                    "maxDeliveryTime": info["sla"].get("maxDeliveryTime"),
                    "opened": info["availability"].get("opened", False)
                }
            }
        except (StopIteration, KeyError):
            return {}

    def getDishes(self, cards):
        dishes = {}
        try:
            dish_card = next(
                c for c in cards 
                if c.get("groupedCard", {}).get("cardGroupMap", {}).get("REGULAR")
            )
            for category in dish_card["groupedCard"]["cardGroupMap"]["REGULAR"]["cards"]:
                for item in category["card"]["card"].get("itemCards", []):
                    dish = item["card"]["info"]
                    dishes[dish["id"]] = {
                        "name": dish.get("name"),
                        "description": dish.get("description"),
                        "price": dish.get("price", 0) / 100,
                        "finalPrice": dish.get("finalPrice", dish.get("price", 0)) / 100,
                        "vegClassifier": dish.get("itemAttribute", {}).get("vegClassifier", "NON_VEG"),
                        "rating": dish.get("ratings", {}).get("aggregatedRating", {}).get("rating", 0),
                        "ratingCount": dish.get("ratings", {}).get("aggregatedRating", {}).get("ratingCountV2", 0)
                    }
        except (StopIteration, KeyError):
            pass
        return dishes
