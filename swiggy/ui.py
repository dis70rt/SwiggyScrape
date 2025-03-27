import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px


class SwiggyUI:
    def __init__(self, restaurants=None, default_location=None):
        self.default_location = default_location or [25.3176, 82.9739]
        self.restaurants = self._process_data(restaurants) if restaurants else None
        self.filtered_df = None

    def _process_data(self, restaurants):
        processed = []
        for r in restaurants:
            try:

                lat_long = None
                if "latLong" in r["info"]:
                    try:
                        if isinstance(r["info"]["latLong"], str):
                            lat_long = list(
                                map(float, r["info"]["latLong"].strip().split(","))
                            )
                        elif isinstance(r["info"]["latLong"], (list, tuple)):
                            lat_long = list(map(float, r["info"]["latLong"]))
                    except (ValueError, AttributeError):
                        pass

                address = r["info"].get("address", "Address not available")

                latitude = (
                    lat_long[0]
                    if lat_long and len(lat_long) > 0
                    else np.random.uniform(
                        self.default_location[0] - 0.05, self.default_location[0] + 0.05
                    )
                )
                longitude = (
                    lat_long[1]
                    if lat_long and len(lat_long) > 1
                    else np.random.uniform(
                        self.default_location[1] - 0.05, self.default_location[1] + 0.05
                    )
                )

                processed.append(
                    {
                        "id": r["info"].get("id"),
                        "name": r["info"].get("name"),
                        "bayesianScore": r["info"].get("bayesianScore", 0),
                        "avgRating": r["info"].get("avgRating", 0),
                        "totalRatings": self._format_reviews(
                            r["info"].get("totalRatings", 0)
                        ),
                        "tags": self._extract_tags(r),
                        "dishes": list(r["dishes"].values()),
                        "latitude": latitude,
                        "longitude": longitude,
                        "delivery.deliveryTime": r["info"]["delivery"].get(
                            "deliveryTime", 40
                        ),
                        "delivery.minDeliveryTime": r["info"]["delivery"].get(
                            "minDeliveryTime", 35
                        ),
                        "delivery.maxDeliveryTime": r["info"]["delivery"].get(
                            "maxDeliveryTime", 45
                        ),
                        "delivery.opened": r["info"]["delivery"].get("opened", False),
                        "address": address,
                    }
                )
            except KeyError as e:
                st.warning(f"Skipping restaurant due to missing data: {str(e)}")
                continue
        return pd.DataFrame(processed)

    def _format_reviews(self, num):
        if num >= 1000:
            return f"{num/1000:.1f}K".replace(".0K", "K")
        return str(int(num))

    def _extract_tags(self, restaurant):
        tags = set()
        for dish in restaurant["dishes"].values():
            classifier = dish.get("vegClassifier", "").upper()
            if "VEG" in classifier:
                tags.add("Veg")
            if "NON_VEG" in classifier:
                tags.add("Non-Veg")
            if "EGG" in classifier:
                tags.add("Egg")
        return list(tags)

    def _create_price_chart(self, dishes):
        if not dishes:
            return None

        prices = []
        names = []
        for dish in dishes:
            price = dish.get("finalPrice") or dish.get("price", 0)
            if 0 < price < 10000:
                prices.append(price)
                name = (
                    dish["name"][:25] + "..."
                    if len(dish["name"]) > 25
                    else dish["name"]
                )
                names.append(name)

        if not prices:
            return None

        df = pd.DataFrame({"Dish": names, "Price (₹)": prices})
        fig = px.bar(
            df,
            x="Dish",
            y="Price (₹)",
            title="Top Dish Prices",
            color="Price (₹)",
            color_continuous_scale="tealrose",
        )

        fig.update_layout(
            xaxis_title=None,
            yaxis_title="Price (₹)",
            showlegend=False,
            height=350,
            margin=dict(l=20, r=20, t=40, b=100),
            xaxis_tickangle=-45,
            xaxis={"categoryorder": "total descending"},
            plot_bgcolor="rgba(0,0,0,0)",
        )
        fig.update_traces(marker_line_width=0)
        return fig

    def render_results(self):
        if self.restaurants is None or self.restaurants.empty:
            st.warning("No restaurants found. Try a different search.")
            return

        st.sidebar.header("Filters")
        dish_search = st.sidebar.text_input("Search Dishes")

        sort_option = st.sidebar.selectbox(
            "Sort By",
            options=[
                "Relevance",
                "Consistent Delivery (Most First)",
                "Bayesian Score (Highest First)",
                "Rating (Highest First)",
            ],
        )

        self.filtered_df = self.restaurants.copy()
        if dish_search:
            self.filtered_df = self.filtered_df[
                self.filtered_df["dishes"].apply(
                    lambda x: any(
                        dish_search.lower() in dish["name"].lower() for dish in x
                    )
                )
            ]

        if sort_option == "Consistent Delivery (Most First)":
            self.filtered_df["delivery_range"] = (
                self.filtered_df["delivery.maxDeliveryTime"]
                - self.filtered_df["delivery.minDeliveryTime"]
            )
            self.filtered_df = self.filtered_df.sort_values("delivery_range")
        elif sort_option == "Bayesian Score (Highest First)":
            self.filtered_df = self.filtered_df.sort_values(
                "bayesianScore", ascending=False
            )
        elif sort_option == "Rating (Highest First)":
            self.filtered_df = self.filtered_df.sort_values(
                "avgRating", ascending=False
            )

        col1, col2, col3 = st.columns(3)
        col1.metric("Restaurants Found", len(self.filtered_df))
        col2.metric("Average Rating", f"{self.filtered_df['avgRating'].mean():.1f} ⭐")
        col3.metric(
            "Fastest Delivery",
            f"{self.filtered_df['delivery.deliveryTime'].min()} mins",
        )

        st.divider()
        st.header("Insights")

        open_status = self.filtered_df["delivery.opened"].value_counts().reset_index()
        open_status.columns = ["Opened", "Count"]
        open_status["Opened"] = open_status["Opened"].map(
            {True: "Open", False: "Closed"}
        )
        pie_fig = px.pie(
            open_status,
            values="Count",
            names="Opened",
            title="Open vs. Closed Restaurants",
            color_discrete_sequence=px.colors.sequential.Teal,
        )

        if not self.filtered_df.empty:
            heatmap_fig = px.density_mapbox(
                self.filtered_df,
                lat="latitude",
                lon="longitude",
                z=None,
                radius=10,
                center={
                    "lat": self.default_location[0],
                    "lon": self.default_location[1],
                },
                zoom=10,
                mapbox_style="open-street-map",
                title="City/Area Distribution",
            )
        else:
            heatmap_fig = None

        cols = st.columns(2)
        with cols[0]:
            st.plotly_chart(
                pie_fig, use_container_width=True, config={"displayModeBar": False}
            )
            st.caption("Insight: Market saturation or churn rate.")
        with cols[1]:
            if heatmap_fig:
                st.plotly_chart(
                    heatmap_fig,
                    use_container_width=True,
                    config={"displayModeBar": False},
                )
            else:
                st.info("Heatmap data not available")
            st.caption("Insight: Identify restaurant hotspots.")

        st.divider()
        st.header("Restaurant List")

        for _, row in self.filtered_df.iterrows():
            with st.expander(
                f"{row['name']} - ⭐ {row['avgRating']} ({row['totalRatings']} reviews)",
                expanded=False,
            ):

                col1, col2 = st.columns([1, 2], gap="large")

                with col1:
                    st.write(f"📌 **Address:** {row['address']}")

                    st.markdown(
                        """
                    <style>
                    .square-map iframe {
                        height: 300px !important;
                    }
                    </style>
                    """,
                        unsafe_allow_html=True,
                    )

                    st.markdown('<div class="square-map">', unsafe_allow_html=True)
                    st.map(
                        pd.DataFrame(
                            {"lat": [row["latitude"]], "lon": [row["longitude"]]}
                        ),
                        zoom=14,
                        use_container_width=True,
                    )
                    st.markdown("</div>", unsafe_allow_html=True)

                    tags = " ".join(
                        [
                            f'<span style="background-color: {"#a3f7a3" if tag=="Veg" else "#ffb3b3"}; \
                        padding: 4px 12px; border-radius: 8px; margin: 4px; \
                        font-size: 0.9em; display: inline-block;">{tag}</span>'
                            for tag in row["tags"]
                        ]
                    )
                    st.markdown(
                        f"**Dietary Options:**<br>{tags}", unsafe_allow_html=True
                    )

                with col2:

                    st.write(f"**📊 Bayesian Score:** {row['bayesianScore']}")
                    st.write(
                        f"**⏱ Delivery Time:** {row['delivery.deliveryTime']} mins \
                            (Range: {row['delivery.minDeliveryTime']}-{row['delivery.maxDeliveryTime']} mins)"
                    )
                    st.write(
                        f"**🔄 Status:** {'🟢 Open Now' if row['delivery.opened'] else '🔴 Closed'}"
                    )

                    fig = self._create_price_chart(row["dishes"])
                    if fig:
                        st.plotly_chart(
                            fig,
                            use_container_width=True,
                            config={"displayModeBar": False},
                        )
                    else:
                        st.info("Price data not available")

                    dishes = "\n\n".join(
                        [
                            f"🍲 **{dish['name']}** \n₹{dish.get('finalPrice', dish.get('price', '?'))} \
                                        {'🥬' if dish.get('vegClassifier', '').upper() == 'VEG' else '🍗'}"
                            for dish in row["dishes"][:6]
                        ]
                    )
                    st.markdown(f"## Popular Dishes:\n{dishes}")

        st.divider()
        st.header("All Restaurant Locations")

        with st.container():
            st.markdown(
                """
            <style>
            .full-width-map {
                width: 100% !important;
                height: 500px !important;
            }
            </style>
            """,
                unsafe_allow_html=True,
            )

            st.map(
                self.filtered_df,
                latitude="latitude",
                longitude="longitude",
                size=30,
                color="#FF6B6B",
                use_container_width=True,
            )
