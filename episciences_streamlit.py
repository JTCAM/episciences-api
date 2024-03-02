#!/bin/env python
import json
import os
import streamlit as st
import extra_streamlit_components as stx
import episciences as epi

st.set_page_config(layout="wide")
st.markdown('# Episciences papers explorator')
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
    codes[-1] = 'Unknown'
    sel_status = st.multiselect("Article status selection",
                                ['-1'] +
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
    for p in selectable_papers:
        p = conn.get_paper(p)
        summary_papers.append((
            p.title['#text'],
            p.creator,
            p.submissionDate,
            epi.EpisciencesDB.status_codes[p.status],
            dir(p),
        ))

    import pandas as pd
    summary_papers = pd.DataFrame(summary_papers, columns=[
        'title', 'authors', 'submissiondate', 'status', 'features'])
    st.dataframe(summary_papers, use_container_width=True)

    sel = st.selectbox("Choose paper", options=selectable_papers)
    if sel is None:
        st.warning('No paper selected')
        return
    p = conn.get_paper(sel)

    if not isinstance(p.title, str):
        if isinstance(p.title, list):
            p.title = p.title[0]
        p.title = p.title['#text']
    p.title = p.title.replace('\n', ' ')
    st.markdown("## " + p.title)
    if isinstance(p.creator, str):
        p.creator = [p.creator]
    st.markdown("### *" + '; '.join(p.creator) + "*")
    st.markdown('#### submissionDate: ' + p.submissionDate)

    if hasattr(p, 'description'):
        if not isinstance(p.description, str):
            if isinstance(p.description, list):
                p.description = p.description[0]
            if not isinstance(p.description, str):
                p.description = p.description['#text']
        st.markdown(p.description.strip())
    if not isinstance(p.identifier, str):
        p.identifier = '- ' + '\n - '.join(
            [e.strip() for e in p.identifier if e.strip() != ''])
    else:
        p.identifier = '- ' + p.identifier
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
        st.write(p.json)


try:
    conn = STEpisciencesDB()
    # auth_box.empty()

    def reset():
        cookie_manager.set('episciences_api_token', {})
        os.remove('papers.json')

    with main_box:
        lout = st.button('logout and refresh', on_click=reset)
        # st.write(cookies)
        print_page(conn)
except RuntimeError as e:
    st.error(e)
    pass
