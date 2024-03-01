#!/bin/env python
import json
import episcience_api as epi
import argparse
################################################################

parser = argparse.ArgumentParser()
parser.add_argument("paper", type=str,
                    help="Provide the paper to extract information from")
args = parser.parse_args()

conn = epi.EpiscienceDB()
u = conn.get_paper(args.paper)
with open('paper.json', 'w') as f:
    f.write(json.dumps(u))

print('record:', u['record'])
for k, v in u.items():
    print(f'{k}: {v}')

