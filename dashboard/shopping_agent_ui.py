"""Streamlit rendering for the personalized AI Shopping Agent."""

from __future__ import annotations

from html import escape

import streamlit as st

from shopping_agent.workflow import run_workflow


def _render_aspect_summary(title: str, aspects: list[dict], empty: str) -> None:
    st.markdown(f"**{title}**")
    if not aspects:
        st.caption(empty)
        return
    for aspect in aspects:
        label = str(aspect.get("label") or aspect.get("aspect") or "Review theme")
        count = aspect.get("review_count") or aspect.get("count")
        suffix = f" · {int(count)} reviews" if isinstance(count, (int, float)) else ""
        st.markdown(f"- {escape(label)}{suffix}")


def _render_result(result: dict) -> None:
    status = result.get("status")
    if status != "completed":
        st.error(result.get("message", "The comparison could not be completed."))
        for error in result.get("cart_errors", []):
            st.caption(str(error.get("reason", error)))
        return

    if result.get("model_warning"):
        st.warning(
            "Inkling is unavailable, so explicit requirements were parsed locally. "
            "Review the extracted constraints before relying on the result."
        )

    preferences = result["preferences"]
    with st.expander("Requirements used for this comparison"):
        st.json(preferences)

    recommendations = result.get("recommendations", [])
    if not recommendations:
        st.warning(result["message"])
    else:
        st.success(result["message"])
        for item in recommendations:
            with st.container(border=True):
                st.markdown(
                    f"### {item['rank']}. {escape(item['title'])}\n"
                    f"**{item['rating_source']}: {item['rating_used']:.2f}/5** · "
                    f"[Amazon listing]({item['product_url']})"
                )
                if item["matched_priorities"]:
                    st.caption(
                        "Matched priorities: " + ", ".join(item["matched_priorities"])
                    )
                pros_col, cons_col = st.columns(2, gap="medium")
                with pros_col:
                    _render_aspect_summary(
                        "✓ Pros from reviews",
                        item.get("pros", []),
                        "No recurring positive theme was available in B2 analysis.",
                    )
                with cons_col:
                    _render_aspect_summary(
                        "△ Cons from reviews",
                        item.get("cons", []),
                        "No recurring negative theme was available in B2 analysis.",
                    )
                if item["citations"]:
                    st.markdown("**Review evidence**")
                    for citation in item["citations"]:
                        quote = str(citation["quote"]).strip()
                        if len(quote) > 420:
                            quote = quote[:417].rsplit(" ", 1)[0] + "..."
                        st.markdown(f"> {quote}")
                        st.caption(
                            f"{citation['aspect']} · Review {citation['review_id']} · "
                            f"{citation.get('stars', 'N/A')}/5 stars"
                        )

    status_by_asin = {item["asin"]: item for item in result.get("eligibility", [])}
    with st.expander("Hard-requirement checks"):
        for asin, item in status_by_asin.items():
            icon = {"eligible": "✅", "ineligible": "⛔", "unknown": "⚠️"}[item["status"]]
            st.markdown(f"{icon} **{asin} — {item['status'].title()}**")
            st.caption(item["reason"])
    for warning in result.get("analysis_warnings", []):
        st.caption(warning)
    for error in result.get("cart_errors", []):
        st.caption(f"Skipped input: {error.get('reason', error)}")


def render_shopping_agent() -> None:
    """Render a one-to-five product personalized comparison workflow."""
    st.markdown(
        '<div class="rt-section-head"><div><div class="rt-section-label">'
        'AI SHOPPING AGENT</div><h2>Compare products for your needs.</h2></div>'
        '<p>Hard filters first, then B1/B2 review evidence</p></div>',
        unsafe_allow_html=True,
    )
    count = st.number_input(
        "Number of products", min_value=1, max_value=5, value=2, step=1,
        help="Compare one to five Amazon products from the historical dataset.",
    )
    with st.form("personalized_shopping_agent"):
        need = st.text_area(
            "What do you need?",
            placeholder=(
                "Example: I need AA batteries for a wireless mouse. Reliability and "
                "battery life matter most. Do not include AAA batteries."
            ),
        )
        links = [
            st.text_input(
                f"Amazon product {index + 1}",
                placeholder="https://www.amazon.com/dp/...",
                key=f"agent_link_{index}",
            )
            for index in range(int(count))
        ]
        submitted = st.form_submit_button(
            "Get a personalized recommendation →",
            type="primary",
            use_container_width=True,
        )
    if submitted:
        with st.spinner("Checking requirements and review evidence..."):
            st.session_state["shopping_agent_result"] = run_workflow(links, need)
    if result := st.session_state.get("shopping_agent_result"):
        _render_result(result)
