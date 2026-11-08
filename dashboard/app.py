"""ReviewTrust's product evidence desk: real sample data, clearly labeled."""
from __future__ import annotations
from dashboard.hybrid_search import hybrid_rank_products

import sys
from html import escape
from pathlib import Path
from textwrap import shorten
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import psycopg
import streamlit as st
from dashboard.data_access import Product, ProductSnapshot, ReviewExcerpt, load_catalog, load_product_snapshot, load_recent_reviews
from dashboard.view_model import amazon_asin, filter_products, product_label
from dashboard.analysis_access import (
    load_reliability_results,
    load_pros_cons_results,
)
from dashboard.shopping_agent_ui import render_shopping_agent

st.set_page_config(page_title="ReviewTrust | Product evidence desk", page_icon="◒", layout="wide", initial_sidebar_state="collapsed")
st.markdown("""
<style>
:root { --paper:#F5F3EC; --ink:#202620; --muted:#657067; --line:#DADDD0; --lime:#D6EA8D; }
html,body,[class*="css"],[data-testid="stApp"] { font-family:'Onest',Arial,sans-serif; }
[data-testid="stApp"] { background:var(--paper); color:var(--ink); }
.block-container { max-width:1240px; padding-top:1.45rem; padding-bottom:5rem; }
header[data-testid="stHeader"] { background:transparent; }
.rt-topline { display:flex; justify-content:space-between; align-items:center; padding:0 0 1rem; border-bottom:1px solid var(--ink); gap:1rem; }
.rt-wordmark { font-size:1.05rem; font-weight:700; letter-spacing:-.055em; color:var(--ink); }
.rt-symbol { display:inline-block; background:var(--ink); color:var(--lime); border-radius:50%; width:1.45rem; height:1.45rem; text-align:center; line-height:1.35rem; margin-right:.5rem; }
.rt-topnote,.rt-eyebrow,.rt-section-label,.rt-micro { font-family:'DM Mono',monospace; font-size:.68rem; letter-spacing:.08em; text-transform:uppercase; color:var(--muted); }
.rt-intro { padding:1.7rem 0 1.1rem; max-width:900px; }
.rt-intro h1 { font-family:'Instrument Serif',Georgia,serif; font-weight:400; letter-spacing:-.035em; line-height:.98; font-size:clamp(3.2rem,5vw,4.8rem); margin:.35rem 0 .8rem; color:var(--ink); }
.rt-intro h1 em { color:#708B39; font-weight:400; }
.rt-intro p { color:#526057; font-size:1.06rem; line-height:1.55; max-width:650px; margin:0; }
.rt-section-head { display:flex; justify-content:space-between; align-items:end; gap:1rem; margin:2rem 0 1rem; border-top:1px solid var(--ink); padding-top:.9rem; }
.rt-section-head h2 { font-family:'Instrument Serif',Georgia,serif; font-weight:400; letter-spacing:-.025em; font-size:2.15rem; margin:.2rem 0 0; color:var(--ink); }
.rt-section-head p { color:var(--muted); font-size:.84rem; margin:0; }
.rt-product-head { padding:1.1rem 0 1.4rem; }
.rt-product-head h2 { font-family:'Instrument Serif',Georgia,serif; font-size:clamp(2rem,3.7vw,3.5rem); font-weight:400; letter-spacing:-.03em; line-height:1.08; margin:.5rem 0 .75rem; color:var(--ink); }
.rt-product-head p { color:var(--muted); font-size:.84rem; margin:0; }
.rt-stat { border-top:1px solid var(--ink); padding:.65rem 0 1rem; min-height:7.7rem; }
.rt-stat .label { font-family:'DM Mono',monospace; text-transform:uppercase; letter-spacing:.05em; color:var(--muted); font-size:.65rem; }
.rt-stat .value { font-family:'Instrument Serif',Georgia,serif; font-size:2.65rem; line-height:1.15; color:var(--ink); margin:.55rem 0 .1rem; }
.rt-stat .detail { color:var(--muted); font-size:.74rem; }
.rt-note { border-left:3px solid #8EAD4F; background:#EBEDE3; padding:.75rem 1rem; color:#4C5B48; font-size:.82rem; line-height:1.45; margin:.75rem 0 1.3rem; }
.rt-review { border-top:1px solid var(--line); padding:1rem 0 1.15rem; }
.rt-review .rating { color:#668135; font-family:'DM Mono',monospace; font-size:.72rem; }
.rt-review h3 { font-size:1rem; line-height:1.3; font-weight:600; margin:.4rem 0; color:var(--ink); }
.rt-review p { font-size:.9rem; line-height:1.55; margin:0 0 .55rem; color:#49534B; }
.rt-review .meta { color:var(--muted); font-family:'DM Mono',monospace; font-size:.65rem; }
.rt-compare-card { border-top:1px solid var(--ink); padding:1rem 0 .2rem; }
.rt-compare-card .number { display:inline-block; background:var(--lime); padding:.2rem .45rem; font-family:'DM Mono',monospace; font-size:.66rem; }
.rt-compare-card h3 { font-family:'Instrument Serif',Georgia,serif; font-size:1.7rem; font-weight:400; line-height:1.12; min-height:5.8rem; margin:.8rem 0; color:var(--ink); }
.rt-compare-card .meta { color:var(--muted); font-size:.75rem; }
.rt-compare-row { display:flex; justify-content:space-between; align-items:baseline; border-top:1px solid var(--line); padding:.65rem 0; gap:1rem; }
.rt-compare-row span { color:var(--muted); font-size:.75rem; }
.rt-compare-row strong { color:var(--ink); font-size:1.1rem; font-weight:600; }
.rt-future { border-top:1px solid var(--ink); margin-top:2rem; padding:1rem 0; display:flex; justify-content:space-between; gap:2rem; }
.rt-future strong { font-size:.9rem; }.rt-future p { color:var(--muted); font-size:.8rem; margin:.3rem 0 0; max-width:590px; }
.rt-future span { font-family:'DM Mono',monospace; font-size:.67rem; color:#6A7D46; white-space:nowrap; }
.rt-footer { border-top:1px solid var(--line); margin-top:2.2rem; padding-top:.8rem; color:var(--muted); font-family:'DM Mono',monospace; text-transform:uppercase; font-size:.63rem; letter-spacing:.04em; }
div[data-testid="stSelectbox"] label,div[data-testid="stTextInput"] label { font-size:.78rem; font-weight:600; }
div[data-baseweb="select"] > div,div[data-testid="stTextInput"] input { background:#FFFEF9; border-color:#BFC6B8; border-radius:3px; }
div[data-testid="stSegmentedControl"] button,div[data-testid="stButton"] button { border-radius:2px; font-weight:600; }
[data-testid="stImage"] img { object-fit:contain; background:#F0F0E8; border:1px solid var(--line); border-radius:3px; max-height:260px; }
@media (max-width:700px) { .block-container { padding-top:.7rem; } .rt-topnote { display:none; } .rt-intro { padding:1.8rem 0 1rem; } .rt-section-head { display:block; } .rt-section-head p { margin-top:.5rem; } .rt-future { display:block; } .rt-future span { display:block; margin-top:.65rem; } }
</style>
<div class="rt-topline"><div class="rt-wordmark"><span class="rt-symbol">✦</span> ReviewTrust<span style="color:#7767DF">.</span></div></div>
""", unsafe_allow_html=True)
st.markdown(f"<style>{Path(__file__).with_name('styles.css').read_text()}</style>", unsafe_allow_html=True)

@st.cache_data(ttl=120, show_spinner=False)
def catalog() -> list[Product]:
    return load_catalog()

@st.cache_resource(show_spinner="Building semantic search index...")
def semantic_index(products: tuple[Product, ...]):
    """Cache the SBERT model and product embeddings."""
    from dashboard.semantic_search import SemanticProductSearch

    return SemanticProductSearch(list(products))

@st.cache_data(ttl=120, show_spinner=False)
def snapshot(asin: str) -> ProductSnapshot | None:
    return load_product_snapshot(asin)

@st.cache_data(ttl=120, show_spinner=False)
def recent_reviews(asin: str) -> list[ReviewExcerpt]:
    return load_recent_reviews(asin, limit=6)

@st.cache_data(ttl=120, show_spinner=False)
def reliability_results():
    return load_reliability_results()

@st.cache_data(ttl=120, show_spinner=False)
def pros_cons_results():
    return load_pros_cons_results()

def section(title: str, number: str, note: str = "") -> None:
    st.markdown(f'<div class="rt-section-head"><div><div class="rt-section-label">{escape(number)}</div><h2>{escape(title)}</h2></div><p>{escape(note)}</p></div>', unsafe_allow_html=True)

def rating_distribution(item: ProductSnapshot) -> str:
    count = item.sample_review_count
    positive = rating_share(item, (4, 5)) if count else 0
    rows = []
    for stars in range(5, 0, -1):
        reviews = item.star_counts[stars - 1]
        width = 100 * reviews / count if count else 0
        rows.append(
            f'<div class="rt-dist-row"><span>{stars} <b>★</b></span>'
            f'<div class="rt-dist-rail"><div class="rt-dist-fill level-{stars}" style="width:{width:.2f}%"></div></div>'
            f'<strong>{reviews}</strong></div>'
        )
    return (
        '<div class="rt-dist-card"><div class="rt-dist-head"><div><span class="rt-micro">RATING DISTRIBUTION</span>'
        '<h3>Every star, in context.</h3></div>'
        f'<div class="rt-dist-share"><strong>{positive}%</strong><span>rated 4 or 5 stars</span></div></div>'
        f'<div class="rt-dist-list">{"".join(rows)}</div>'
        f'<p>Based on {count:,} cleaned reviews in this dataset. Counts are shown beside every bar.</p></div>'
    )

def restore_input(key: str, default: object = "") -> None:
    """Recreate a widget from its durable value after another page hid it."""
    widget_key = f"_{key}"
    if widget_key not in st.session_state:
        st.session_state[widget_key] = st.session_state.get(key, default)

def save_input(key: str) -> None:
    st.session_state[key] = st.session_state[f"_{key}"]

def save_search_input(key: str) -> None:
    save_input(key)
    reset_browse_count()

def compare_from_explore(product: Product) -> None:
    st.session_state["compare_left_product"] = product
    st.session_state["_compare_left_product"] = product
    st.session_state["page"] = "Compare"

def open_featured(product: Product) -> None:
    st.session_state["evidence_product"] = product
    st.session_state["_evidence_product"] = product
    st.session_state["explore_mode"] = "detail"
    st.session_state["page"] = "Explore"

def open_category(category: str) -> None:
    st.session_state["category_filter"] = category
    st.session_state["_category_filter"] = category
    st.session_state["product_search"] = ""
    st.session_state["_product_search"] = ""
    st.session_state["browse_visible_count"] = 8
    st.session_state["explore_mode"] = "browse"
    st.session_state["page"] = "Explore"

def set_search_query(query: str) -> None:
    st.session_state["product_search"] = query
    st.session_state["_product_search"] = query
    st.session_state["category_filter"] = "All categories"
    st.session_state["_category_filter"] = "All categories"
    st.session_state.pop("selected_product", None)
    st.session_state["browse_visible_count"] = 8

def reset_browse_count() -> None:
    st.session_state["browse_visible_count"] = 8

def show_product_results() -> None:
    st.session_state["explore_mode"] = "browse"

def load_more_products() -> None:
    st.session_state["browse_visible_count"] = st.session_state.get("browse_visible_count", 8) + 8

def fill_example_links() -> None:
    st.session_state["amazon_link_a"] = "https://www.amazon.com/dp/B085DVHQ57"
    st.session_state["amazon_link_b"] = "https://www.amazon.com/dp/B0D2Z1PJWT"
    st.session_state["_amazon_link_a"] = st.session_state["amazon_link_a"]
    st.session_state["_amazon_link_b"] = st.session_state["amazon_link_b"]

def toggle_evidence() -> None:
    st.session_state["evidence_open"] = not st.session_state.get("evidence_open", False)

def rating_share(item: ProductSnapshot, stars: tuple[int, ...]) -> int:
    if item.sample_review_count == 0:
        return 0
    return round(100 * sum(item.star_counts[star - 1] for star in stars) / item.sample_review_count)

def product_image(product: Product) -> str:
    image = (f'<img src="{escape(product.image_url, quote=True)}" alt="{escape(product.title, quote=True)}" loading="lazy">'
             if product.image_url and product.image_url.startswith(("https://", "http://"))
             else '<span class="rt-no-image">Product image unavailable</span>')
    return image

def featured_card(product: Product, index: int) -> None:
    tones = ("lavender", "apricot", "citron", "sky")
    st.markdown(
        f'<article class="rt-feature-card size-{index}"><div class="rt-feature-image {tones[index % 4]}"><span class="rt-feature-tag">{escape(product.category)}</span>'
        f'<span class="rt-feature-medal">✦ 0{index + 1}</span>{product_image(product)}'
        f'<div class="rt-feature-overlay"><span>{product.source_rating:.1f} ★ listed rating</span></div></div>'
        f'<div class="rt-feature-body"><h3 title="{escape(product.title, quote=True)}">{escape(shorten(product.title, width=78, placeholder="…"))}</h3><div class="rt-feature-meta">{product.source_rating_count:,} ratings listed on product page</div></div></article>',
        unsafe_allow_html=True,
    )
    st.button("View review evidence →", key=f"featured_{product.asin}", on_click=open_featured, args=(product,), use_container_width=True)

def browse_card(product: Product, index: int) -> None:
    tones = ("lavender", "citron", "apricot", "sky")
    st.markdown(
        f'<article class="rt-browse-card"><div class="rt-browse-image {tones[index % 4]}">'
        f'<span class="rt-browse-index">DISCOVER / {index + 1:02d}</span>'
        f'<span class="rt-browse-rating">★ {product.source_rating:.1f}</span>{product_image(product)}</div>'
        f'<div class="rt-browse-info"><h3 title="{escape(product.title, quote=True)}">{escape(shorten(product.title, width=56, placeholder="…"))}</h3>'
        f'<div class="rt-browse-meta">{escape(product.category)} · {product.source_rating_count:,} listed ratings</div></div></article>',
        unsafe_allow_html=True,
    )
    st.button("Inspect reviews ↗", key=f"browse_{product.asin}", on_click=open_featured, args=(product,), use_container_width=True)

def search_result_card(product: Product, index: int) -> None:
    st.markdown(
        f'<article class="rt-search-result tone-{index}"><div class="rt-search-result-image">{product_image(product)}</div>'
        f'<div class="rt-search-result-copy"><span>{escape(product.category)}</span>'
        f'<h3 title="{escape(product.title, quote=True)}">{escape(shorten(product.title, width=67, placeholder="…"))}</h3>'
        f'<p><strong>★ {product.source_rating:.1f}</strong> listed rating <i>·</i> {product.source_rating_count:,} ratings</p></div></article>',
        unsafe_allow_html=True,
    )
    st.button("Explore this product →", key=f"search_result_{product.asin}", on_click=open_featured, args=(product,), use_container_width=True)

def category_card(category: str, product: Product, index: int) -> None:
    tones = ("mint", "sun", "rose", "blue", "lilac")
    st.markdown(
        f'<div class="rt-category-card {tones[index % len(tones)]}"><div class="rt-category-label">{escape(category)}</div>'
        f'<div class="rt-category-image">{product_image(product)}</div></div>',
        unsafe_allow_html=True,
    )
    st.button("Browse category ↗", key=f"category_{category}", on_click=open_category, args=(category,), use_container_width=True)

def pulse_card(product: Product, kicker: str, value: str, label: str, detail: str, index: int) -> str:
    return (
        f'<article class="rt-pulse-card tone-{index}" tabindex="0">'
        f'<div class="rt-pulse-top"><span class="rt-pulse-thumb">{product_image(product)}</span><span>{escape(kicker)}</span><b>↗</b></div>'
        f'<strong>{escape(value)}</strong><h3>{escape(label)}</h3>'
        f'<p class="rt-pulse-detail">{escape(detail)}</p></article>'
    )

def best_buy_card(item: ProductSnapshot, index: int) -> None:
    product = item.product
    positive = rating_share(item, (4, 5))
    st.markdown(
        f'<article class="rt-best-card size-{index}"><div class="rt-best-image tone-{index}">'
        f'<span>0{index + 1} / BEST REVIEWED</span>{product_image(product)}</div>'
        f'<div class="rt-best-body"><div class="rt-best-category">{escape(product.category)}</div>'
        f'<h3 title="{escape(product.title, quote=True)}">{escape(shorten(product.title, width=72, placeholder="…"))}</h3>'
        f'<div class="rt-best-metric"><strong>{item.sample_rating:.2f}<small> / 5</small></strong><span>SAMPLE MEAN<br>{item.sample_review_count} REVIEWS</span></div>'
        f'<div class="rt-best-proof"><span>{positive}% positive</span><span>{product.source_rating:.1f} / 5 listed rating</span></div></div></article>',
        unsafe_allow_html=True,
    )
    st.button("View the evidence →", key=f"best_{product.asin}", on_click=open_featured, args=(product,), use_container_width=True)

def review_card(review: ReviewExcerpt) -> str:
    body = review.body.strip()
    if len(body) > 270:
        body = body[:267].rsplit(" ", 1)[0] + "..."
    return f'<article class="rt-review"><div class="rating">{"★" * review.stars} &nbsp; {review.stars} / 5 STARS</div><h3>{escape(review.title or "Untitled review")}</h3><p>{escape(body)}</p><div class="meta">{escape(str(review.review_date))} &nbsp; / &nbsp; Source ID {escape(review.source_review_id)}</div></article>'


def render_pros_cons(asin: str) -> None:
    """Display B2 product themes and supporting review evidence."""
    result = pros_cons_results().get(asin)

    if result is None:
        st.info("Pros & Cons analysis is unavailable for this product.")
        return

    def render_aspects(aspects: list, positive: bool) -> None:
        kind = "liked" if positive else "disliked"
        heading = "What buyers liked" if positive else "What buyers flagged"
        symbol = "✓" if positive else "×"
        with st.container(key=f"compare_{kind}_{asin}"):
            st.markdown(
                f'<div class="rt-theme-heading {kind}"><span aria-hidden="true">{symbol}</span>'
                f'<strong>{heading}</strong><small>{len(aspects[:5])} themes</small></div>',
                unsafe_allow_html=True,
            )

            if not aspects:
                st.caption("No qualifying themes were extracted from the current review sample.")
                return

            for aspect in aspects[:5]:
                label = str(aspect.get("label", "Other"))
                count = int(aspect.get("review_count", 0))
                support = str(aspect.get("support_level", "unknown"))

                with st.expander(f"{label}  ·  {count} reviews"):
                    st.caption(f"Evidence support: {support}")
                    evidence = aspect.get("evidence", [])
                    if not evidence:
                        st.caption("No supporting excerpts available.")
                        continue
                    for review in evidence[:3]:
                        text = str(review.get("text", "")).strip()
                        stars = review.get("stars", "N/A")
                        if text:
                            st.markdown(f"> {text}")
                            st.caption(f"Review rating: {stars}/5")

    with st.container(key=f"compare_themes_{asin}"):
        st.markdown(
            f'<div class="rt-theme-context"><span>B2 / REVIEW THEMES</span>'
            f'<p>Patterns from <strong>{result.n_text_reviews:,} written reviews</strong>. Tap a row for evidence.</p></div>',
            unsafe_allow_html=True,
        )
        pros_col, cons_col = st.columns(2, gap="medium")
        with pros_col:
            render_aspects(result.pros, positive=True)
        with cons_col:
            render_aspects(result.cons, positive=False)




def compare_card(item: ProductSnapshot, number: str) -> None:
    product = item.product
    reliability = reliability_results().get(product.asin)
    sample_rating = f"{item.sample_rating:.2f} / 5" if item.sample_rating is not None else "No reviews"
    if reliability is not None:
        delta = reliability.adjusted_rating - reliability.original_rating
        trust_rating = f"{reliability.adjusted_rating:.2f}"
        rating_change = f"{delta:+.3f}"
        adjusted_reviews = f"{reliability.adjusted_review_count:,} ({reliability.adjusted_review_percentage:.1f}%)"
    else:
        trust_rating = "Unavailable"
        rating_change = "Unavailable"
        adjusted_reviews = "Unavailable"

    metrics = (
        ("Product-page rating", f"{product.source_rating:.1f} / 5"),
        ("Rating from sample", sample_rating),
        ("Reviews in sample", f"{item.sample_review_count:,}"),
        ("Product-page rating count", f"{product.source_rating_count:,}"),
        ("B1 rating change", rating_change),
        ("Reviews adjusted", adjusted_reviews),
    )
    metric_html = "".join(
        f'<div class="rt-compare-metric"><span>{escape(label)}</span><strong>{escape(value)}</strong></div>'
        for label, value in metrics
    )
    trust_unit = "<small> / 5</small>" if reliability is not None else ""
    st.markdown(
        f'<article class="rt-compare-product">'
        f'<div class="rt-compare-product-top"><span>PRODUCT {escape(number)} / REVIEW SNAPSHOT</span>'
        f'<a href="https://www.amazon.com/dp/{escape(product.asin, quote=True)}" '
        f'target="_blank" rel="noopener noreferrer">Amazon listing ↗</a></div>'
        f'<div class="rt-compare-product-main"><div class="rt-compare-product-image">{product_image(product)}</div>'
        f'<div class="rt-compare-product-name"><small>{escape(product.category)} &nbsp;·&nbsp; {escape(product.asin)}</small>'
        f'<h3 title="{escape(product.title, quote=True)}">{escape(product.title)}</h3></div></div>'
        f'<div class="rt-compare-trust"><div><span>B1 / TRUST-ADJUSTED RATING</span>'
        f'<p>Experimental rating from this review sample</p></div>'
        f'<strong>{escape(trust_rating)}{trust_unit}</strong></div>'
        f'<div class="rt-compare-metrics">{metric_html}</div></article>',
        unsafe_allow_html=True,
    )


def render_compare_summary(left_product: Product, right_product: Product) -> None:
    """Render the selected comparison near the link form, including B2 themes."""
    left_snapshot = snapshot(left_product.asin)
    right_snapshot = snapshot(right_product.asin)
    if not left_snapshot or not right_snapshot:
        st.warning("Review evidence is unavailable for one of these products.")
        return

    section("Comparison results", "RESULT", "Ratings and B2 review themes in one view")
    left_col, right_col = st.columns(2, gap="large")
    for column, item, number in (
        (left_col, left_snapshot, "01"),
        (right_col, right_snapshot, "02"),
    ):
        with column:
            compare_card(item, number)
            render_pros_cons(item.product.asin)
            with st.container(key=f"compare_source_{item.product.asin}"):
                st.markdown(
                    '<div class="rt-source-heading"><span aria-hidden="true">“</span>'
                    '<div><strong>In shoppers’ words</strong>'
                    '<small>Original review excerpts from the sample</small></div></div>',
                    unsafe_allow_html=True,
                )
                with st.expander(f"Read original reviews · Product {number}"):
                    excerpts = recent_reviews(item.product.asin)
                    if excerpts:
                        for review in excerpts[:3]:
                            st.markdown(review_card(review), unsafe_allow_html=True)
                    else:
                        st.caption("No review text is available for this product.")
try:
    products = catalog()
except (psycopg.Error, OSError, ValueError):
    st.error("The product database is unavailable. Start PostgreSQL with 'docker compose up -d --wait db' and run 'python3 pipeline/load_snapshot.py' from the project root.")
    st.stop()
if not products:
    st.warning("The catalog is empty. Load the A1 snapshot to explore products.")
    st.stop()
products_by_asin = {product.asin: product for product in products}
if st.session_state.get("page") not in ("Explore", "Compare", "AI Advisor"):
    st.session_state["page"] = "AI Advisor"
st.session_state.setdefault("explore_mode", "browse")
st.session_state.setdefault("browse_visible_count", 8)
hero_asins = ("B085DVHQ57", "B097CNMZF5", "B0014BYHJE")
hero_products = [products_by_asin[asin] for asin in hero_asins if asin in products_by_asin]
hero_products.extend(product for product in products if product.image_url and product not in hero_products)
hero_products = hero_products[:3]
hero_visual = ''.join(f'<div class="rt-hero-product item-{index}">{product_image(product)}</div>' for index, product in enumerate(hero_products))
st.markdown('<div id="product-pages" class="rt-jump-target"></div>', unsafe_allow_html=True)
with st.container(key="page_navigation"):
    st.segmented_control(
        "Main pages", ["AI Advisor", "Compare", "Explore"],
        key="page", selection_mode="single", required=True, label_visibility="collapsed",
    )

if st.session_state["page"] == "AI Advisor":
    st.markdown(
        '<div class="rt-intro"><div class="rt-hero-copy">'
        '<span class="rt-hero-kicker">REVIEW EVIDENCE, MADE PERSONAL</span>'
        '<h1>Know more.<br><em>Choose better.</em></h1>'
        '<p>Find the Amazon product that fits your needs, backed by real customer reviews and a clear view of the tradeoffs.</p></div>'
        f'<div class="rt-hero-art" aria-hidden="true"><div class="rt-hero-platform"></div>{hero_visual}'
        '<div class="rt-art-sticker"><span>A</span><b>vs</b><span>B</span></div></div></div>',
        unsafe_allow_html=True,
    )
    render_shopping_agent(products)
elif st.session_state["page"] == "Explore":
    if st.session_state["explore_mode"] == "detail":
        st.button("← Back to product results", on_click=show_product_results, key="back_to_products")
        if st.session_state.get("evidence_product") not in products:
            st.session_state["evidence_product"] = products_by_asin.get("B085DVHQ57", products[0])
        if st.session_state.get("_evidence_product") not in products:
            st.session_state["_evidence_product"] = st.session_state["evidence_product"]
        chosen = st.selectbox(
            "Choose a product to inspect", products, format_func=product_label,
            key="_evidence_product", on_change=save_input, args=("evidence_product",),
        )
        selected = snapshot(chosen.asin)
        if selected is None:
            st.warning("Review evidence is unavailable for this product.")
        else:

            # Updated product inspection UI.
            section(
                "The story behind this product.",
                "06 / INSPECT",
                "A focused view of the source facts and review sample",
            )

            with st.container(key="product_stage"):
                image_col, identity_col = st.columns(
                    [.88, 1.12],
                    gap="large",
                    vertical_alignment="center",
                )

                with image_col:
                    st.markdown(
                        f'<div class="rt-inspect-visual">'
                        f'<span>THE PRODUCT / {escape(selected.product.asin)}</span>'
                        f'<div class="rt-inspect-product">'
                        f'{product_image(selected.product)}'
                        f'</div>'
                        f'<b>✳ &nbsp; REVIEW EVIDENCE INSIDE</b>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

                with identity_col:
                    positive_share = (
                        rating_share(selected, (4, 5))
                        if selected.sample_review_count
                        else None
                    )

                    summary = (
                        f"{positive_share}% of the cleaned review sample "
                        "rated this product 4 or 5 stars."
                        if positive_share is not None
                        else "Review evidence is being collected for this product."
                    )

                    sample_mean = (
                        f"{selected.sample_rating:.2f}"
                        if selected.sample_rating is not None
                        else "—"
                    )

                    st.markdown(
                        f'<div class="rt-product-head">'
                        f'<div class="rt-eyebrow">'
                        f'{escape(selected.product.category)}'
                        f' &nbsp; / &nbsp; PRODUCT {escape(selected.product.asin)}'
                        f'</div>'
                        f'<h2>{escape(selected.product.title)}</h2>'
                        f'<p>{escape(summary)}</p>'
                        f'<div class="rt-inspect-metrics">'
                        f'<div><span>PRODUCT-PAGE RATING</span>'
                        f'<strong>{selected.product.source_rating:.1f}'
                        f'<small> / 5</small></strong>'
                        f'<em>{selected.product.source_rating_count:,} listed ratings</em>'
                        f'</div>'
                        f'<div><span>SAMPLE MEAN</span>'
                        f'<strong>{sample_mean}<small> / 5</small></strong>'
                        f'<em>{selected.sample_review_count:,} cleaned reviews</em>'
                        f'</div></div>'
                        f'<div class="rt-inspect-period">'
                        f'REVIEW WINDOW &nbsp; '
                        f'{escape(str(selected.first_review_date or "N/A"))}'
                        f' — '
                        f'{escape(str(selected.last_review_date or "N/A"))}'
                        f'</div></div>',
                        unsafe_allow_html=True,
                    )

                    compare_action, amazon_action = st.columns(
                        2, gap="small"
                    )

                    with compare_action:
                        st.button(
                            "Compare this product →",
                            on_click=compare_from_explore,
                            args=(selected.product,),
                            type="primary",
                            use_container_width=True,
                        )

                    with amazon_action:
                        st.link_button(
                            "View Amazon listing ↗",
                            f"https://www.amazon.com/dp/{selected.product.asin}",
                            use_container_width=True,
                        )


            # B1: Product-level review reliability analysis.
            reliability = reliability_results().get(selected.product.asin)

            st.markdown(
                '<div class="rt-micro" style="margin-top:1.2rem">'
                'B1 / REVIEW RELIABILITY ANALYSIS'
                '</div>',
                unsafe_allow_html=True,
            )

            if reliability is not None:
                rating_delta = (
                    reliability.adjusted_rating
                    - reliability.original_rating
                )

                st.markdown(
                    '<div class="rt-inspect-metrics" '
                    'style="grid-template-columns:repeat(3,minmax(0,1fr))">'
                    '<div>'
                    '<span>TRUST-ADJUSTED RATING</span>'
                    f'<strong>{reliability.adjusted_rating:.2f}'
                    '<small> / 5</small></strong>'
                    f'<em>Original B1 sample: {reliability.original_rating:.2f}</em>'
                    '</div>'
                    '<div>'
                    '<span>RATING CHANGE</span>'
                    f'<strong>{rating_delta:+.3f}</strong>'
                    '<em>Adjusted minus original B1 rating</em>'
                    '</div>'
                    '<div>'
                    '<span>REVIEWS ADJUSTED</span>'
                    f'<strong>{reliability.adjusted_review_count:,}</strong>'
                    f'<em>{reliability.adjusted_review_percentage:.1f}% '
                    'of B1 analyzed reviews</em>'
                    '</div>'
                    '</div>',
                    unsafe_allow_html=True,
                )

                st.caption(
                    "B1 uses review reliability signals to adjust the "
                    "contribution of certain reviews. The adjusted rating "
                    "is an experimental sample-based metric, not an "
                    "official Amazon rating or a determination that "
                    "a review is fraudulent."
                )
            else:
                st.caption(
                    "B1 reliability analysis is not available for this product."
                )


            st.markdown('<div class="rt-note">These ratings come from different populations. The product-page rating reflects its listed rating count; the sample mean uses only cleaned reviews available in this dataset.</div>', unsafe_allow_html=True)

            # B2: Evidence-backed product pros and cons.
            section(
                "What reviewers are saying",
                "06 / PROS & CONS",
                "Recurring product themes with supporting review excerpts",
            )
            render_pros_cons(selected.product.asin)

            # Updated dashboard UI: Review Pulse and expandable evidence.
            section(
                "The review pulse",
                "07 / EVIDENCE",
                "A concise read of the cleaned review sample",
            )

            count = selected.sample_review_count
            positive = selected.star_counts[3] + selected.star_counts[4]
            low = selected.star_counts[0] + selected.star_counts[1]
            gap = (
                selected.sample_rating - selected.product.source_rating
                if selected.sample_rating is not None
                else None
            )

            cards = [
                pulse_card(
                    selected.product,
                    "01 / RATING MIX",
                    f"{rating_share(selected, (4, 5))}%" if count else "—",
                    "4–5 star share",
                    f"{positive} of {count} cleaned reviews in this sample gave four or five stars.",
                    0,
                ),
                pulse_card(
                    selected.product,
                    "02 / CRITICAL SHARE",
                    f"{rating_share(selected, (1, 2))}%" if count else "—",
                    "1–2 star share",
                    f"{low} of {count} cleaned reviews in this sample gave one or two stars.",
                    1,
                ),
                pulse_card(
                    selected.product,
                    "03 / RATING CONTEXT",
                    f"{gap:+.2f}" if gap is not None else "—",
                    "Sample versus listing",
                    "Difference between the sampled mean and product-page rating. "
                    "These represent different review populations, not a trust score.",
                    2,
                ),
                pulse_card(
                    selected.product,
                    "04 / REVIEW WINDOW",
                    f"{count:,}",
                    "Reviews available",
                    f"Historical sample from {selected.first_review_date or 'N/A'} "
                    f"to {selected.last_review_date or 'N/A'}.",
                    3,
                ),
            ]

            st.markdown(
                '<div class="rt-pulse-track" '
                'aria-label="Aggregate product review summary">'
                + "".join(cards)
                + "</div>",
                unsafe_allow_html=True,
            )
            st.caption(
                "Hover over a card or focus it with the keyboard "
                "to see how each number is calculated."
            )

            with st.container(key="evidence_panel"):
                st.markdown(
                    '<div class="rt-evidence-intro">'
                    '<span>GO DEEPER / THE SOURCE MATERIAL</span>'
                    '<h3>Want to see every star behind this summary?</h3>'
                    '<p>Open the complete rating pattern and original review excerpts.</p>'
                    '</div>',
                    unsafe_allow_html=True,
                )
                st.button(
                    "Hide the detailed evidence ↑"
                    if st.session_state.get("evidence_open", False)
                    else "Show rating breakdown and original reviews →",
                    on_click=toggle_evidence,
                    key="evidence_button",
                    use_container_width=True,
                )

            if st.session_state.get("evidence_open", False):
                st.markdown(
                    rating_distribution(selected),
                    unsafe_allow_html=True,
                )
                excerpts = recent_reviews(selected.product.asin)
                if excerpts:
                    st.markdown(
                        '<div class="rt-review-heading">'
                        '<div><span>ORIGINAL VOICES</span>'
                        '<h3>From the review sample.</h3></div>'
                        '<span>SCROLL TO EXPLORE →</span>'
                        '</div>',
                        unsafe_allow_html=True,
                    )
                    st.markdown(
                        '<div class="rt-review-track" '
                        'aria-label="Original review excerpts">'
                        + "".join(review_card(review) for review in excerpts)
                        + "</div>",
                        unsafe_allow_html=True,
                    )
                else:
                    st.caption("No review text is available for this product.")
    else:
        with st.container(key="search_zone"):
            st.markdown(
                '<div class="rt-search-intro"><div class="rt-search-intro-copy">'
                '<span>EXPLORE THE CATALOG</span>'
                '<h3>Find your next fit.</h3>'
                '<p>Search by name, ASIN, or simply describe what matters to you.</p></div>'
                f'<div class="rt-search-catalog-count"><strong>{len(products):,}</strong>'
                '<span>products to explore</span></div></div>',
                unsafe_allow_html=True,
            )
            search_col, category_col = st.columns([2.2, 1], gap="medium")
            with search_col:
                restore_input("product_search")
                query = st.text_input(
                    "Product name or ASIN", placeholder="Try ‘a bottle that keeps drinks cold’ or enter an ASIN",
                    key="_product_search", on_change=save_search_input, args=("product_search",),
                )
            with category_col:
                categories = ["All categories"] + sorted({item.category for item in products})
                restore_input("category_filter", "All categories")
                category = st.selectbox(
                    "Category", categories, key="_category_filter",
                    on_change=save_search_input, args=("category_filter",),
                )
            with st.container(key="search_suggestions"):
                st.markdown('<div class="rt-search-quick-label">QUICK IDEAS</div>', unsafe_allow_html=True)
                for column, term in zip(st.columns(3, gap="small"), ("water bottle", "headphones", "hair dryer")):
                    with column:
                        st.button(f"{term.title()} ↗", key=f"search_suggestion_{term}", on_click=set_search_query, args=(term,), use_container_width=True)

        if len(query.strip().split()) >= 4:
            # Preserve BM25 + SBERT hybrid ranking for natural-language queries.
            selected_products = filter_products(products, "", category)
            matches = hybrid_rank_products(selected_products, query, semantic_index(tuple(products)))
        else:
            # Short keywords and exact ASINs retain the existing search path.
            matches = filter_products(products, query, category)
        if not query and category == "All categories":
            # Open with varied catalog photography, away from the featured shelf below.
            showcase_asins = {"B085DVHQ57", "B097CNMZF5", "B0014BYHJE", "B01N6ZJH96", "B00NHQFA1I", "B0D2Z1PJWT", "B00T0C9XRK"}
            candidates = [product for product in matches if product.asin not in showcase_asins and product.image_url]
            browse_categories = (
                "Toys & Games", "Electronics", "Home & Kitchen", "Sports & Outdoors",
                "Beauty & Personal Care", "Baby Products", "Grocery & Gourmet Food", "Automotive",
            )
            category_leads = []
            for category_name in browse_categories:
                category_products = [product for product in candidates if product.category == category_name]
                if category_products:
                    category_leads.append(max(category_products, key=lambda product: product.source_rating_count))
            lead_asins = {product.asin for product in category_leads}
            more_leads = sorted(
                (product for product in candidates if product.asin not in lead_asins),
                key=lambda product: product.source_rating_count, reverse=True,
            )[:max(0, 8 - len(category_leads))]
            leading = category_leads[:8] + more_leads
            leading_asins = {product.asin for product in leading}
            matches = leading + [product for product in matches if product.asin not in leading_asins]
        section("Browse the collection", "01 / PRODUCTS", "Search results and listed ratings from the source catalog")
        with st.expander("Explore by category"):
            st.caption("Choose a category to filter the product results below.")
            category_specs = (
                ("Home & Kitchen", "B085DVHQ57"),
                ("Beauty & Personal Care", "B097CNMZF5"),
                ("Electronics", "B0CCYM3F1V"),
                ("Clothing, Shoes & Jewelry", "B0014BYHJE"),
                ("Toys & Games", "B00NHQFA1I"),
            )
            category_tiles = []
            for category_name, preferred_asin in category_specs:
                representative = products_by_asin.get(preferred_asin)
                if representative is None or representative.category != category_name:
                    representative = next((product for product in products if product.category == category_name and product.image_url), None)
                if representative:
                    category_tiles.append((category_name, representative))
            if category_tiles:
                with st.container(key="category_tiles"):
                    for column, (category_name, representative), index in zip(st.columns(len(category_tiles), gap="small"), category_tiles, range(len(category_tiles))):
                        with column:
                            category_card(category_name, representative, index)
        st.markdown(f'<div class="rt-search-count"><strong>{len(matches):,}</strong> matching products <span>↓ &nbsp; OPEN A PRODUCT FOR REVIEW EVIDENCE</span></div>', unsafe_allow_html=True)
        if not matches:
            st.markdown('<div class="rt-search-empty"><strong>No match in this review snapshot.</strong><p>Try a shorter product name or another category.</p></div>', unsafe_allow_html=True)
            st.button("Clear search →", on_click=set_search_query, args=("",))
        else:
            visible_count = min(len(matches), st.session_state["browse_visible_count"])
            visible_products = matches[:visible_count]
            with st.container(key="browse_grid"):
                for start in range(0, len(visible_products), 4):
                    for column, product, index in zip(
                        st.columns(4, gap="medium"),
                        visible_products[start:start + 4],
                        range(start, min(start + 4, visible_count)),
                    ):
                        with column:
                            browse_card(product, index)
            if visible_count < len(matches):
                st.button(f"Load more products · {len(matches) - visible_count:,} remaining ↓", key="load_more_products", on_click=load_more_products, use_container_width=True)
            options = matches[:60]
            if st.session_state.get("selected_product") not in options:
                st.session_state["selected_product"] = options[0]
            if st.session_state.get("_selected_product") not in options:
                st.session_state["_selected_product"] = st.session_state["selected_product"]
            chosen = st.selectbox(
                "Explore another matching product", options, format_func=product_label,
                key="_selected_product", on_change=save_input, args=("selected_product",),
            )
            if chosen is not None:
                st.button("Open product evidence →", on_click=open_featured, args=(chosen,), type="primary")

        st.markdown(
            '<div class="rt-curated-head"><div class="rt-curated-emblem" aria-hidden="true">★</div>'
            '<div class="rt-curated-label"><span>THE REVIEWTRUST EDIT / 01</span><h3>On the <em>podium.</em></h3>'
            '<p>Featured finds and standout review scores, ready for a closer look.</p></div>'
            '<span class="rt-curated-side">FEATURED FINDS<br>BEST REVIEWED</span></div>',
            unsafe_allow_html=True,
        )
        featured_tab, shortlist_tab = st.tabs(["Featured products", "Best reviewed picks"])
        with featured_tab:
            featured_asins = ("B085DVHQ57", "B097CNMZF5", "B0014BYHJE", "B01N6ZJH96")
            featured = [products_by_asin[asin] for asin in featured_asins if asin in products_by_asin]
            featured_categories = {product.category for product in featured}
            for product in products:
                if len(featured) < 4 and product.category not in featured_categories:
                    featured.append(product)
                    featured_categories.add(product.category)
                if len(featured) == 4:
                    break
            if len(featured) < 4:
                featured.extend(product for product in products if product not in featured)
                featured = featured[:4]
            st.markdown('<div class="rt-curated-note">Start with a product, then see the review sample behind its rating.</div>', unsafe_allow_html=True)
            with st.container(key="spotlight"):
                left, center, right = st.columns([1, 1.05, 1], gap="large")
                with left:
                    featured_card(featured[0], 0)
                with center:
                    featured_card(featured[1], 1)
                    featured_card(featured[2], 2)
                with right:
                    st.markdown(
                        '<div class="rt-editorial-note"><span>✦ / FEATURED FINDS</span>'
                        '<h4>Good finds deserve a closer look.</h4>'
                        '<p>Open any product to see the review sample and the evidence behind it.</p></div>',
                        unsafe_allow_html=True,
                    )
                    featured_card(featured[3], 3)
        with shortlist_tab:
            st.markdown('<div class="rt-shortlist-note"><strong>What makes a pick?</strong> High sampled ratings backed by at least 50 reviews. Open any card to see the underlying evidence.</div>', unsafe_allow_html=True)
            candidate_asins = ("B085DVHQ57", "B0D2Z1PJWT", "B097CNMZF5", "B0014BYHJE", "B00NHQFA1I", "B01N6ZJH96", "B00T0C9XRK")
            candidate_snapshots = [snapshot(asin) for asin in candidate_asins if asin in products_by_asin]
            eligible = [item for item in candidate_snapshots if item and item.sample_rating is not None and item.sample_review_count >= 50 and item.sample_rating >= 4.5 and item.product.source_rating >= 4.4]
            eligible.sort(key=lambda item: (item.sample_rating, item.product.source_rating_count), reverse=True)
            best_buy = []
            seen_categories = set()
            for item in eligible:
                if item.product.category not in seen_categories:
                    best_buy.append(item)
                    seen_categories.add(item.product.category)
                if len(best_buy) == 4:
                    break
            with st.container(key="best_buy"):
                if len(best_buy) == 4:
                    left, center, right = st.columns([1, 1.05, 1], gap="large")
                    with left:
                        best_buy_card(best_buy[0], 0)
                    with center:
                        best_buy_card(best_buy[1], 1)
                        best_buy_card(best_buy[2], 2)
                    with right:
                        st.markdown(
                            '<div class="rt-editorial-note"><span>★ / BEST REVIEWED</span>'
                            '<h4>Scores with a story behind them.</h4>'
                            '<p>These picks meet the review-sample rule. Explore the evidence before deciding.</p></div>',
                            unsafe_allow_html=True,
                        )
                        best_buy_card(best_buy[3], 3)
                elif best_buy:
                    for column, item, index in zip(st.columns(len(best_buy), gap="medium"), best_buy, range(len(best_buy))):
                        with column:
                            best_buy_card(item, index)
                else:
                    st.caption("No products meet the current shortlist rule in this catalog.")
            with st.expander("How the shortlist is selected"):
                st.write("A product needs at least 50 reviews in our cleaned sample, a sample mean of 4.5 or higher, and a product-page rating of 4.4 or higher. We show one candidate per category and rank by sample mean, then listed rating count. These are review-based picks; price, product quality testing, and future trust signals are not included.")
elif st.session_state["page"] == "Compare":
    section("Compare products", "02 / COMPARE", "Use Amazon links or choose directly from the catalog")
    st.markdown('<div id="quick-compare" class="rt-jump-target"></div>', unsafe_allow_html=True)
    with st.container(key="hero_compare"):
        st.markdown('<div class="rt-hero-compare-label"><span>QUICK COMPARE / TWO PRODUCTS</span><strong>Two links. One clearer choice.</strong><p>Paste two Amazon product links. We’ll match them to products in our review dataset.</p></div>', unsafe_allow_html=True)
        left_picker, versus, right_picker = st.columns([1, .17, 1], vertical_alignment="bottom", gap="small")
        with left_picker:
            restore_input("amazon_link_a")
            link_a = st.text_input(
                "AMAZON LINK A", placeholder="https://www.amazon.com/dp/...",
                key="_amazon_link_a", on_change=save_input, args=("amazon_link_a",),
            )
        with versus:
            st.markdown('<div class="rt-vs">VS</div>', unsafe_allow_html=True)
        with right_picker:
            restore_input("amazon_link_b")
            link_b = st.text_input(
                "AMAZON LINK B", placeholder="https://www.amazon.com/dp/...",
                key="_amazon_link_b", on_change=save_input, args=("amazon_link_b",),
            )
        submitted = st.button("Compare these products →", key="compare_submit", use_container_width=True, type="primary")
        st.button("Try an example pair", on_click=fill_example_links, key="example_links")
        if submitted:
            asin_a, asin_b = amazon_asin(link_a), amazon_asin(link_b)
            if not asin_a or not asin_b:
                st.error("Paste two full Amazon product links, such as amazon.com/dp/B085DVHQ57. Short redirect links cannot be matched here.")
            elif asin_a == asin_b:
                st.error("Choose two different Amazon products to compare.")
            elif asin_a not in products_by_asin or asin_b not in products_by_asin:
                missing = [asin for asin in (asin_a, asin_b) if asin not in products_by_asin]
                st.warning(f"This review snapshot does not contain: {', '.join(missing)}. Try another Amazon product link or the example pair.")
            else:
                st.session_state["compare_left_product"] = products_by_asin[asin_a]
                st.session_state["compare_right_product"] = products_by_asin[asin_b]
                st.session_state["_compare_left_product"] = st.session_state["compare_left_product"]
                st.session_state["_compare_right_product"] = st.session_state["compare_right_product"]
                st.success("Products found. Their comparison is shown below.")
    st.markdown('<div class="rt-compare-or"><span>OR</span> Choose products from the catalog</div>', unsafe_allow_html=True)
    left_col, right_col = st.columns(2, gap="large")
    if st.session_state.get("compare_left_product") not in products:
        st.session_state["compare_left_product"] = products_by_asin.get("B085DVHQ57", products[0])
    if st.session_state.get("_compare_left_product") not in products:
        st.session_state["_compare_left_product"] = st.session_state["compare_left_product"]
    with left_col:
        left_product = st.selectbox(
            "Product 01", products, format_func=product_label,
            key="_compare_left_product", on_change=save_input, args=("compare_left_product",),
        )
    if left_product is None:
        st.info("Choose a first product to compare.")
    else:
        right_index = next((i for i, item in enumerate(products) if item.asin != left_product.asin and item.category == left_product.category), next((i for i, item in enumerate(products) if item.asin != left_product.asin), 0))
        if st.session_state.get("compare_right_product") not in products:
            example_right = products_by_asin.get("B0D2Z1PJWT")
            st.session_state["compare_right_product"] = example_right if example_right and example_right.asin != left_product.asin else products[right_index]
        if st.session_state.get("_compare_right_product") not in products:
            st.session_state["_compare_right_product"] = st.session_state["compare_right_product"]
        with right_col:
            right_product = st.selectbox(
                "Product 02", products, format_func=product_label,
                key="_compare_right_product", on_change=save_input, args=("compare_right_product",),
            )
        if right_product is None:
            st.info("Choose a second product to compare.")
        elif left_product.asin == right_product.asin:
            st.warning("Choose a different second product to compare.")
        else:
            render_compare_summary(left_product, right_product)
