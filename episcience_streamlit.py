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
st.markdown(p['record'], unsafe_allow_html=True)
for k, v in p.items():
    st.write(f'{k}: {v}')

#     for p in papers:
#         with st.expander(p['@id']):
#             for k in p.keys():
#                 st.write(f'{k}: {p[k]}')

#     return
#     print('*'*60)
#     print("Fetch users")
#     print('*'*60)
#
#     users = conn.list_users()
#     print(f'Found {len(users)} users')
#     for p in users:
#         print('\n' + '*'*60 + '\n')
#         for k, v in p.items():
#             print(k, v)
#
u = conn.get_paper(12489)
with open('paper.json', 'w') as f:
    f.write(json.dumps(u))

st.write(u)
for k, v in u.items():
    st.write(f'{k}: {v}')
