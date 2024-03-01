#!/bin/env python
import json
import os
import streamlit as st
import extra_streamlit_components as stx
import episcience_api as epi

st.set_page_config(layout="wide")
cookie_manager = stx.CookieManager()
cookies = cookie_manager.get_all()
should_not_update_cookie = False
if not (cookies):
    should_not_update_cookie = True

################################################################
class STEpisciencesDB(epi.EpisciencesDB):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
    def fetch_token(self, username=None, password=None):
        username = st.text_input('Username', value=username)
        password = st.text_input('API Password', value=password, type='password')
        button = st.button('connect')
        if not button:
            return
        if (username == '' or password == '' or 
            username is None or password is None):
            st.error("Wrong credentials")
            return
        
        super().fetch_token(username, password)
        if not should_not_update_cookie:
            cookie_manager.set('episciences_api_token', self.token)

    def read_token_from_file(self):
        if 'episciences_api_token' in cookies:
            self.token = cookie_manager.get('episciences_api_token')

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

    sel = st.selectbox("Choose paper", options=[p['docid'] for p in papers])
    p = conn.get_paper(sel)

    if not isinstance(p.title, str):
        p.title = p.title['#text']
    st.markdown("## " + p.title)
    if isinstance(p.creator, str):
        p.creator = [p.creator]
    st.markdown("### *" + '; '.join(p.creator) + "*")
    st.markdown('#### submissionDate: '+ p.submissionDate)
    if not isinstance(p.description, str):
        p.description = p.description['#text']
    st.markdown(p.description.strip())   
    st.markdown('Identifiers:\n\n- ' + '\n - '.join(
        [e.strip() for e in p.identifier if e.strip() != '']))
    st.markdown('Status:' + str(p.status))
    field = st.selectbox("Choose field", options=dir(p))
    field = getattr(p, field)
    if field is None:
        field = "Empty or not found"
    st.write(field)
    with st.expander('Full Content'):
        st.write(p.json)


try:
    conn = STEpisciencesDB()
    print_page(conn)
except RuntimeError as e:
    pass

