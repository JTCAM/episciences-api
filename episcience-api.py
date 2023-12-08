#!/bin/env python
import requests
import json
import getpass
import os

url = 'https://api.episciences.org'


def fetch_token():
    password = getpass.getpass()
    r = requests.post(
        url+'/api/login',
        data=json.dumps({'username': 'ganciaux',
                         'password': password,
                         'code': 'jtcam'
                         }),
        headers={
            "accept": "application/json",
            "Content-Type": "application/json",
        })
    r = r.json()
    return r


def authenticate():
    if os.path.exists('token.json'):
        f = open('token.json')
        r = json.load(f)
    else:
        r = fetch_token()
        with open('token.json', 'w') as f:
            f.write(r)
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
