#!/bin/env python
import argparse
import json

import episciences as epi
import yaml

################################################################


def printPaperDetail(paper_id, conn):
    try:
        paper_id = paper_id.split("/api/papers/")[1]
    except Exception:
        pass
    p = conn.get_paper(paper_id)
    with open("paper.json", "w") as f:
        f.write(json.dumps(p.json))

    print("Title:", p.title)
    print("Authors:", p.contributors)
    print("Status:", p.status)
    print("Dates:", p.dates)
    print("Abstract:", p.get("abstract", ""))
    print("Identifiers:", p.identifier)


################################################################


def printPaperNoDetail(paper, users):
    print("paperID:", paper["@id"])
    if "@type" in paper:
        print("Type:", paper["@type"])
    if "status" in paper:
        status = epi.EpisciencesDB.getStatusFromCode(paper["status"])
        print("Status: ", status)
    if "user" in paper:
        auth_id = paper["user"]["@id"]
        if auth_id in users:
            user = users[auth_id]
        else:
            user = ("not found: ", paper["user"])

        print("Author:", user)
    if "editors" in paper and paper["editors"]:
        for editor in paper["editors"]:
            if "/api/users/" + editor in users:
                editor = users["/api/users/" + editor]
            print("Editor: ", editor)
    if "review" in paper and paper["review"]:
        print("Review: ", paper["review"])
    if "copyEditors" in paper and paper["copyEditors"]:
        for editor in paper["copyEditors"]:
            if "/api/users/" + editor in users:
                editor = users["/api/users/" + editor]
            print("copyEditor: ", editor)


################################################################


def printPapersSummary(conn, args):
    papers = conn.list_papers()

    # users = conn.list_users()
    users = conn.list_users()
    users = dict([(e["@id"], e["screenName"]) for e in users])
    for e in papers:
        if "status" in e:
            status = epi.EpisciencesDB.getStatusFromCode(e["status"])
        else:
            status = "Unknown"

        if args.status is not None and status != args.status:
            continue

        if args.details:
            print("*" * 70)
            print(e)
            try:
                printPaperDetail(e["paperid"], conn)
            except epi.episciences_api.HttpErrorCode as e:
                print(e)

        else:
            printPaperNoDetail(e, users)

    print(f"Found {len(papers)} papers")


################################################################


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--paper",
        default=None,
        type=str,
        help="Provide the paper to extract information from",
    )

    parser.add_argument("--details", action="store_true", help="Ask for full details")

    parser.add_argument(
        "--cmd", default=None, type=str, help="Provide a command to the api"
    )

    parser.add_argument("--status", default=None, type=str, help="Constaint on status")

    args = parser.parse_args()

    conn = epi.EpisciencesDB()
    if args.paper:
        printPaperDetail(args.paper, conn)
    elif args.cmd:
        r = conn.epi_get(args.cmd)
        print(yaml.dump(r))
    else:
        printPapersSummary(conn, args)


if __name__ == "__main__":
    main()
