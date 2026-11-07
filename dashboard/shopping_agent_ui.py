"""Streamlit presentation for the shopping agent; the workflow is unchanged."""

from __future__ import annotations

import base64
import re
from html import escape
from pathlib import Path
from typing import TYPE_CHECKING

import streamlit as st

from shopping_agent.workflow import run_workflow

if TYPE_CHECKING:
    from dashboard.data_access import Product


_RABBIT = Path(__file__).with_name("assets") / "shopping-agent-rabbit.svg"


def _change_count(delta: int) -> None:
    st.session_state["agent_product_count"] = max(
        1, min(5, st.session_state.get("agent_product_count", 2) + delta)
    )


def _image(product: Product | None) -> str:
    url = product.image_url if product else None
    if url and url.startswith(("https://", "http://")):
        return f'<img src="{escape(url, quote=True)}" alt="Product photo" loading="lazy">'
    return '<span class="rt-agent-no-image">Product image unavailable</span>'


def _aspects(values: list[dict], empty: str) -> str:
    if not values:
        return f'<span class="rt-agent-empty">{escape(empty)}</span>'
    return "".join(
        f'<span class="rt-agent-aspect">{escape(str(value.get("label") or value.get("aspect") or "Review theme"))}</span>'
        for value in values[:3]
    )


def _card(item: dict, product: Product | None) -> str:
    asin = str(item["asin"])
    listing = ""
    if re.fullmatch(r"[A-Z0-9]{10}", asin):
        listing = f'<a href="https://www.amazon.com/dp/{asin}" target="_blank" rel="noopener noreferrer">View on Amazon ↗</a>'
    category = product.category if product else "Review dataset product"
    badge = "BEST MATCH" if item["rank"] == 1 else f'MATCH {item["rank"]:02d}'
    priorities = item.get("matched_priorities", [])
    matched = (
        '<div class="rt-agent-matches"><span>Matched priorities</span>'
        + "".join(f"<b>{escape(str(value))}</b>" for value in priorities[:4])
        + "</div>"
        if priorities else ""
    )
    return (
        '<article class="rt-agent-product-card"><div class="rt-agent-product-image">'
        f'<span class="rt-agent-rank">{badge}</span>{_image(product)}</div>'
        '<div class="rt-agent-product-copy">'
        f'<span class="rt-agent-category">{escape(category)}</span>'
        f'<h3>{escape(str(item["title"]))}</h3>'
        '<div class="rt-agent-rating">'
        f'<strong>★ {float(item["rating_used"]):.2f}<small> / 5</small></strong>'
        f'<span>{escape(str(item["rating_source"]))}</span></div>'
        f'{matched}<div class="rt-agent-themes">'
        f'<div><b>What people like</b>{_aspects(item.get("pros", []), "No recurring positive theme")}</div>'
        f'<div><b>Worth knowing</b>{_aspects(item.get("cons", []), "No recurring negative theme")}</div>'
        f'</div><div class="rt-agent-card-footer"><span>Review-backed match</span>{listing}</div>'
        '</div></article>'
    )


def _render_result(result: dict, products_by_asin: dict[str, Product]) -> None:
    if result.get("status") != "completed":
        st.error(result.get("message", "The comparison could not be completed."))
        for error in result.get("cart_errors", []):
            st.caption(str(error.get("reason", error)))
        return

    st.markdown(
        '<div class="rt-agent-result-head"><span>YOUR SHORTLIST</span>'
        '<h3>Thoughtful matches, backed by reviews.</h3>'
        f'<p>{escape(str(result["message"]))}</p></div>',
        unsafe_allow_html=True,
    )
    if result.get("model_warning"):
        st.warning(
            "Inkling is unavailable, so explicit requirements were parsed locally. "
            "Review the extracted constraints before relying on the result."
        )
    with st.expander("Requirements used for this comparison"):
        st.json(result["preferences"])

    recommendations = result.get("recommendations", [])
    if not recommendations:
        st.warning(result["message"])
    else:
        columns = st.columns(2, gap="medium")
        for index, item in enumerate(recommendations):
            with columns[index % 2]:
                st.markdown(_card(item, products_by_asin.get(item["asin"])), unsafe_allow_html=True)
                if item.get("citations"):
                    with st.expander(f"Read review evidence · {item['rank']}"):
                        for citation in item["citations"]:
                            quote = str(citation["quote"]).strip()
                            if len(quote) > 420:
                                quote = quote[:417].rsplit(" ", 1)[0] + "..."
                            st.markdown(f"> {escape(quote)}")
                            st.caption(
                                f"{citation['aspect']} · Review {citation['review_id']} · "
                                f"{citation.get('stars', 'N/A')}/5 stars"
                            )

    with st.expander("Hard-requirement checks"):
        for item in result.get("eligibility", []):
            icon = {"eligible": "✅", "ineligible": "⛔", "unknown": "⚠️"}[item["status"]]
            st.markdown(f"{icon} **{item['asin']} — {item['status'].title()}**")
            st.caption(item["reason"])
    for warning in result.get("analysis_warnings", []):
        st.caption(warning)
    for error in result.get("cart_errors", []):
        st.caption(f"Skipped input: {error.get('reason', error)}")


def render_shopping_agent(products: list[Product]) -> None:
    """Show a conversational comparison for one to five products."""
    st.session_state.setdefault("agent_product_count", 2)
    rabbit_data = base64.b64encode(_RABBIT.read_bytes()).decode("ascii")
    products_by_asin = {product.asin: product for product in products}

    with st.container(key="agent_panel"):
        st.markdown(
            '<div class="rt-agent-hero"><div class="rt-agent-hero-copy">'
            '<span class="rt-agent-eyebrow">✳ YOUR PERSONAL SHOPPING GUIDE</span>'
            '<h2>Find the right fit, <em>with a little help.</em></h2>'
            '<p>Tell our guide what matters to you. We will check your must-haves first, '
            'then compare real review evidence for the products you choose.</p>'
            '<div class="rt-agent-hero-note"><span class="rt-agent-online"></span>'
            'Ready when you are <span>·</span> 1–5 products</div></div>'
            f'<div class="rt-agent-mascot"><div class="rt-agent-halo"></div><img src="data:image/svg+xml;base64,{rabbit_data}" '
            'alt="A friendly rabbit shopping guide wearing a headset"></div></div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="rt-agent-step"><span>01 / TELL US WHAT MATTERS</span>'
            '<h3>Start a conversation</h3><p>Write naturally. Include deal-breakers, '
            'favorite features, or how you plan to use the product.</p></div>'
            '<div class="rt-agent-guide-message"><span class="rt-agent-guide-avatar">✳</span>'
            '<div><strong>ReviewTrust guide</strong><p>Hi there! What are you shopping for today?</p></div></div>',
            unsafe_allow_html=True,
        )

        count = st.session_state["agent_product_count"]
        with st.form("personalized_shopping_agent"):
            need = st.text_area(
                "Your message",
                placeholder="For example: I need AA batteries for a wireless mouse. Battery life matters most, and I do not want AAA batteries.",
                key="agent_need", label_visibility="collapsed",
            )
            st.markdown(
                '<div class="rt-agent-step rt-agent-product-step"><span>02 / ADD YOUR OPTIONS</span>'
                '<h3>Products to compare</h3><p>Paste Amazon links for products in our review dataset.</p></div>',
                unsafe_allow_html=True,
            )
            fields = st.columns(2, gap="medium")
            links = []
            for index in range(count):
                with fields[index % 2]:
                    st.markdown(
                        f'<div class="rt-agent-input-label"><span>0{index + 1}</span> PRODUCT LINK</div>',
                        unsafe_allow_html=True,
                    )
                    links.append(st.text_input(
                        f"Amazon product {index + 1}",
                        placeholder="https://www.amazon.com/dp/...",
                        key=f"agent_link_{index}", label_visibility="collapsed",
                    ))
            controls = st.columns([7, 1, 1], vertical_alignment="center")
            with controls[0]:
                st.caption(f"{count} product{'s' if count != 1 else ''} selected · Add up to five")
            with controls[1]:
                st.form_submit_button("−", key="agent_remove_product", help="Remove a product",
                                      disabled=count == 1, on_click=_change_count, args=(-1,), use_container_width=True)
            with controls[2]:
                st.form_submit_button("+", key="agent_add_product", help="Add a product",
                                      disabled=count == 5, on_click=_change_count, args=(1,), use_container_width=True)
            submitted = st.form_submit_button(
                "Find my best match  →", type="primary", use_container_width=True
            )

        if submitted:
            with st.spinner("Checking requirements and review evidence..."):
                st.session_state["shopping_agent_result"] = run_workflow(links, need)
        if result := st.session_state.get("shopping_agent_result"):
            _render_result(result, products_by_asin)
