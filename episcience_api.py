#!/bin/env python
import requests
import json
import getpass
import os

################################################################


class HttpErrorCode(Exception):
    def __init__(self, code, msg):
        self.code = code

################################################################


class EpiscienceDB:

    status_codes = {
        'Copy editing': 19,

    }

    # rvid = 23 => JTCAM
    def __init__(self, rvid=23):
        self.token = None
        self.authenticate()
        self.rvid = rvid

    def fetch_token(self):
        username = input('login:')
        password = getpass.getpass()
        url = 'https://api.episciences.org'
        r = requests.post(
            url+'/api/login',
            data=json.dumps({'username': username,
                             'password': password,
                             'code': 'jtcam'
                             }),
            headers={
                "accept": "application/json",
                "Content-Type": "application/json",
            }, timeout=1000)
        # print(r.content)
        r = r.json()
        if 'code' in r:
            if r['code'] == 401:
                raise HttpErrorCode(401)
        self.token = r

    def refresh_token(self):
        url = 'https://api.episciences.org'
        r = requests.post(
            url+'/api/token/refresh',
            data=json.dumps({'refresh_token': self.token['refresh_token']}),
            headers={
                "accept": "application/json",
                "Content-Type": "application/json",
            }, timeout=1000)
        r = r.json()
        self.token = r

    def read_token_from_file(self):
        with open('token.json') as f:
            self.token = json.load(f)

    def write_token_to_file(self):
        with open('token.json', 'w') as f:
            f.write(json.dumps(self.token))

    def authenticate(self):
        if os.path.exists('token.json'):
            try:
                self.read_token_from_file()
                if not self.check_authentication():
                    self.token = None
                if self.token is None:
                    self.read_token_from_file()
                    self.refresh_token()
                    print('Refreshed token')
                    self.write_token_to_file()
                if not self.check_authentication():
                    self.token = None
            except json.JSONDecodeError:
                pass
            except HttpErrorCode as e:
                print("error during authentication:", e.code)
                pass
        if self.token is None:
            try:
                self.fetch_token()
                self.write_token_to_file()
            except HttpErrorCode as e:
                raise RuntimeError(
                    "Incorrect login when fetching the token:", e.code)
        if self.token is None:
            raise RuntimeError("Error with the token")
        print('token:', self.token['token'][:12], '...')

    def check_authentication(self):
        try:
            r = self.epi_get('/api/me')
        except HttpErrorCode as e:
            if e.code == 401:
                print('Expired token')
                return False
        print('Logged:', r['email'])
        return True

    def epi_get(self, req, **kwargs):
        url = 'https://api.episciences.org'
        url = url + req
        args = []
        for k, v in kwargs.items():
            args.append(f'{k}={v}')
        if args:
            url += '?'+'&'.join(args)
        print(url)
        headers = {
            "accept": "application/ld+json",
            "Authorization": f"Bearer {self.token['token']}"
        }
        code = 500
        while 1:
            r = requests.get(url, headers=headers, timeout=1000)
            code = r.status_code
            if code == 500:
                continue
            if code != 200:
                raise HttpErrorCode(code, f'Failed to perform request: {req}')
            r = r.json()
            if 'hydra:member' in r:
                print('hydra:totalItems: ', r['hydra:totalItems'])
                # print(r['hydra:search'])
                ret = r['hydra:member']
                return ret

            return r

    def list_papers(self):
        r = self.epi_get('/api/papers', rvid=self.rvid, pagination='false')
        return r

    def list_users(self):
        kwargs = {
            'userRoles.rvid': self.rvid,
            'pagination': 'false'
        }
        r = self.epi_get('/api/users', **kwargs)
        return r

    def get_user(self, uid):
        r = self.epi_get(f'/api/users/{uid}')
        return r

    def get_paper(self, uid):
        r = self.epi_get(f'/api/papers/{uid}')
        return r

################################################################


if __name__ == '__main__':
    import streamlit as st
    st.set_page_config(layout="wide")
    conn = EpiscienceDB()

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
