#!/bin/env python
import requests
import json
import getpass
import logging
from dotmap import DotMap
import os

logger = logging.getLogger()
################################################################


class HttpErrorCode(Exception):
    def __init__(self, code, msg):
        self.code = code
        self.msg = msg


################################################################


class EpiSciencesPaper:

    def __init__(self, json):
        # import yaml
        # print(yaml.safe_dump(json))

        self.json = DotMap(json)
        self.document = self.json.document
        self.journal_document = self.document.journal
        self.journal_article = self.journal_document.journal_article
        self.titles = self.journal_article.titles
        self.title = self.titles.title
        self.contributors = self.journal_article.contributors
        self.dates = self.document.database.current.dates
        self.status = self.document.database.current.status
        if hasattr(self.journal_article.keywords, "en"):
            self.keywords = self.journal_article.keywords.en
        else:
            self.keywords = self.journal_article.keywords
        self.editors = self.json.editors
        self.reviewers = self.json.reviewers

        print("*" * 70)
        import yaml

        print(json.keys())

    @property
    def abstract(self):
        abstract = self.journal_article.abstract.value.value
        if isinstance(abstract, list):
            abstract = abstract[0]
        return abstract

    @property
    def files(self):
        files = self.document.database.current.files
        if not isinstance(files, list):
            files = [files]
        return [f.link for f in files]

    def __getattr__(self, key):
        if key in self.document:
            return self.document[key]

        if key in self.json:
            return self.json[key]
        raise AttributeError(key)

    def __dir__(self):
        d = [e for e in self.json]
        return d


################################################################


class EpisciencesDB:

    status_codes = {
        -1: "Unknown",
        19: "Copy editing",
        16: "Published",
        6: "Obsolete",
        4: "Accepted",
        5: "Refused",
        0: "Submitted",
        2: "In review",
        7: "Pending minor revision",
        15: "Pending major revision",
        12: "Reviewed",
        17: "Abandoned",
    }

    @staticmethod
    def getStatusFromCode(code):
        if code in EpisciencesDB.status_codes:
            status = EpisciencesDB.status_codes[code]
        else:
            status = "Unknown"
        return status

    # rvid = 23 => JTCAM
    def __init__(self, rvid=23, token=None):
        self.token = None
        self.provided_token = token
        self.authenticate()
        self.rvid = rvid

    def fetch_token(self, username=None, password=None):
        if username is None and "EPI_USERNAME" in os.environ:
            username = os.environ["EPI_USERNAME"]
        if username is None:
            username = input("login:")
        if password is None and "EPI_PASSWORD" in os.environ:
            password = os.environ["EPI_PASSWORD"]
        if password is None:
            password = getpass.getpass()
        url = "https://api.episciences.org"
        r = requests.post(
            url + "/api/login",
            data=json.dumps(
                {"username": username, "password": password, "code": "jtcam"}
            ),
            headers={
                "accept": "application/json",
                "Content-Type": "application/json",
            },
            timeout=1000,
        )
        # print(r.content)
        r = r.json()
        if "code" in r:
            if r["code"] == 401:
                raise HttpErrorCode(401, "Error code 401 was returned")
        self.token = r

    def refresh_token(self):
        if self.token is None:
            return
        if "code" in self.token and self.token["code"] == 401:
            return
        url = "https://api.episciences.org"
        r = requests.post(
            url + "/api/token/refresh",
            data=json.dumps({"refresh_token": self.token["refresh_token"]}),
            headers={
                "accept": "application/json",
                "Content-Type": "application/json",
            },
            timeout=1000,
        )
        r = r.json()
        self.token = r

    def read_token_from_file(self):
        if self.provided_token is not None:
            self.token = {"token": self.provided_token}
            # logger.error(f'received token: {self.token}')
            return
        try:
            with open("token.json") as f:
                self.token = json.load(f)
        except FileNotFoundError as e:
            pass

    def write_token_to_file(self):
        with open("token.json", "w") as f:
            f.write(json.dumps(self.token))

    def authenticate(self):
        try:
            self.read_token_from_file()
            if not self.check_authentication():
                self.token = None
            if self.token is None:
                self.read_token_from_file()
                self.refresh_token()
                print("Refreshed token")
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
                raise RuntimeError("Incorrect login when fetching the token:", e.code)
        if self.token is None:
            raise RuntimeError("Error with the token (None)")
        # print('token:', self.token['token'][:12], '...')

    def check_authentication(self):
        if self.token is None:
            return False
        if "token" not in self.token:
            return False
        try:
            r = self.epi_get("/api/me")
        except HttpErrorCode as e:
            if e.code == 401:
                print("Expired token")
                return False
        # print('Logged:', r['email'])
        return True

    def epi_get(self, req, **kwargs):
        url = "https://api.episciences.org"
        url = url + req
        args = []
        for k, v in kwargs.items():
            args.append(f"{k}={v}")
        if args:
            url += "?" + "&".join(args)
        headers = {
            "accept": "application/ld+json",
            "Authorization": f"Bearer {self.token['token']}",
        }
        # print(headers)
        code = 500
        n_failure = 0
        while 1:
            r = requests.get(url, headers=headers, timeout=1000)
            code = r.status_code
            if code == 500:
                n_failure += 1
                if n_failure > 10:
                    raise HttpErrorCode(code, f"Failed to perform request: {req}")
                continue
            if code != 200:
                raise HttpErrorCode(code, f"Failed to perform request: {req}")
            r = r.json()
            if "hydra:member" in r:
                # print('hydra:totalItems: ', r['hydra:totalItems'])
                # print(r['hydra:search'])
                ret = r["hydra:member"]
                return ret

            return r

    def list_papers(self):
        r = self.epi_get("/api/papers/", rvid=self.rvid, pagination="false")
        return r

    def list_users(self):
        kwargs = {"pagination": "false"}
        r = self.epi_get("/api/users", **kwargs)
        return r

    def get_user(self, uid):
        r = self.epi_get(f"/api/users/{uid}")
        return r

    def get_paper(self, uid):
        r = self.epi_get(f"/api/papers/{uid}")
        return EpiSciencesPaper(r)


################################################################
