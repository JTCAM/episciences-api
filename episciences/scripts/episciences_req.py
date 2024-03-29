#!/bin/env python
import json
import episciences as epi
import argparse
################################################################


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("paper", type=str,
                        help="Provide the paper to extract information from")
    args = parser.parse_args()

    conn = epi.EpisciencesDB()
    p = conn.get_paper(args.paper)
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


if __name__ == "__main__":
    main()
