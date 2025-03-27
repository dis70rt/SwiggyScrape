import threading
import queue
from swiggy.scrape import SwiggyScrape, Restaurant
from swiggy.ui import SwiggyUI
import streamlit as st


@st.cache_data(ttl=3600)
def fetch_restaurant_data(restaurant_id):
    try:
        restaurant = Restaurant(restaurant_id)
        return restaurant.get()
    except Exception as e:
        st.error(f"Error fetching data for restaurant {restaurant_id}: {str(e)}")
        return None


def main():

    ui = SwiggyUI()
    st.set_page_config(layout="wide", page_title="🍽️ Food Finder")

    st.title("Swiggy Analyser")
    query = st.text_input(
        "What are you craving today? (e.g., Biryani, Pizza, Burger)",
        placeholder="Enter food name...",
        key="search_query",
    )

    if query:
        with st.spinner(f"Searching for {query}..."):
            swiggy = SwiggyScrape()
            try:
                restaurants = swiggy.getResturants(query)
            except Exception as e:
                st.error(f"Failed to fetch restaurants: {str(e)}")
                st.stop()

            if restaurants:
                result_queue = queue.Queue()
                threads = []

                for rest in restaurants:
                    t = threading.Thread(
                        target=lambda q, rid: q.put(fetch_restaurant_data(rid)),
                        args=(result_queue, rest["id"]),
                    )
                    t.start()
                    threads.append(t)

                for t in threads:
                    t.join()

                results = []
                while not result_queue.empty():
                    res = result_queue.get()
                    if res:
                        results.append(res)

                if results:

                    default_location = [25.3176, 82.9739]
                    ui = SwiggyUI(results, default_location)
                    ui.render_results()
                else:
                    st.error(
                        "No restaurant data could be loaded. Please try a different search."
                    )

if __name__ == "__main__":
    main()
