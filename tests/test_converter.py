"""Unit tests for the reverse converter core and the reverter-CSV build helper.

Covers the bug classes fixed in 2026-06: the dio trailing-comma artifact (神ᴰ must
reverse to dio) and the x-system leak (igx must become iĝ), plus the core greedy
longest-match, passthrough/lowercasing, priority tie-break, and CSV header detection.
"""
import pandas as pd

from esperanto_converter import (
    build_mapping_index,
    convert_kanji_esperanto_to_alphabet,
    read_assignment_csv,
)
from build_reverter_dictionary_from_all_json import to_unicode_esperanto_root


def _mapping(rows):
    df = pd.DataFrame(rows, columns=["esperanto", "kanji", "priority"])
    return build_mapping_index(df)


# --- to_unicode_esperanto_root: notation normalisation ---------------------------------

def test_caret_notation_to_unicode():
    assert to_unicode_esperanto_root("c^i") == "ĉi"
    assert to_unicode_esperanto_root("h^ameleon") == "ĥameleon"


def test_xsystem_notation_to_unicode():
    # Regression for the 'igx' bug: x-system digraphs must become real diacritics.
    assert to_unicode_esperanto_root("igx") == "iĝ"
    assert to_unicode_esperanto_root("sxangx") == "ŝanĝ"
    assert to_unicode_esperanto_root("auxto") == "aŭto"


def test_comma_variant_keeps_first_alias():
    assert to_unicode_esperanto_root("dio,Di") == "dio"


def test_plain_root_and_fallback():
    assert to_unicode_esperanto_root("bon") == "bon"
    assert to_unicode_esperanto_root("", "bon") == "bon"


# --- convert_kanji_esperanto_to_alphabet: core behaviour ------------------------------

def test_greedy_longest_match_prefers_superscript_keys():
    mapping = _mapping([("fic", "藻ᶠᶜ", 0), ("bangi", "藻ᴮ", 0), ("alg", "藻", 0)])
    assert convert_kanji_esperanto_to_alphabet("藻ᶠᶜoj 藻ᴮoj 藻oj", mapping) == "ficoj bangioj algoj"


def test_passthrough_and_lowercase():
    mapping = _mapping([("bon", "良", 0)])
    assert convert_kanji_esperanto_to_alphabet("ABC 良 Xyz", mapping) == "abc bon xyz"


def test_priority_tiebreak_lower_priority_wins():
    mapping = _mapping([("high", "同", 1), ("low", "同", 10)])
    assert convert_kanji_esperanto_to_alphabet("同", mapping) == "high"


def test_dio_reverts_after_comma_fix():
    # Regression for the 神ᴰ, trailing-comma artifact: clean 神ᴰ must reverse to dio.
    mapping = _mapping([("dio", "神ᴰ", 0), ("di", "神", 1)])
    assert convert_kanji_esperanto_to_alphabet("神ᴰ", mapping) == "dio"
    assert convert_kanji_esperanto_to_alphabet("神", mapping) == "di"


# --- read_assignment_csv: header detection / column mapping ---------------------------

def test_read_csv_5col_with_header(tmp_path):
    path = tmp_path / "d.csv"
    path.write_text(
        "esperanto,kanji,priority,source_root,source_line\nbon,良,0,bon,1\n",
        encoding="utf-8",
    )
    df = read_assignment_csv(path)
    assert list(df["esperanto"]) == ["bon"]
    assert list(df["kanji"]) == ["良"]


def test_read_csv_2col_headerless(tmp_path):
    path = tmp_path / "d.csv"
    path.write_text("li,他\nmi,我\n", encoding="utf-8")
    df = read_assignment_csv(path)
    assert list(df["kanji"]) == ["他", "我"]
