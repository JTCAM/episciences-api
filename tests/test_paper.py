"""Tests for EpiSciencesPaper against both API response shapes:
the legacy flat shape and the current nested `document` (JATS) shape."""

import pytest
from episciences.episciences_api import EpiSciencesPaper, EpisciencesDB

NESTED_PAPER = {
    "@context": "/api/contexts/Paper",
    "@id": "/api/papers/20086",
    "@type": "Paper",
    "paperid": 18597,
    "doi": "10.46298/jtcam.18597",
    "document": {
        "journal": {
            "journal_issue": {
                "publication_date": {"day": "04", "year": "2026", "month": "11"}
            },
            "journal_article": {
                "titles": {"title": "A new perspective in linear Cauchy Elasticity"},
                "abstract": {"value": "  We revisit Cauchy elasticity.  ", "@lang": "en"},
                "contributors": {
                    "person_name": [
                        {
                            "given_name": "Alice",
                            "surname": "Smith",
                            "ORCID": "https://orcid.org/0000-0002-0000-0000",
                            "affiliations": {"institution": {"institution_name": "EPFL"}},
                        },
                        {
                            "given_name": "Bob",
                            "surname": "Jones",
                            "affiliations": {
                                "institution": [
                                    {"institution_name": "CNRS"},
                                    {"institution_name": "UPMC"},
                                ]
                            },
                        },
                    ]
                },
            },
        },
        "database": {"current": {"files": {"link": "https://jtcam.episciences.org/20086/pdf"}}},
    },
}

LEGACY_PAPER = {
    "paperid": 12489,
    "docid": 12489,
    "doi": "10.46298/jtcam.12489",
    "status": 19,
    "title": ["Legacy paper title"],
    "abstract": [{"value": "Legacy abstract"}],
    "contributors": {"person_name": [{"given_name": "Carol", "surname": "Danvers"}]},
    "dates": {"first_submission_date": "2021-01-01"},
    "files": ["https://example.org/y.pdf"],
    "keywords": [["elasticity", "waves"]],
}


def test_nested_title():
    p = EpiSciencesPaper(NESTED_PAPER)
    assert p.title == "A new perspective in linear Cauchy Elasticity"


def test_nested_abstract_is_stripped():
    p = EpiSciencesPaper(NESTED_PAPER)
    assert p.abstract == "We revisit Cauchy elasticity."


def test_nested_authors_with_single_and_multiple_affiliations():
    p = EpiSciencesPaper(NESTED_PAPER)
    authors = p.authors
    assert len(authors) == 2
    assert authors[0]["given_name"] == "Alice"
    assert authors[0]["affiliations"] == ["EPFL"]
    assert authors[0]["orcid"] == "https://orcid.org/0000-0002-0000-0000"
    assert authors[1]["affiliations"] == ["CNRS", "UPMC"]


def test_nested_files():
    p = EpiSciencesPaper(NESTED_PAPER)
    assert p.files == ["https://jtcam.episciences.org/20086/pdf"]


def test_status_falls_back_to_list_data():
    p = EpiSciencesPaper(NESTED_PAPER, list_data={"status": 16})
    assert p.status == 16
    assert p.status_label == "Published"


def test_status_unknown_without_list_data():
    p = EpiSciencesPaper(NESTED_PAPER)
    assert p.status is None
    assert p.status_label is None


def test_doi_comes_from_top_level_or_listing_not_bibliography():
    p = EpiSciencesPaper(NESTED_PAPER)
    assert p.doi == "10.46298/jtcam.18597"  # the paper's own DOI
    p = EpiSciencesPaper({"@type": "Paper", "paperid": 1})
    assert p.doi is None  # no bibliography leak
    p = EpiSciencesPaper({"@type": "Paper", "paperid": 1}, list_data={"doi": "10.1/x"})
    assert p.doi == "10.1/x"


def test_docid_falls_back_to_paperid():
    p = EpiSciencesPaper(NESTED_PAPER)
    assert p.docid == 18597


def test_legacy_shape_title_and_status():
    p = EpiSciencesPaper(LEGACY_PAPER)
    assert p.title == "Legacy paper title"
    assert p.status == 19
    assert p.status_label == "Copy editing"


def test_legacy_shape_rest():
    p = EpiSciencesPaper(LEGACY_PAPER)
    assert p.abstract == "Legacy abstract"
    assert p.dates.first_submission_date == "2021-01-01"
    assert p.first_submission_date == "2021-01-01"
    assert p.files == ["https://example.org/y.pdf"]
    assert p.keywords == [["elasticity", "waves"]]
    assert p.docid == 12489
    assert p.doi == "10.46298/jtcam.12489"


def test_title_raises_when_missing():
    p = EpiSciencesPaper({"paperid": 1})
    with pytest.raises(AttributeError):
        p.title


def test_get_or_none():
    p = EpiSciencesPaper({"paperid": 1})
    assert p.get_or_none("nonexistent") is None
    assert p.get_or_none("paperid") == 1


def test_status_label_of_unknown_code():
    assert EpisciencesDB.getStatusFromCode(999) == "Unknown"
    assert EpisciencesDB.getStatusFromCode(16) == "Published"
