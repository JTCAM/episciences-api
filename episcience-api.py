#!/bin/env python
import requests
import json
import getpass
import os

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
            r = json.load(f)
            if not check_authentication(r):
                r = None
            if r is None:
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
    return r

################################################################


def check_authentication(token):
    r, code = epi_get_single(f'/api/me', token)
    if code == 401:
        print('Expired token')
        return False
    else:
        print('Logged:', r['email'])
    return True

################################################################


def epi_get_single(req, token, page=None):
    url = 'https://api.episciences.org'
    url = url + req
    if page is not None:
        url += f'?page={page}'
    # url += '?status=16'
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
            # print(code)
            # print(r.content)
            return [], code
        r = r.json()
        if 'hydra:member' in r:
            print('hydra:totalItems: ', r['hydra:totalItems'])
            # print(r['hydra:search'])
            ret = r['hydra:member']
            return ret, code

        return r, code

################################################################


def epi_get(req, token):
    r = []
    ret = 1
    page = 0
    while ret:
        page += 1
        ret, code = epi_get_single(req, token, page)
        print('returned len', len(ret))
        for p in ret:
            print(p['@id'])
        r += ret
    return r

################################################################


def list_papers(token):
    r = epi_get('/api/papers', token)
    return r

################################################################


def list_users(token):
    r = epi_get('/api/users', token)
    return r

################################################################


def get_user(uid, token):
    r = epi_get_single(f'/api/users/{uid}', token)
    return r

################################################################


def get_paper(uid, token):
    r = epi_get_single(f'/api/papers/{uid}', token)
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

# u = get_paper(11497, token)
# for k, v in u.items():
#     print(k, v)
