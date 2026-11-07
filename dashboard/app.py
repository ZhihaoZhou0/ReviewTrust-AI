"""ReviewTrust's product evidence desk: real sample data, clearly labeled."""
from __future__ import annotations

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
<div class="rt-topline"><div class="rt-wordmark"><span class="rt-symbol">✦</span> ReviewTrust<span style="color:#7767DF">.</span></div><div class="rt-topnote">Discover the story behind the stars &nbsp; / &nbsp; Review evidence, made clear</div></div>
""", unsafe_allow_html=True)
st.markdown(f"<style>{Path(__file__).with_name('styles.css').read_text()}</style>", unsafe_allow_html=True)

@st.cache_data(ttl=120, show_spinner=False)
def catalog() -> list[Product]:
    return load_catalog()

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

def stat(label: str, value: str, detail: str) -> None:
    st.markdown(f'<div class="rt-stat"><div class="label">{escape(label)}</div><div class="value">{escape(value)}</div><div class="detail">{escape(detail)}</div></div>', unsafe_allow_html=True)

def compare_from_explore(product: Product) -> None:
    st.session_state["compare_left_product"] = product
    st.session_state["view"] = "Compare"

def open_featured(product: Product) -> None:
    st.session_state["product_search"] = product.title
    st.session_state["category_filter"] = "All categories"
    st.session_state["selected_product"] = product
    st.session_state["view"] = "Explore"

def open_category(category: str) -> None:
    st.session_state["browse_category"] = category

def fill_example_links() -> None:
    st.session_state["amazon_link_a"] = "https://www.amazon.com/dp/B085DVHQ57"
    st.session_state["amazon_link_b"] = "https://www.amazon.com/dp/B0D2Z1PJWT"

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
        f'<article class="rt-feature-card size-{index}"><div class="rt-feature-image {tones[index % 4]}"><span class="rt-feature-tag">{escape(product.category)}</span>{product_image(product)}'
        f'<div class="rt-feature-overlay"><span>{product.source_rating:.1f} ★ listed rating</span></div></div>'
        f'<div class="rt-feature-body"><h3 title="{escape(product.title, quote=True)}">{escape(shorten(product.title, width=78, placeholder="…"))}</h3><div class="rt-feature-meta">{product.source_rating_count:,} ratings listed on product page</div></div></article>',
        unsafe_allow_html=True,
    )
    st.button("View review evidence →", key=f"featured_{product.asin}", on_click=open_featured, args=(product,), use_container_width=True)

def browse_card(product: Product, index: int) -> None:
    tones = ("lavender", "citron", "apricot", "sky")
    st.markdown(
        f'<article class="rt-browse-card"><div class="rt-browse-image {tones[index % 4]}">'
        f'<span class="rt-browse-rating">★ {product.source_rating:.1f}</span>{product_image(product)}</div>'
        f'<div class="rt-browse-info"><h3 title="{escape(product.title, quote=True)}">{escape(shorten(product.title, width=56, placeholder="…"))}</h3>'
        f'<div>{escape(product.category)} · {product.source_rating_count:,} listed ratings</div></div></article>',
        unsafe_allow_html=True,
    )
    st.button("Inspect reviews ↗", key=f"browse_{product.asin}", on_click=open_featured, args=(product,), use_container_width=True)

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
        f'<article class="rt-best-card"><div class="rt-best-image tone-{index}">'
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

    st.caption(
        f"Based on {result.n_text_reviews:,} text reviews analyzed "
        "using B2 aspect extraction."
    )

    pros_col, cons_col = st.columns(2, gap="large")

    def render_aspects(aspects: list, positive: bool) -> None:
        heading = "What reviewers liked" if positive else "What reviewers disliked"
        st.markdown(f"**{heading}**")

        if not aspects:
            st.caption(
                "No qualifying positive themes were extracted."
                if positive
                else "No qualifying negative themes were extracted."
            )
            return

        for aspect in aspects[:5]:
            label = str(aspect.get("label", "Other"))
            count = int(aspect.get("review_count", 0))
            support = str(aspect.get("support_level", "unknown"))

            with st.expander(f"{label} · {count} reviews"):
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

    with pros_col:
        render_aspects(result.pros, positive=True)

    with cons_col:
        render_aspects(result.cons, positive=False)




def compare_card(item: ProductSnapshot, number: str) -> None:
    product = item.product
    reliability = reliability_results().get(product.asin)

    # Updated dashboard UI: product image, identity, and Amazon link.
    st.markdown(
        f'<div class="rt-compare-card">'
        f'<div class="rt-compare-identity">'
        f'<div class="rt-compare-product-image">{product_image(product)}</div>'
        f'<div>'
        f'<span class="number">PRODUCT {escape(number)}</span>'
        f'<h3>{escape(product.title)}</h3>'
        f'<div class="meta">{escape(product.category)}'
        f' &nbsp; / &nbsp; {escape(product.asin)}</div>'
        f'<a class="rt-amazon-link" '
        f'href="https://www.amazon.com/dp/{escape(product.asin, quote=True)}" '
        f'target="_blank" rel="noopener noreferrer">'
        f'View Amazon listing ↗</a>'
        f'</div></div>',
        unsafe_allow_html=True,
    )

    # Original product and sample metrics.
    rows = [
        ("Product-page rating", f"{product.source_rating:.1f} / 5"),
        (
            "Rating from sample",
            f"{item.sample_rating:.2f} / 5"
            if item.sample_rating is not None else "No reviews",
        ),
        ("Reviews in sample", f"{item.sample_review_count:,}"),
        ("Product-page rating count", f"{product.source_rating_count:,}"),
    ]

    # B1: Review reliability analysis.
    if reliability is not None:
        delta = reliability.adjusted_rating - reliability.original_rating

        rows.extend([
            ("Trust-adjusted rating", f"{reliability.adjusted_rating:.2f} / 5"),
            ("B1 rating change", f"{delta:+.3f}"),
            (
                "Reviews adjusted",
                f"{reliability.adjusted_review_count:,} "
                f"({reliability.adjusted_review_percentage:.1f}%)",
            ),
        ])
    else:
        rows.append(("Trust-adjusted rating", "Unavailable"))

    for label, value in rows:
        st.markdown(
            f'<div class="rt-compare-row">'
            f'<span>{escape(label)}</span>'
            f'<strong>{escape(value)}</strong>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.markdown("</div>", unsafe_allow_html=True)



try:
    products = catalog()
except (psycopg.Error, OSError, ValueError):
    st.error("The product database is unavailable. Start PostgreSQL with 'docker compose up -d --wait db' and run 'python3 pipeline/load_snapshot.py' from the project root.")
    st.stop()
if not products:
    st.warning("The catalog is empty. Load the A1 snapshot to explore products.")
    st.stop()
products_by_asin = {product.asin: product for product in products}
if "view" not in st.session_state:
    st.session_state["view"] = "Explore"
hero_asins = ("B085DVHQ57", "B097CNMZF5", "B0014BYHJE")
hero_products = [products_by_asin[asin] for asin in hero_asins if asin in products_by_asin]
hero_products.extend(product for product in products if product.image_url and product not in hero_products)
hero_products = hero_products[:3]
hero_visual = ''.join(f'<div class="rt-hero-product item-{index}">{product_image(product)}</div>' for index, product in enumerate(hero_products))
st.markdown(
    '<div class="rt-intro"><div class="rt-hero-copy"><div class="rt-eyebrow">REVIEWTRUST / PRODUCT INTELLIGENCE</div>'
    '<h1>Know more.<br><em>Choose better.</em></h1>'
    '<p>Paste two Amazon product links. We turn the review sample into a clear, side-by-side decision.</p>'
    '<div class="rt-hero-prompt">REAL REVIEWS &nbsp; · &nbsp; CLEAR CONTEXT &nbsp; · &nbsp; ONE BETTER DECISION</div></div>'
    f'<div class="rt-hero-art" aria-hidden="true"><div class="rt-hero-platform"></div>{hero_visual}'
    '<div class="rt-art-sticker">A<br>VS<br>B</div></div></div>',
    unsafe_allow_html=True,
)
with st.container(key="hero_compare"):
    st.markdown('<div class="rt-hero-compare-label"><span>START A COMPARISON</span><strong>Two links. One clearer choice.</strong><p>Amazon product URLs are matched against the products in our review dataset.</p></div>', unsafe_allow_html=True)
    with st.form("amazon_compare_form", border=False):
        left_picker, versus, right_picker = st.columns([1, .08, 1], vertical_alignment="bottom", gap="small")
        with left_picker:
            link_a = st.text_input("AMAZON LINK A", placeholder="https://www.amazon.com/dp/...", key="amazon_link_a")
        with versus:
            st.markdown('<div class="rt-vs">VS</div>', unsafe_allow_html=True)
        with right_picker:
            link_b = st.text_input("AMAZON LINK B", placeholder="https://www.amazon.com/dp/...", key="amazon_link_b")
        submitted = st.form_submit_button("Compare these products →", use_container_width=True, type="primary")
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
            st.session_state["view"] = "Compare"
            st.success("Products found. Their review evidence is ready below.")
st.markdown('<div class="rt-value-strip"><span>✳ &nbsp; REAL REVIEW EVIDENCE</span><span>◇ &nbsp; CLEAR SAMPLE CONTEXT</span><span>↗ &nbsp; SIDE-BY-SIDE COMPARISON</span></div>', unsafe_allow_html=True)

section("Explore by category", "01 / CATEGORIES", "Browse products from the source catalog")
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

section("A closer look starts here", "02 / FEATURED PRODUCTS", "Real products from our review dataset")
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
with st.container(key="spotlight"):
    first, middle, last = st.columns(3, gap="medium")
    with first:
        featured_card(featured[0], 0)
    with middle:
        if len(featured) > 1:
            featured_card(featured[1], 1)
        if len(featured) > 3:
            featured_card(featured[2], 2)
    with last:
        st.markdown('<div class="rt-spotlight-copy"><div class="rt-eyebrow">THE STORY BEHIND THE STARS</div><h3>Every product has more to tell.</h3><p>Start with a product, then see the review sample behind its rating.</p></div>', unsafe_allow_html=True)
        if len(featured) > 2:
            featured_card(featured[-1], 3)

section("Best reviewed picks", "03 / THE SHORTLIST", "Strong review samples across different categories")
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
    if best_buy:
        for column, item, index in zip(st.columns(len(best_buy), gap="medium"), best_buy, range(len(best_buy))):
            with column:
                best_buy_card(item, index)
    else:
        st.caption("No products meet the current shortlist rule in this catalog.")
with st.expander("How the shortlist is selected"):
    st.write("A product needs at least 50 reviews in our cleaned sample, a sample mean of 4.5 or higher, and a product-page rating of 4.4 or higher. We show one candidate per category and rank by sample mean, then listed rating count. These are review-based picks; price, product quality testing, and future trust signals are not included.")
section("Browse the collection", "04 / EXPLORE PRODUCTS", "Product images and listed ratings come from the source catalog")
browse_categories = ["All products"] + [name for name in ("Beauty & Personal Care", "Home & Kitchen", "Electronics", "Clothing, Shoes & Jewelry", "Toys & Games") if any(product.category == name for product in products)]
browse_category = st.pills("Product category", browse_categories, default="All products", key="browse_category", required=True, label_visibility="collapsed")
if browse_category == "All products":
    picks = [products_by_asin[asin] for asin in ("B085DVHQ57", "B097CNMZF5", "B0014BYHJE", "B01N6ZJH96", "B00NHQFA1I", "B0D2Z1PJWT", "B00T0C9XRK") if asin in products_by_asin]
    for product in products:
        if len(picks) >= 8:
            break
        if product not in picks and product.image_url:
            picks.append(product)
else:
    picks = [product for product in products if product.category == browse_category and product.image_url][:8]
    if not picks:
        picks = [product for product in products if product.category == browse_category][:8]
with st.container(key="browse_grid"):
    for start in range(0, len(picks), 4):
        for column, product, index in zip(st.columns(4, gap="medium"), picks[start:start + 4], range(start, min(start + 4, len(picks)))):
            with column:
                browse_card(product, index)

st.markdown('<div class="rt-workspace-intro"><div class="rt-eyebrow">YOUR RESEARCH DESK</div><h2>Shop with the full story.</h2><p>Search the catalog, inspect the review sample, or compare two products.</p></div>', unsafe_allow_html=True)
st.segmented_control("Workspace", ["Explore", "Compare"], key="view", selection_mode="single", required=True, label_visibility="collapsed")

if st.session_state["view"] == "Explore":
    section("Find your product", "05 / SEARCH", "Search by name or product ID")
    search_col, category_col = st.columns([2.2, 1], gap="medium")
    with search_col:
        query = st.text_input("Product name or ASIN", placeholder="Try headphones, water bottle, or an ASIN", key="product_search")
    with category_col:
        categories = ["All categories"] + sorted({item.category for item in products})
        category = st.selectbox("Category", categories, key="category_filter")
    matches = filter_products(products, query, category)
    st.caption(f"{len(matches):,} products found" + (" · showing the first 60" if len(matches) > 60 else ""))
    if not matches:
        st.warning("No products match. Try a shorter search or another category.")
    else:
        if st.session_state.get("selected_product") not in matches[:60]:
            st.session_state.pop("selected_product", None)
        chosen = st.selectbox("Choose a product to inspect", matches[:60], format_func=product_label, key="selected_product")
        selected = snapshot(chosen.asin)
        if selected is not None:
            section("The product at a glance", "06 / INSPECT", "Source facts and sampled evidence")
            image_col, identity_col = st.columns([.85, 2.15], gap="large")
            with image_col:
                if selected.product.image_url and selected.product.image_url.startswith(("https://", "http://")):
                    st.image(selected.product.image_url, width="stretch")
            with identity_col:
                st.markdown(f'<div class="rt-product-head"><div class="rt-eyebrow">{escape(selected.product.category)} &nbsp; / &nbsp; {escape(selected.product.asin)}</div><h2>{escape(selected.product.title)}</h2><p>Review sample: {escape(str(selected.first_review_date or "N/A"))} to {escape(str(selected.last_review_date or "N/A"))}</p></div>', unsafe_allow_html=True)
                st.button("Compare this product →", on_click=compare_from_explore, args=(selected.product,), type="primary")
            one, two, three = st.columns(3, gap="medium")
            with one: stat("Product-page rating", f"{selected.product.source_rating:.1f} / 5", f"{selected.product.source_rating_count:,} ratings listed on product page")
            with two: stat("Rating from sample", f"{selected.sample_rating:.2f} / 5" if selected.sample_rating is not None else "—", "Mean of cleaned reviews in this dataset")
            with three: stat("Reviews in sample", f"{selected.sample_review_count:,}", "Historical review records available here")
            
            # B1: Product-level review reliability analysis
            reliability = reliability_results().get(selected.product.asin)

            if reliability is not None:
                st.markdown(
                    '<div class="rt-micro" style="margin-top:1.2rem">'
                    'B1 / REVIEW RELIABILITY ANALYSIS'
                    '</div>',
                    unsafe_allow_html=True,
                )

                trust_one, trust_two, trust_three = st.columns(3, gap="medium")

                with trust_one:
                    stat(
                        "Trust-adjusted rating",
                        f"{reliability.adjusted_rating:.2f} / 5",
                        f"Original B1 sample rating: {reliability.original_rating:.2f}",
                    )

                with trust_two:
                    rating_delta = (
                        reliability.adjusted_rating - reliability.original_rating
                    )
                    stat(
                        "Rating change",
                        f"{rating_delta:+.3f}",
                        "Adjusted rating minus original B1 sample rating",
                    )

                with trust_three:
                    stat(
                        "Reviews adjusted",
                        f"{reliability.adjusted_review_count:,}",
                        f"{reliability.adjusted_review_percentage:.1f}% "
                        "of B1 analyzed reviews",
                    )

                st.caption(
                    "B1 uses review reliability signals to adjust the contribution "
                    "of certain reviews. The adjusted rating is an experimental "
                    "sample-based metric, not an official Amazon rating or a "
                    "determination that a review is fraudulent."
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
    section("Compare two products", "05 / COMPARE", "One clear view of the same evidence")
    st.caption("Choose two distinct products. Ratings and counts below retain their original source labels.")
    left_col, right_col = st.columns(2, gap="large")
    if st.session_state.get("compare_left_product") not in products:
        st.session_state["compare_left_product"] = products[0]
    with left_col:
        left_product = st.selectbox("Product 01", products, index=None, format_func=product_label, key="compare_left_product")
    right_index = next((i for i, item in enumerate(products) if item.asin != left_product.asin and item.category == left_product.category), next((i for i, item in enumerate(products) if item.asin != left_product.asin), 0))
    if st.session_state.get("compare_right_product") not in products:
        st.session_state["compare_right_product"] = products[right_index]
    with right_col:
        right_product = st.selectbox("Product 02", products, index=None, format_func=product_label, key="compare_right_product")
    if left_product.asin == right_product.asin:
        st.warning("Choose a different second product to compare.")
    else:
        left_snapshot, right_snapshot = snapshot(left_product.asin), snapshot(right_product.asin)
        if left_snapshot and right_snapshot:
            with left_col: compare_card(left_snapshot, "01")
            with right_col: compare_card(right_snapshot, "02")
            st.markdown('<div class="rt-note">Sample ratings summarize only the cleaned reviews available here. A higher sample mean does not establish that one product is more trustworthy.</div>', unsafe_allow_html=True)
            section("Rating patterns", "06 / EVIDENCE", "Review counts by star rating in each sample")
            chart_left, chart_right = st.columns(2, gap="medium")
            with chart_left:
                st.markdown(rating_distribution(left_snapshot), unsafe_allow_html=True)
            with chart_right:
                st.markdown(rating_distribution(right_snapshot), unsafe_allow_html=True)

st.markdown('<div class="rt-future"><div><strong>Trust signals and recurring themes</strong><p>Deeper review analysis is being developed. When available, this desk will show weighted ratings, unusual patterns, and evidence-backed pros and cons.</p></div><span>COMING IN A LATER RELEASE ↗</span></div><div class="rt-footer">DataHive Amazon Reviews sample &nbsp; / &nbsp; Historical data, not live Amazon ratings &nbsp; / &nbsp; Review patterns are not fraud verdicts</div>', unsafe_allow_html=True)
