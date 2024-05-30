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
    print('Title:', p.title)
    print('Authors:', '; '.join(p.creator))
    print('Status:', p.status)
    # print('submissionDate:', p.submissionDate)
    # print('Date:', p.date)
    # print('Description:', p.description)
    # print('Identifiers:', ', '.join(p.identifier))
    # print('Subject:', str(p.subject))
    # print('Available_fields:', dir(p))
    return p

################################################################


def create_repo(p, args):
    os.mkdir(args.loc)
    subprocess.call(
        'renku init -s https://gitlab.com/dcsm/renku-templates -t jtcam', shell=True, cwd=args.loc)
    return p

################################################################


def set_study_metadata(p, args):
    cwd = os.getcwd()
    os.chdir(args.loc)
    zenodo_metadata = sp.utils.get_study_metadata()
    zenodo_metadata['title'] = p.title
    zenodo_metadata['related_identifiers'] = []
    for _id in p.identifier:
        zenodo_metadata['related_identifiers'].append(
            {'identifier': _id,
             'relation': 'isCitedBy',
             'resource_type': 'publication-article'
             }
        )

    # st.markdown("### *" + '; '.join(p.creator) + "*")

    zenodo_metadata['creators'] = []
    if hasattr(p, 'contributor'):
        for auth, aff in zip(p.creator, p.contributor):
            zenodo_metadata['creators'].append(
                {
                    'affiliation': aff,
                    'name': auth
                }
            )
    else:
        for auth in p.creator:
            zenodo_metadata['creators'].append(
                {
                    'name': auth
                }
            )

    if hasattr(p, 'description'):
        if not isinstance(p.description, str):
            if isinstance(p.description, list):
                p.description = p.description[0]
            if not isinstance(p.description, str):
                p.description = p.description['#text']

        zenodo_metadata['description'] += """
Paper Description
-----------------

""" + p.description

    zenodo_metadata['keywords'] = []
    subject = []
    try:
        subject = p.subject[1:]
    except AttributeError:
        pass
    for s in subject:
        if isinstance(s, dict):
            s = s['#text']
        zenodo_metadata['keywords'].append(s)
    for k, v in zenodo_metadata.items():
        print(f'{k}: {v}')

    sp.utils.set_study_metadata(zenodo_metadata)
    os.chdir(cwd)

################################################################


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("paper", type=str,
                        help="Provide the paper to extract information from")
    parser.add_argument("--token", type=str,
                        help="Provide the token to log to episcience api")

    args = parser.parse_args()

    args.loc = f'jtcam-data-{args.paper}'
    paper = fetch_info(args)
    # create_repo(paper, args)
    set_study_metadata(paper, args)


if __name__ == "__main__":
    main()
