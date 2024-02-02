#!/bin/env python
import requests
import json
import getpass
import os

################################################################
class HttpErrorCode(Exception):
    def __init__(self, code):
        self.code = code

################################################################
def fetch_token():
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
    return r

################################################################


def refresh_token(token):
    url = 'https://api.episciences.org'
    r = requests.post(
        url+'/api/token/refresh',
        data=json.dumps({'refresh_token': token['refresh_token']}),
        headers={
            "accept": "application/json",
            "Content-Type": "application/json",
        }, timeout=1000)
    r = r.json()
    return r

################################################################


def authenticate():
    r = None
    if os.path.exists('token.json'):
        try:
            f = open('token.json')
            token = json.load(f)
            r = token.copy()
            if not check_authentication(r):
                r = None
            if r is None:
                r = token.copy()
                r = refresh_token(r)
                with open('token.json', 'w') as f:
                    f.write(json.dumps(r))
        except json.JSONDecodeError:
            pass
    if r is None:
        r = fetch_token()
        with open('token.json', 'w') as f:
            f.write(json.dumps(r))
    if r is None:
        raise RuntimeError("Error fetching the token")
    print('token:', r['token'][:12], '...')
    return r

################################################################


def check_authentication(token):
    try:
        r = epi_get('/api/me', token)
    except HttpErrorCode as e:
        if e.code == 401:
            print('Expired token')
            return False
    print('Logged:', r['email'])
    return True

################################################################


def epi_get(req, token, **kwargs):
    url = 'https://api.episciences.org'
    url = url + req
    args = []
    kwargs['pagination'] = 'false'
    for k, v in kwargs.items():
        args.append(f'{k}={v}')
    if args:
        url += '?'+'&'.join(args)
    print(url)
    headers = {
        "accept": "application/ld+json",
        "Authorization": f"Bearer {token['token']}"
    }
    code = 500
    while 1:
        r = requests.get(url, headers=headers, timeout=1000)
        code = r.status_code
        if code == 500:
            continue
        if code != 200:
            raise HttpErrorCode(code)
        r = r.json()
        if 'hydra:member' in r:
            print('hydra:totalItems: ', r['hydra:totalItems'])
            # print(r['hydra:search'])
            ret = r['hydra:member']
            return ret

        return r

################################################################


# rvid = 23 => JTCAM
def list_papers(token, rvid=23):
    r = epi_get('/api/papers', token, rvid=rvid)
    return r

################################################################


def list_users(token, rvid=23):
    kwargs ={
        'userRoles.rvid': rvid
    }
    r = epi_get('/api/users', token, **kwargs)
    return r

################################################################


def get_user(uid, token):
    r = epi_get(f'/api/users/{uid}', token)
    return r

################################################################


def get_paper(uid, token):
    r = epi_get(f'/api/papers/{uid}', token)
    return r


################################################################
token = authenticate()
# print(token['token'])
print('*'*60)
print("Fetch papers")
papers = list_papers(token)
print(f'Found {len(papers)} papers')

for p in papers:
    print('\n' + '*'*60 + '\n')
    print(p)
    for k, v in p.items():
        print(k, v)

print('*'*60)
print("Fetch users")
print('*'*60)

users = list_users(token)
print(f'Found {len(users)} users')
for p in users:
    print('\n' + '*'*60 + '\n')
    for k, v in p.items():
        print(k, v)

u = get_paper(11497, token)
print(u)
for p in u:
    print(p)
