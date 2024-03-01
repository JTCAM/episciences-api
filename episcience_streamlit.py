#!/bin/env python
import json
import os
import episcience_api as epi
################################################################


import streamlit as st
st.set_page_config(layout="wide")
conn = epi.EpiscienceDB()

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
if not isinstance(p.title, str):
    p.title = p.title['#text']
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
