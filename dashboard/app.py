"""Streamlit dashboard for managing the search queue and reviewing results."""
from __future__ import annotations

import os
from typing import Any, Dict, List

import streamlit as st
from supabase import create_client

from dotenv import load_dotenv


@st.cache_resource(show_spinner=False)
def get_supabase():
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_KEY"]
    return create_client(url, key)


def fetch_queue_items(status: str) -> List[Dict[str, Any]]:
    client = get_supabase()
    # Orders by run_at (oldest first) for queue, or created_at for reviews
    response = client.table("search_actions").select("*").eq("status", status).order("id", desc=False).execute()
    return response.data or []


def fetch_scraped_items(action_id: str) -> List[Dict[str, Any]]:
    client = get_supabase()
    response = client.table("scraped_items").select("*").eq("action_id", action_id).order("created_at", desc=False).execute()
    return response.data or []


def update_action(action_id: str, updates: Dict[str, Any]) -> None:
    client = get_supabase()
    client.table("search_actions").update(updates).eq("id", action_id).execute()


def render_queue_tab() -> None:
    st.header("Pending Queue")
    pending_actions = fetch_queue_items("PENDING")

    if not pending_actions:
        st.info("No pending search actions.")
        return

    for action in pending_actions:
        with st.container(border=True):
            st.subheader(action.get("search_phrase", "(unknown phrase)"))
            cols = st.columns(2)
            with cols[0]:
                if st.button("Approve", key=f"approve-{action['id']}"):
                    update_action(action["id"], {"status": "QUEUED"})
                    st.success("Action approved and queued.")
                    st.rerun()
            with cols[1]:
                if st.button("Reject", key=f"reject-{action['id']}"):
                    update_action(action["id"], {"status": "REJECTED"})
                    st.warning("Action rejected.")
                    st.rerun()


def render_review_tab() -> None:
    st.header("Ready for Review")
    review_actions = fetch_queue_items("REVIEW_READY")

    if not review_actions:
        st.info("No actions awaiting review.")
        return

    for action in review_actions:
        with st.expander(action.get("search_phrase", "(unknown phrase)"), expanded=True):
            items = fetch_scraped_items(action["id"])
            if items:
                # Basic dataframe view - you can upgrade this to st.image grid later
                st.dataframe(items)
            else:
                st.write("No scraped items for this action yet.")

            cols = st.columns(2)
            with cols[0]:
                if st.button("Market Gap Found", key=f"gap-{action['id']}"):
                    # Updates status to COMPLETED so it leaves the review list
                    update_action(action["id"], {"market_gap_found": True, "status": "COMPLETED"})
                    st.success("Marked as gap found.")
                    st.rerun()
            with cols[1]:
                if st.button("Saturated / No Gap", key=f"nogap-{action['id']}"):
                    # Updates status to COMPLETED so it leaves the review list
                    update_action(action["id"], {"market_gap_found": False, "status": "COMPLETED"})
                    st.info("Marked as saturated.")
                    st.rerun()


def main() -> None:
    load_dotenv()
    st.set_page_config(page_title="Browser God Queue", layout="wide")
    st.title("Browser God Queue Manager")

    queue_tab, review_tab = st.tabs(["Queue", "Review"])

    with queue_tab:
        render_queue_tab()

    with review_tab:
        render_review_tab()


if __name__ == "__main__":
    main()