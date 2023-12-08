#!/bin/env python
import requests
import json
import getpass
import os


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
        })
    # print(r.content)
    r = r.json()
    return r


def authenticate():
    r = None
    if os.path.exists('token.json'):
        try:
            f = open('token.json')
            r = json.load(f)
        except json.JSONDecodeError:
            pass
    elif r is None:
        r = fetch_token()
        with open('token.json', 'w') as f:
            f.write(json.dumps(r))
    else:
        raise RuntimeError("Error fetching the token")
    return r


def epi_get_single(req, token, page=1):
    url = 'https://api.episciences.org'
    url = url + req + f'?page={page}'
    print(url)
    headers = {
        "accept": "application/ld+json",
        "Authorization": f"Bearer {token['token']}"
    }
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        print(r.status_code)
        print(r.content)
        return None
    # print(r.content)
    r = r.json()
    r = r['hydra:member']
    return r


def epi_get(req, token):
    page = 1
    ret = epi_get_single(req, token, page)
    if ret is None:
        return []
    r = ret.copy()
    while ret:
        page += 1
        r += ret
        ret = epi_get_single(req, token, page)
    return r


def list_papers(token):
    r = epi_get('/api/papers', token)
    return r


def list_users(token):
    r = epi_get('/api/users', token)
    return r


token = authenticate()
print(token['token'])
print("papers")

papers = list_papers(token)
for p in papers:
    print(p['@id'])

print("users")
users = list_users(token)
print(users)
for p in users:
    print('\n' + '*'*60 + '\n')
    for k, v in p.items():
        print(k, v)
