#!/usr/bin/env python3

from jsonpath_ng.ext import parse
import json
import episciences as epi

with open("papers.json") as f:
    f = f.read()
    f = json.loads(f)
    # f = f[:1]
    expr = parse("$[?(@.document.database.current.status.label.en == 'published')]")
    matches = [match.value for match in expr.find(f)]

    cpt = 1
    for m in matches:
        m = epi.episciences_api.EpiSciencesPaper(m)
        name = list(zip(m.contributors.given_name, m.contributors.given_name))
        name = [" ".join(e) for e in name]
        if "2025" not in m.document.database.current.publication_date:
            continue
        print(f"{cpt:2d}. ", m.journal.title)
        print("    ", ", ".join(name))

        print(
            "    ",
            m.document.database.current.status.label.en,
            m.document.database.current.publication_date,
        )
        print("    ", "https://doi.org/" + m.doi_data[0]["doi"])
        print("")
        cpt += 1
