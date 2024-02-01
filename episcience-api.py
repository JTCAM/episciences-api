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
        }, timeout=1000)
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


def epi_get_single(req, token, page=None):
    url = 'https://api.episciences.org'
    url = url + req
    if page is not None:
        url += f'?page={page}'
    # url += '?status=16'
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
            print(code)
            print(r.content)
            return []
        r = r.json()
        print('aaaa', code, r)
        # print(r.keys())
        if 'hydra:member' in r:
            print(r['hydra:totalItems'])
            # print(r['hydra:search'])
            return r['hydra:member']
        
        return r


def epi_get(req, token):
    page = 1
    ret = epi_get_single(req, token, page)
    if ret is None:
        return []
    r = []
    while ret:
        page += 1
        ret = epi_get_single(req, token, page)
        print('returned len', len(ret))
        for p in ret:
            print(p['@id'])
        # print(ret)
        r += ret
        break
    return r


def list_papers(token):
    r = epi_get('/api/papers', token)
    return r


def list_users(token):
    r = epi_get('/api/users', token)
    return r


def get_user(uid, token):
    r = epi_get_single(f'/api/users/{uid}', token)
    return r


def get_paper(uid, token):
    r = epi_get_single(f'/api/papers/{uid}', token)
    return r


token = authenticate()
print(token['token'])
print("papers")

papers = list_papers(token)
print(f'Found {len(papers)} papers')
for p in papers:
    print('\n' + '*'*60 + '\n')
    for k, v in p.items():
        print(k, v)

# print("users")
# users = list_users(token)
# # print(users)
# for p in users:
#     print('\n' + '*'*60 + '\n')
#     for k, v in p.items():
#         print(k, v)

print('*'*30)
print('*'*30)
# u = get_paper(11497, token)
# for k, v in u.items():
#     print(k, v)
