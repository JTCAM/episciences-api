#!/bin/env python
import episciences as epi
import solidipes as sp
import subprocess
import os
import argparse

################################################################


def fetch_info(args):
    conn = epi.EpisciencesDB(token=args.token)
    p = conn.get_paper(args.paper)
    print("Title:", p.title)
    surnames = [f"{e.given_name} {e.surname}" for e in p.contributors.person_name]
    print("Authors:", "; ".join(surnames))
    aff = [f"{e.affiliations}" for e in p.contributors.person_name]
    print("Affiliations:", aff)
    print("Status:", p.status)
    if p.dates:
        print("Dates:")
        for d, v in p.dates.items():
            print(f"\t- {d}: {v}")
    print("Abstract:", p.abstract)
    print("Files:", ", ".join(p.files))
    print(p.keywords)
    print("Keywords:", ", ".join(p.keywords))
    print("Available_fields:", dir(p))
    return p


################################################################


def create_repo(p, args):
    os.mkdir(args.loc)
    subprocess.call(
        "renku init -s https://gitlab.com/dcsm/renku-templates -t jtcam",
        shell=True,
        cwd=args.loc,
    )
    return p


################################################################


def set_study_metadata(p, args):
    cwd = os.getcwd()
    os.chdir(args.loc)
    zenodo_metadata = sp.utils.get_study_metadata()
    zenodo_metadata["title"] = p.title
    zenodo_metadata["related_identifiers"] = []
    if isinstance(p.files, str):
        p.files = [p.files]
    elif not isinstance(p.files, list):
        p.files = [p.files]
    for _id in p.files:
        zenodo_metadata["related_identifiers"].append(
            {
                "identifier": _id,
                "relation": "isCitedBy",
                "resource_type": "publication-article",
            }
        )

    # st.markdown("### *" + '; '.join(p.creator) + "*")

    zenodo_metadata["creators"] = []
    for e in p.contributors.person_name:
        if not isinstance(e.affiliations.institution, list):
            e.affiliations.institution = [e.affiliations.institution]
        e.affiliations.institution = [
            i.institution_name for i in e.affiliations.institution
        ]
        e.affiliations.institution = ";".join(e.affiliations.institution)
        zenodo_metadata["creators"].append(
            {
                "name": f"{e.given_name} {e.surname}",
                "affiliation": e.affiliations.institution,
                "orcid": f"{e.ORCID.replace('https://orcid.org/', '')}",
            }
        )

    if hasattr(p, "abstract"):
        zenodo_metadata["description"] += (
            """
Paper Description
-----------------

"""
            + p.abstract
        )

    zenodo_metadata["keywords"] = []
    zenodo_metadata["keywords"] += p.keywords
    for k, v in zenodo_metadata.items():
        print(f"{k}: {v}")

    sp.utils.set_study_metadata(zenodo_metadata)
    os.chdir(cwd)


################################################################


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "paper", type=str, help="Provide the paper to extract information from"
    )
    parser.add_argument(
        "--token", type=str, help="Provide the token to log to episcience api"
    )

    args = parser.parse_args()

    args.loc = f"jtcam-data-{args.paper}"
    paper = fetch_info(args)
    # create_repo(paper, args)
    set_study_metadata(paper, args)


if __name__ == "__main__":
    main()
