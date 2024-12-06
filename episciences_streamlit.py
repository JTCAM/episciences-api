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


def format_authors(authors):
    _authors = []
    _affiliations = []

    def get_author_affiliations(author):
        if 'affiliations' not in author:
            return []

        affs = author.affiliations.institution
        res = []
        if not isinstance(affs, list):
            affs = [affs]

        for e in affs:
            name = e.institution_name
            res.append(name)
        return res

    for author in authors.person_name:
        affs = get_author_affiliations(author)

        for e in affs:
            if e not in _affiliations:
                _affiliations.append(e)

    for auth in authors.person_name:
        text = ""
        text += f'**{auth.given_name} {auth.surname}**'
        affs = get_author_affiliations(auth)
        if affs:
            text += "$^{"
            affs = [_affiliations.index(e) + 1 for e in affs]
            aff = [str(e) for e in affs]
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

    selectable_papers = [p['paperid']
                         for p in papers if p['status'] in sel_status]

    summary_papers = []
    with st.spinner('Fetching data, please wait...'):
        for p in selectable_papers:
            p = conn.get_paper(p)
            status = f'{p.status.label.en}({p.status.id})'

            # st.write(p.contributors.toDict())
            summary_papers.append((
                str(p.paperid),
                p.title,
                [e.surname for e in p.contributors.person_name],
                p.submissionDate,
                status,
                dir(p),
            ))

    # st.write(summary_papers)
    import pandas as pd
    summary_papers = pd.DataFrame(
        summary_papers,
        columns=['paperid',
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
    fmt = format_authors(p.contributors)

    st.markdown(fmt, unsafe_allow_html=True)
    st.markdown(f'<br><h5><center> submissionDate: {p.submissionDate} </center></h5>',
                unsafe_allow_html=True)

    st.write(p.abstract.toDict())
    if hasattr(p, 'abstract'):
        st.markdown(f'<div style="text-align: justify"> {p.abstract.value} </div><br>',
                    unsafe_allow_html=True
                    )

    st.markdown(f'Files:\n\n {p.files.link}')
    st.markdown(f'Status: {p.status.label.en}')
    field = st.selectbox("Choose field", options=dir(p))
    field = getattr(p, field)
    if field is None:
        field = "Empty or not found"
    try:
        st.write(field.toDict())
    except:
        st.write(field)

    with st.expander('Full Content'):
        st.write('Info from request /api/papers')
        for _p in papers:
            if _p['paperid'] == p.paperid:
                st.write(_p)
        st.write(f'Info from request /api/papers/{sel}')
        st.write(p.json.toDict())


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
