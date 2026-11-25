#!/bin/env python
import json
import os

import streamlit as st
import extra_streamlit_components as stx

import episciences as epi

st.set_page_config(
    layout="wide",
    page_icon="https://jtcam.episciences.org/favicon-32x32.png?v=20211124",
)
st.markdown(
    '<center><img style="width: 60%;" src="https://jtcam.episciences.org/public/BandeauWebv_3.svg" alt="JTCAM_header"></center>',
    unsafe_allow_html=True,
)
st.markdown(
    "<h1> <center> Episciences papers explorator </center></h1> <hr>",
    unsafe_allow_html=True,
)
main_box = st.container()
auth_box = st.container()

cookie_manager = stx.CookieManager()
cookies = cookie_manager.get_all() or {}
################################################################


class STEpisciencesDB(epi.EpisciencesDB):

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("interactive", True)
        super().__init__(*args, **kwargs)

    def fetch_token(self, username=None, password=None):
        with auth_box.form("Episcience API authentication"):
            username = st.text_input("Username", value=username)
            password = st.text_input("API Password", value=password, type="password")
            button = st.form_submit_button("connect")
            if button:
                if not username or not password:
                    st.error("Wrong credentials")
                    return
                try:
                    super().fetch_token(username, password)
                except epi.HttpErrorCode as e:
                    st.error("Wrong credentials")
                    return
                self.write_token_to_file()
                st.rerun()

    def read_token_from_file(self):
        raw = cookies.get("episciences_api_token")
        if not raw:
            return super().read_token_from_file()
        try:
            data = json.loads(raw) if isinstance(raw, str) else raw
        except (json.JSONDecodeError, TypeError):
            data = raw
        if isinstance(data, dict) and "token" in data:
            self.token = {"token": data["token"], "refresh_token": data.get("refresh_token")}
        elif isinstance(data, str):
            self.token = {"token": data}

    def write_token_to_file(self):
        if self.token and "token" in self.token:
            cookie_manager.set(
                "episciences_api_token",
                json.dumps(
                    {
                        "token": self.token["token"],
                        "refresh_token": self.token.get("refresh_token"),
                    }
                ),
            )


################################################################


def format_authors(contributors):
    _authors = []
    _affiliations = []

    def get_author_affiliations(author):
        if not hasattr(author, "get"):
            return []
        affs = author.get("affiliations", None)
        if affs is None:
            return []
        if not hasattr(affs, "get"):
            return []
        institutions = affs.get("institution", None)
        if institutions is None:
            return []
        if not isinstance(institutions.json, list):
            institutions = [institutions]
        res = []
        for e in institutions:
            name = e.get("institution_name", None)
            if name is None:
                continue
            if not isinstance(name.json, list):
                name = [name]
            for n in name:
                res.append(str(n))
        return res

    persons = contributors.get("person_name", None) if hasattr(contributors, "get") else None
    if persons is None:
        return ""
    if not isinstance(persons.json, list):
        persons = [persons]

    for author in persons:
        affs = get_author_affiliations(author)
        for e in affs:
            if e not in _affiliations:
                _affiliations.append(e)

    for author in persons:
        given_name = author.get("given_name", "")
        surname = author.get("surname", "")
        text = f"**{given_name} {surname}**"
        affs = get_author_affiliations(author)
        if affs:
            indexes = [str(_affiliations.index(e) + 1) for e in affs]
            text += f"$^{{ {','.join(indexes)} }}$"
        _authors.append(text)

    formatted = "**<h4><center> " + "; ".join(_authors) + " </center></h4>**\n"
    for idx, aff in enumerate(_affiliations):
        formatted += f"<center><sup>{idx+1}</sup> <i>{aff}</i></center>\n"
    return formatted


################################################################


def print_page(conn):
    papers = conn.list_papers()
    st.toast(f"Fetched {len(papers)} papers")

    codes = epi.EpisciencesDB.status_codes.copy()
    sel_status = st.multiselect(
        "Article status selection",
        list(epi.EpisciencesDB.status_codes.keys()),
        format_func=lambda i: codes[int(i)] + f"({i})",
        default=[19],
    )
    sel_status = [int(s) for s in sel_status]

    selectable_papers = [p["paperid"] for p in papers if p.get("status") in sel_status]
    status_by_id = {str(p.get("paperid")): p.get("status") for p in papers}

    summary_papers = []
    with st.spinner("Fetching data, please wait..."):
        for paper_id in selectable_papers:
            p = conn.get_paper(paper_id, list_data={"status": status_by_id.get(str(paper_id))})
            title = p.title or "(no title)"
            authors = ", ".join(
                f"{a['given_name']} {a['surname']}"
                for a in p.authors
                if a.get("surname")
            )
            summary_papers.append(
                (
                    str(p.paperid),
                    title,
                    authors,
                    p.first_submission_date,
                    p.status_label,
                )
            )

    import pandas as pd

    summary_papers = pd.DataFrame(
        summary_papers,
        columns=["paperid", "title", "authors", "submissiondate", "status"],
    )
    st.dataframe(summary_papers, use_container_width=True, hide_index=True)

    sel = st.selectbox("Choose paper (id)", options=selectable_papers)
    if sel is None:
        st.warning("No paper selected")
        return
    p = conn.get_paper(sel, list_data={"status": status_by_id.get(str(sel))})

    st.markdown(f"<h2> <center>{p.title} </center></h2>", unsafe_allow_html=True)
    fmt = format_authors(p.contributors) if p.contributors is not None else ""
    st.markdown(fmt, unsafe_allow_html=True)

    submission = p.first_submission_date
    if submission:
        st.markdown(
            f"<br><h5><center> submissionDate: {submission} </center></h5>",
            unsafe_allow_html=True,
        )

    abstract = p.abstract or "No abstract"
    st.markdown(
        f'<div style="text-align: justify"> {abstract} </div><br>',
        unsafe_allow_html=True,
    )

    st.markdown(f'Files: {", ".join(p.files) if p.files else "none"}')
    st.markdown(f"Status: {p.status_label}")
    fields = list(p.journal_article[0].keys()) if p.get_or_none("journal_article") is not None else []
    if not fields:
        st.warning("No journal article fields available")
        return
    field = st.selectbox("Choose field", options=fields)
    field = p.get(field)
    if hasattr(field, "json"):
        field = field.json
    if field is None:
        field = "Empty or not found"
    try:
        st.write(field.toDict())
    except Exception:
        st.write(field)

    with st.expander("Full Content"):
        st.write("Info from request /api/papers")
        for _p in papers:
            if _p.get("paperid") == p.paperid:
                st.write(_p)
        st.write(f"Info from request /api/papers/{sel}")
        st.write(p.json)


try:
    conn = STEpisciencesDB()
except (epi.AuthenticationError, RuntimeError) as e:
    conn = None
    auth_error = e

with main_box:
    if conn is not None:
        def reset():
            cookie_manager.set("episciences_api_token", "")
            conn.forget_token()
            st.rerun()

        lout = st.button("logout and refresh")
        if lout:
            reset()
        try:
            print_page(conn)
        except epi.HttpErrorCode as e:
            st.error(f"API error: {e}")
    else:
        st.info("Connect to the Episciences API to browse the papers.")
        conn = STEpisciencesDB(auto_authenticate=False)
        conn.fetch_token()
