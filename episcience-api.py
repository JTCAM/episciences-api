#!/bin/env python
import requests
import json
import getpass
import os

url = 'https://api.episciences.org'


def fetch_token():
    username = getpass.getuser()
    password = getpass.getpass()
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


def list_papers(token):
    r = requests.get(
        url+'/api/papers',
        #        data=json.dumps({'code': 'jtcam'}),
        headers={
            "accept": "application/ld+json",
            "Authorization": f"Bearer {token['token']}"
        })
    r = r.json()
    return r

    r = json.dumps(r)


token = authenticate()
print(token['token'])
p = list_papers(token)
print(p)
