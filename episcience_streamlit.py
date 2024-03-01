#!/bin/env python
import json
import os
import streamlit as st
import episcience_api as epi
################################################################
class STEpisciencesDB(epi.EpisciencesDB):


    def fetch_token(self):
        username = st.text_input('Username')
        password = st.text_input('API Password', type='password')
        button = st.button('connect')
        if not button:
            return
        if username == '' or password == '':
            st.error("Wrong credentials")
            return
        
        super().fetch_token(username, password)

    def read_token_from_file(self):
        return
#        with open('token.json') as f:
#            self.token = json.load(f)

    def write_token_to_file(self):
        return
 #       with open('token.json', 'w') as f:
 #           f.write(json.dumps(self.token))


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


st.set_page_config(layout="wide")
try:
    conn = STEpisciencesDB()
    print_page(conn)
except RuntimeError as e:
    pass

