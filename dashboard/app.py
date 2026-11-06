"""ReviewTrust AI's first dashboard milestone: real catalog, honest placeholders."""

from __future__ import annotations

import sys
from html import escape
from pathlib import Path

# Streamlit executes this file from its own script directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import psycopg
import plotly.graph_objects as go
import streamlit as st

from dashboard.data_access import (
    ProductSnapshot,
    ReviewExcerpt,
    load_catalog,
    load_product_snapshot,
    load_recent_reviews,
)
from dashboard.view_model import filter_products, product_label


st.set_page_config(
    page_title="ReviewTrust AI | Product review clarity",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
      .block-container { max-width: 1220px; padding-top: 2rem; padding-bottom: 4rem; }
      .rt-hero {
        padding: 2.15rem 2.4rem;
        border-radius: 22px;
        background: linear-gradient(115deg, #123F3A 0%, #1C665C 62%, #268475 100%);
        color: #FFFFFF;
        margin-bottom: 1.6rem;
      }
      .rt-hero h1 { color: #FFFFFF; font-size: 2.5rem; line-height: 1.08; margin: .45rem 0; }
      .rt-hero p { color: #E1F3ED; margin: 0; max-width: 680px; }
      .rt-kicker { font-size: .76rem; font-weight: 700; letter-spacing: .17em; }
      .rt-product-title {
        color: #17312F;
        font-size: 1.65rem;
        font-weight: 700;
        line-height: 1.28;
        margin: .15rem 0 1rem;
      }
      .rt-compare-title {
        color: #17312F;
        font-size: 1.2rem;
        font-weight: 700;
        line-height: 1.35;
        min-height: 4.85rem;
        margin: .3rem 0 1rem;
        display: -webkit-box;
        -webkit-box-orient: vertical;
        -webkit-line-clamp: 3;
        overflow: hidden;
      }
      div[data-testid="stMetric"] {
        background: #FFFFFF;
        border: 1px solid #DCE8E3;
        border-radius: 14px;
        padding: .8rem 1rem;
      }
      div[data-testid="stMetricLabel"] { color: #49655F; }
    </style>
    <div class="rt-hero">
      <div class="rt-kicker">REVIEWTRUST AI / PRODUCT INTELLIGENCE</div>
      <h1>Look beyond five stars.</h1>
      <p>Explore what the available review sample actually says, then compare products with a clearer view of the evidence.</p>
    </div>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(ttl=120, show_spinner=False)
def catalog():
    return load_catalog()


@st.cache_data(ttl=120, show_spinner=False)
def snapshot(asin: str):
    return load_product_snapshot(asin)


@st.cache_data(ttl=120, show_spinner=False)
def recent_reviews(asin: str):
    return load_recent_reviews(asin)


def distribution_chart(
    left: ProductSnapshot, right: ProductSnapshot | None = None
) -> go.Figure:
    labels = ["1 star", "2 stars", "3 stars", "4 stars", "5 stars"]
    figure = go.Figure()
    figure.add_bar(
        x=labels,
        y=left.star_counts,
        name=left.product.title[:35],
        marker_color="#168477",
        hovertemplate="%{x}: %{y} sampled reviews<extra></extra>",
    )
    if right is not None:
        figure.add_bar(
            x=labels,
            y=right.star_counts,
            name=right.product.title[:35],
            marker_color="#E6A04B",
            hovertemplate="%{x}: %{y} sampled reviews<extra></extra>",
        )
    figure.update_layout(
        barmode="group",
        margin=dict(l=8, r=8, t=14, b=12),
        height=300,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#244943"),
        xaxis=dict(title=None, showgrid=False),
        yaxis=dict(title="Reviews in sample", gridcolor="#E2ECE8"),
        legend=dict(orientation="h", y=1.14),
    )
    return figure


def metric_value(value: float | None) -> str:
    return f"{value:.2f} / 5" if value is not None else "No reviews"


def show_snapshot_metrics(item: ProductSnapshot) -> None:
    first, second, third = st.columns(3)
    first.metric("Product-page rating", f"{item.product.source_rating:.1f} / 5")
    second.metric("Sample rating", metric_value(item.sample_rating))
    third.metric("Reviews in sample", f"{item.sample_review_count:,}")
    st.caption(
        f"Product page lists {item.product.source_rating_count:,} ratings. "
        "The sample rating uses only cleaned reviews in this dataset."
    )


def show_review(review: ReviewExcerpt) -> None:
    heading = review.title or "Untitled review"
    with st.expander(f"{review.stars}/5 stars | {heading[:90]} | {review.review_date}"):
        excerpt = review.body.strip()
        st.write(excerpt[:700] + ("..." if len(excerpt) > 700 else ""))
        st.caption(f"Source review ID: {review.source_review_id}")


try:
    products = catalog()
except (psycopg.Error, OSError, ValueError):
    st.error(
        "The product database is unavailable. Start PostgreSQL with "
        "'docker compose up -d --wait db' and run "
        "'python3 pipeline/load_snapshot.py' from the project root."
    )
    st.stop()

with st.sidebar:
    st.subheader("About this preview")
    st.write(
        "This first dashboard milestone uses real A1 data. Trust signals and "
        "Pros & Cons will appear when the B/C analysis modules are connected."
    )
    st.caption("Source: DataHive Amazon Reviews sample")
    st.caption("Review dates: July 1999 to July 2025")

explore_tab, compare_tab = st.tabs(["Explore products", "Compare two products"])

with explore_tab:
    st.subheader("Find a product")
    search_column, category_column = st.columns([2.2, 1])
    with search_column:
        query = st.text_input(
            "Search by product name or ASIN",
            placeholder="Try water bottle, headphones, or an ASIN",
            key="product_search",
        )
    categories = ["All categories"] + sorted(
        {product.category for product in products}
    )
    with category_column:
        category = st.selectbox(
            "Category", categories, key="category_filter"
        )
    matches = filter_products(products, query, category)
    st.caption(
        f"{len(matches):,} matching products"
        + (f" | Showing the first 60" if len(matches) > 60 else "")
    )
    if not matches:
        st.info("No products match these filters. Try a broader search.")
    else:
        chosen = st.selectbox(
            "Select a product",
            matches[:60],
            format_func=product_label,
            key="selected_product",
        )
        selected = snapshot(chosen.asin)
        if selected is not None:
            st.divider()
            st.caption(f"{selected.product.category}  /  ASIN {selected.product.asin}")
            st.markdown(
                f'<h2 class="rt-product-title">{escape(selected.product.title)}</h2>',
                unsafe_allow_html=True,
            )
            show_snapshot_metrics(selected)
            if selected.first_review_date and selected.last_review_date:
                st.caption(
                    f"Sample review dates: {selected.first_review_date} to "
                    f"{selected.last_review_date}"
                )

            chart_column, status_column = st.columns([1.35, 1])
            with chart_column:
                st.markdown("#### Rating distribution")
                st.plotly_chart(
                    distribution_chart(selected),
                    width="stretch",
                    config={"displayModeBar": False},
                )
            with status_column:
                with st.container(border=True):
                    st.markdown("#### Review trust")
                    st.info(
                        "Analysis pending. B1 will add similarity and timing "
                        "signals, plus an explainable weighted rating."
                    )
                    st.caption("A signal is not proof that a review is fake.")
                with st.container(border=True):
                    st.markdown("#### Pros & Cons")
                    st.info(
                        "Analysis pending. B2 will add recurring themes and "
                        "support each theme with review evidence."
                    )

            st.markdown("#### Recent source reviews")
            st.caption("Original excerpts from the sample, not extracted pros or cons.")
            excerpts = recent_reviews(selected.product.asin)
            if excerpts:
                for review in excerpts:
                    show_review(review)
            else:
                st.caption("No review text is available for this product.")

with compare_tab:
    st.subheader("Compare two products")
    st.caption(
        "Compare factual source and sample metrics now. Trust signals and "
        "Pros & Cons will be added when analysis is ready."
    )
    if len(products) < 2:
        st.info("At least two products are needed for comparison.")
    else:
        comparable_index = next(
            (
                index
                for index, product in enumerate(products[1:], 1)
                if product.category == products[0].category
            ),
            1,
        )
        left_column, right_column = st.columns(2)
        with left_column:
            left_product = st.selectbox(
                "First product",
                products,
                index=0,
                format_func=product_label,
                key="compare_left",
            )
        with right_column:
            right_product = st.selectbox(
                "Second product",
                products,
                index=comparable_index,
                format_func=product_label,
                key="compare_right",
            )
        if left_product.asin == right_product.asin:
            st.warning("Choose two different products to compare.")
        else:
            left_snapshot = snapshot(left_product.asin)
            right_snapshot = snapshot(right_product.asin)
            if left_snapshot and right_snapshot:
                for column, item in zip(
                    (left_column, right_column),
                    (left_snapshot, right_snapshot),
                ):
                    with column:
                        with st.container(border=True):
                            st.caption(f"{item.product.category} / {item.product.asin}")
                            st.markdown(
                                f'<h3 class="rt-compare-title" '
                                f'title="{escape(item.product.title, quote=True)}">'
                                f'{escape(item.product.title)}</h3>',
                                unsafe_allow_html=True,
                            )
                            st.metric(
                                "Product-page rating",
                                f"{item.product.source_rating:.1f} / 5",
                            )
                            st.metric("Sample rating", metric_value(item.sample_rating))
                            st.metric(
                                "Reviews in sample",
                                f"{item.sample_review_count:,}",
                            )
                            st.caption(
                                f"Product page lists "
                                f"{item.product.source_rating_count:,} ratings."
                            )
                st.markdown("#### Sample rating distributions")
                st.plotly_chart(
                    distribution_chart(left_snapshot, right_snapshot),
                    width="stretch",
                    config={"displayModeBar": False},
                )
                st.info(
                    "Weighted ratings and review themes are not available yet. "
                    "The chart above uses only cleaned sample reviews."
                )

st.divider()
st.caption(
    "DataHive Amazon Reviews sample | Historical review data, not live "
    "Amazon ratings | Review signals are not confirmed fraud labels."
)
