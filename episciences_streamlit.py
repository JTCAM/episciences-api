#!/bin/env python
import json
import os
import streamlit as st
import extra_streamlit_components as stx
import episciences as epi

st.set_page_config(
    layout="wide", page_icon='https://jtcam.episciences.org/favicon-32x32.png?v=20211124')
st.markdown('<center><img style="width: 60%;" src="https://jtcam.episciences.org/public/BandeauWebv_3.svg" alt="JTCAM_header"></center>',
            unsafe_allow_html=True)
st.markdown('<h1> <center> Episciences papers explorator </center></h1> <hr>',
            unsafe_allow_html=True)
main_box = st.container()
auth_box = st.container()

cookie_manager = None
cookie_manager = stx.CookieManager()
cookies = cookie_manager.get_all()
# st.write(cookies)
################################################################


class STEpisciencesDB(epi.EpisciencesDB):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def fetch_token(self, username=None, password=None):
        with auth_box.form("Episcience API authentication"):
            username = st.text_input('Username', value=username)
            password = st.text_input(
                'API Password', value=password, type='password')
            button = st.form_submit_button('connect')
            if button:
                if (username == '' or password == '' or
                        username is None or password is None):
                    st.error("Wrong credentials")
                    return

                try:
                    super().fetch_token(username, password)
                except epi.HttpErrorCode as e:
                    st.error("Wrong credentials")
                    raise e
                # st.write('pas here')
                # st.write(self.token)
                cookie_manager.set('episciences_api_token', self.token)

    def read_token_from_file(self):
        if 'episciences_api_token' in cookies and 'token' in cookies['episciences_api_token']:
            self.token = cookies['episciences_api_token']

    def write_token_to_file(self):
        pass

################################################################


def format_authors(authors, affiliations):
    _authors = []
    _affiliations = []

    if affiliations is None:
        affiliations = [None]*len(authors)

    for aff in affiliations:
        if aff is None:
            continue
        aff = aff.split(";")
        for e in aff:
            if e.strip() not in _affiliations:
                _affiliations.append(e.strip())

    for auth, aff in zip(authors, affiliations):
        text = ""
        text += f'**{auth}**'
        if aff is not None:
            text += "$^{"
            aff = aff.split(";")
            aff = [_affiliations.index(e.strip()) + 1 for e in aff]
            aff = [str(e) for e in aff]
            text += f'{",".join(aff)}'
            text += "}$"

        _authors.append(text)
    formatted = "**<h4><center> " + "; ".join(_authors) + " </center></h4>**\n"
    for idx, aff in enumerate(_affiliations):
        formatted += f"<center><sup>{idx+1}</sup> <i>{aff}</i></center>\n"
    return formatted

################################################################


def print_page(conn):
    if not os.path.exists('papers.json'):
        papers = conn.list_papers()
        print(f'Fetched {len(papers)} papers')
        with open('papers.json', 'w') as f:
            f.write(json.dumps(papers))
    else:
        with open('papers.json') as f:
            papers = json.load(f)

    codes = epi.EpisciencesDB.status_codes.copy()
    sel_status = st.multiselect("Article status selection",
                                list(epi.EpisciencesDB.status_codes.keys()),
                                format_func=lambda i: codes[int(i)] + f'({i})',
                                default=[19],
                                )
    sel_status = [int(s) for s in sel_status]
    # st.write(sel_status)

    selectable_papers = [p['docid'] for p in papers
                         if (p['status'] in sel_status or
                             (p['status'] not in epi.EpisciencesDB.status_codes and -1 in sel_status)
                             )]

    summary_papers = []
    with st.spinner('Fetching data, please wait...'):
        for p in selectable_papers:
            p = conn.get_paper(p)
            status = 'Unknwon'
            if p.status in epi.EpisciencesDB.status_codes:
                status = epi.EpisciencesDB.status_codes[p.status]

            summary_papers.append((
                str(p.docid),
                p.title,
                p.creator,
                p.submissionDate,
                status,
                dir(p),
            ))

    # st.write(summary_papers)
    import pandas as pd
    summary_papers = pd.DataFrame(
        summary_papers,
        columns=['docid',
                 'title', 'authors', 'submissiondate', 'status', 'features'])
    st.dataframe(summary_papers, use_container_width=True, hide_index=True)

    sel = st.selectbox("Choose paper", options=selectable_papers)
    if sel is None:
        st.warning('No paper selected')
        return
    p = conn.get_paper(sel)

    st.markdown(
        f"<h2> <center>{p.title} </center></h2>", unsafe_allow_html=True)
    # st.markdown("### *" + '; '.join(p.creator) + "*")
    try:
        contrib = p.contributor
    except AttributeError:
        contrib = None
    fmt = format_authors(p.creator, contrib)

    st.markdown(fmt, unsafe_allow_html=True)
    st.markdown(f'<br><h5><center> submissionDate: {p.submissionDate} </center></h5>',
                unsafe_allow_html=True)

    if hasattr(p, 'description'):
        st.markdown(f'<div style="text-align: justify"> {p.description.strip()} </div><br>',
                    unsafe_allow_html=True
                    )
    p.identifier = '- ' + '\n - '.join(
        [e.strip() for e in p.identifier if e.strip() != ''])
    st.markdown('Identifiers:\n\n' + p.identifier)
    if p.status in epi.EpisciencesDB.status_codes:
        p.status = 'Status: ' + epi.EpisciencesDB.status_codes[p.status]
    else:
        p.status = f'<text style="background-color:red;"> Status: {p.status} </text>'
    st.markdown(p.status, unsafe_allow_html=True)
    field = st.selectbox("Choose field", options=dir(p))
    field = getattr(p, field)
    if field is None:
        field = "Empty or not found"
    st.write(field)
    with st.expander('Full Content'):
        st.write('Info from request /api/papers')
        for _p in papers:
            if _p['docid'] == p.docid:
                st.write(_p)
        st.write(f'Info from request /api/papers/{sel}')
        st.write(p.json)


try:
    conn = STEpisciencesDB()
    # auth_box.empty()

    def reset():
        st.write('logging out')
        cookie_manager.set('episciences_api_token', {})
        os.remove('papers.json')
        st.experimental_rerun()

    with main_box:
        lout = st.button('logout and refresh')
        if lout:
            reset()
        # st.write(cookies)
        print_page(conn)
except RuntimeError as e:
    st.error(e)
