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
    code = paper.status
    status = epi.EpisciencesDB.getStatusFromCode(code)
    print(
        paper["@type"],
        "paperid:",
        paper.paperid,
        "docid:",
        paper.docid,
        "status:",
        f"{status}({code})",
    )


################################################################


def printPapers(conn, args):
    papers = conn.list_papers()

    # users = conn.list_users()
    users = conn.list_users()
    users = dict([(e["@id"], e["screenName"]) for e in users])
    for e in papers:
        e = epi.episciences_api.QueryAbleObject(e)
        status = epi.EpisciencesDB.getStatusFromCode(e.status)

        if args.status is not None and status != args.status:
            continue

        if args.details:
            print("*" * 70)
            print(e)
            try:
                printPaperDetail(e.paperid, conn)
            except epi.episciences_api.HttpErrorCode as e:
                print(e)

        else:
            printPaperNoDetail(e, users)

    print(f"Found {len(papers)} papers")


################################################################


def saveJSON(conn, args):
    papers = conn.list_papers()
    list_papers = []
    from tqdm import tqdm

    for e in tqdm(papers):
        e = epi.episciences_api.QueryAbleObject(e)
        try:
            p = conn.get_paper(e.docid)
        except epi.episciences_api.HttpErrorCode as _e:
            print("error fetching:", e)
            print(_e)
            continue
        list_papers.append(p.json)

    with open("papers.json", "w") as f:
        f.write(json.dumps(list_papers, indent=2, sort_keys=True, ensure_ascii=False))


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

    parser.add_argument("--json", action="store_true", help="Ask to dump to json file")

    parser.add_argument(
        "--cmd", default=None, type=str, help="Provide a command to the api"
    )

    parser.add_argument("--status", default=None, type=str, help="Constaint on status")

    args = parser.parse_args()

    conn = epi.EpisciencesDB()
    if args.paper:
        printPaperDetail(args.paper, conn)
    elif args.json:
        saveJSON(conn, args)
    elif args.cmd:
        r = conn.epi_get(args.cmd)
        print(yaml.dump(r))
    else:
        printPapers(conn, args)


if __name__ == "__main__":
    main()
