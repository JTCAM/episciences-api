#!/usr/bin/env python3

from jsonpath_ng.ext import parse
import json
import markdown
import episciences as epi

with open("papers.json") as f:
    f = f.read()
    f = json.loads(f)

expr = parse("$[?(@.document.database.current.status.label.en == 'published')]")
matches = [match.value for match in expr.find(f)]

with open("papers.md", "w") as f:

    cpt = 1
    for m in matches:
        m = epi.episciences_api.EpiSciencesPaper(m)
        name = list(zip(m.contributors.given_name, m.contributors.surname))
        name = [" ".join(e) for e in name]
        if "2025" not in m.document.database.current.publication_date:
            continue
        print(
            f"{cpt:2d}. ",
            f"[{m.journal.title}](https://doi.org/{m.doi_data[0]['doi']})  ",
            file=f,
        )
        print("    ", ", ".join(name), "  ", file=f)

        print(
            "    ",
            m.document.database.current.status.label.en,
            m.document.database.current.publication_date,
            file=f,
        )
        print("", file=f)
        cpt += 1


with open("papers.md", "r", encoding="utf-8") as f:
    md_text = f.read()

html = markdown.markdown(md_text, extensions=["extra", "tables", "fenced_code"])

with open("papers.html", "w", encoding="utf-8") as f:
    f.write(html)
