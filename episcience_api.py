#!/bin/env python
import requests
import json
import getpass
import os

################################################################


class HttpErrorCode(Exception):
    def __init__(self, code, msg):
        self.code = code
        self.msg = msg

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
                raise HttpErrorCode(401, 'Error code 401 was returned')
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
        # print('token:', self.token['token'][:12], '...')

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
        # print(url)
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


