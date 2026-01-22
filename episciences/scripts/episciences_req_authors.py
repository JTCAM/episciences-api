#!/bin/env python

import episciences as epi
import pandas as pd
import requests
from tqdm import tqdm

################################################################


def flatten(lst):
    if isinstance(lst, str):
        return [lst]

    out = []
    for x in lst:
        if isinstance(x, list):
            out.extend(flatten(x))
        elif isinstance(x, str):
            out.append(x)

    return out


################################################################


def get_info(orcid):
    if isinstance(orcid, epi.episciences_api.QueryAbleObject):
        orcid = orcid[0]
    if isinstance(orcid, list):
        orcid = orcid[0]
    print(orcid, type(orcid))

    if orcid.startswith("https://orcid.org/"):
        orcid = orcid.split("https://orcid.org/")[1]
    url = f"https://pub.orcid.org/v3.0/{orcid}"
    headers = {"Accept": "application/json"}
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    record = r.json()
    print(record)
    raise


################################################################


def getUsers(conn):
    users = conn.list_users()

    users_list = []
    for u in tqdm(users):
        u = epi.episciences_api.QueryAbleObject(u)
        _id = u.uid

        try:
            u = conn.get_user(_id)
        except:
            continue
        u = epi.episciences_api.QueryAbleObject(u)
        given_name = u.firstname
        surname = u.lastname

        email = u.email
        # print(_id, surname)
        affs = u.get("institution_name", "Unknown")
        users_list.append((given_name, surname, email, ", ".join(flatten(affs)), _id))

    df_users = pd.DataFrame(
        users_list, columns=["GivenName", "Surname", "Email", "Affiliations", "epi-ID"]
    )
    print(f"Found {len(users_list)} users")
    return df_users


################################################################


def getAuthors(conn):
    papers = conn.list_papers()
    authors_list = []
    for p in tqdm(papers):
        p = epi.episciences_api.QueryAbleObject(p)
        status1 = epi.EpisciencesDB.getStatusFromCode(p.status)

        try:
            p = conn.get_paper(p.paperid)
        except Exception:
            continue

        status2 = p.status.en
        url = p.database.current[0]["url"]

        authors = epi.episciences_api.QueryAbleObject(p.contributors.person_name[0])
        if not isinstance(authors.json, list):
            authors = [authors]
        for author in authors:
            # print(author)

            affs = author.get("institution_name", "Unknown")
            auth = [
                author.get("given_name", "Unknown"),
                author.surname,
                author.get("ORCID", "Unknown"),
                affs,
                url,
                status1,
                status2,
            ]
            authors_list.append(auth)

    df_authors = pd.DataFrame(
        authors_list,
        columns=[
            "GivenName",
            "Surname",
            "ORCID",
            "Affiliations",
            "Paper",
            "Status1",
            "Status2",
        ],
    )
    # print(df_authors)
    print(f"Found {len(df_authors)} authors")
    return df_authors


################################################################


def main():
    conn = epi.EpisciencesDB()
    authors = getAuthors(conn)
    users = getUsers(conn)

    df_merged = pd.merge(users, authors, on=["GivenName", "Surname"], how="outer")

    df_merged["Affiliations"] = (
        df_merged["Affiliations_x"].fillna("").apply(lambda x: str(x))
        + " "
        + df_merged["Affiliations_y"].fillna("").apply(lambda x: str(x))
    )

    # Drop the old columns
    df_merged = df_merged.drop(columns=["Affiliations_x", "Affiliations_y"])
    df_merged = df_merged.drop_duplicates()
    print(df_merged)
    df_merged.to_csv("users.csv")
    df_merged.to_excel("users.xlsx")


if __name__ == "__main__":
    main()
