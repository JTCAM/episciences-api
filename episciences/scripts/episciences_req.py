#!/bin/env python
import json
import yaml
import episciences as epi
import argparse
################################################################


def printPaperDetail(paper_id, conn):
    p = conn.get_paper(paper_id)
    with open('paper.json', 'w') as f:
        f.write(json.dumps(p.json))

    print('Title:', p.title)
    print('Authors:', '; '.join(p.creator))
    print('Status:', p.status)
    print('submissionDate:', p.submissionDate)
    print('Date:', p.date)
    print('Description:', p.description)
    print('Identifiers:', ', '.join(p.identifier))
    print('Available_fields:', dir(p))
    json_formatted_str = json.dumps(p.json, indent=2)
    print('Full_content:\n', json_formatted_str)

################################################################


def printPapersSummary(conn):
    papers = conn.list_papers()

    # users = conn.list_users()
    users = conn.list_users()
    users = dict([(e['@id'], e['screenName']) for e in users])
    # print(users)
    for e in papers:
        print('paperID:', e['@id'])
        if 'user' in e:
            auth_id = e['user']['@id']
            if auth_id in users:
                user = users[auth_id]
            else:
                user = ('not found: ', e['user'])

            print('Author:', user)
        if '@type' in e:
            print('Type:', e['@type'])
        if 'editors' in e and e['editors']:
            print('Editors: ', e['editors'].keys())
        if 'review' in e and e['review']:
            print('Review: ', e['review'])
        if 'copyEditors' in e and e['copyEditors']:
            print('CopyEditors: ', e['copyEditors'].keys())
        if 'status' in e:
            if e['status'] in epi.EpisciencesDB.status_codes:
                code = epi.EpisciencesDB.status_codes[e['status']]
            else:
                code = "Unknown"
            print('Status: ', code)

        print(e.keys())
        print('*'*70)

    print(f"Found {len(papers)} papers")

################################################################


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--paper", default=None, type=str,
                        help="Provide the paper to extract information from")

    parser.add_argument("--details", action='store_true',
                        help="Ask for full details")

    parser.add_argument("--cmd", default=None, type=str,
                        help="Provide a command to the api")

    args = parser.parse_args()

    conn = epi.EpisciencesDB()
    if args.paper:
        printPaperDetail(args.paper, conn)
    if args.cmd:
        r = conn.epi_get(args.cmd)
        print(yaml.dump(r))
    else:
        printPapersSummary(conn)


if __name__ == "__main__":
    main()
