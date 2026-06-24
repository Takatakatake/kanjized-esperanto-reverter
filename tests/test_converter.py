"""Unit tests for the reverse converter core and the reverter-CSV build helper.

Covers the bug classes fixed in 2026-06: the dio trailing-comma artifact (神ᴰ must
reverse to dio) and the x-system leak (igx must become iĝ), plus the core greedy
longest-match, passthrough/lowercasing, priority tie-break, and CSV header detection.
"""
import pandas as pd

from esperanto_converter import (
    build_mapping_index,
    convert_kanji_esperanto_to_alphabet,
    dataframe_to_mapping_records,
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
    # Order rows so the priority winner is NOT also the source-order winner: 'low' (priority 10)
    # comes first by source order, but 'high' (priority 1) must still win on priority. This
    # isolates the tie-break — the test would fail if priority were dropped from the sort key.
    mapping = _mapping([("low", "同", 10), ("high", "同", 1)])
    assert convert_kanji_esperanto_to_alphabet("同", mapping) == "high"


def test_dio_reverts_after_comma_fix():
    # Regression for the 神ᴰ, trailing-comma artifact (stripped in the Monaco build tool):
    # with the clean key 神ᴰ, realistic input 神ᴰ reverses to dio.
    mapping = _mapping([("dio", "神ᴰ", 0), ("di", "神", 1)])
    assert convert_kanji_esperanto_to_alphabet("神ᴰ", mapping) == "dio"
    assert convert_kanji_esperanto_to_alphabet("神", mapping) == "di"
    # Document WHY stripping matters: if the comma had leaked into the key (神ᴰ,), realistic
    # input 神ᴰ (no comma) would NOT reach dio — it falls back to 神 -> di plus a leftover ᴰ.
    buggy = _mapping([("dio", "神ᴰ,", 0), ("di", "神", 1)])
    assert convert_kanji_esperanto_to_alphabet("神ᴰ", buggy) != "dio"


def test_correlative_uppercase_vowel_still_matches():
    # Regression for case-sensitivity: an uppercased ASCII suffix vowel (sentence-start /
    # auto-capitalize) must still match the lowercase-stored correlative key.
    mapping = _mapping([("ĉio", "全o", 0), ("integr", "全", 1), ("kia", "何a", 0)])
    assert convert_kanji_esperanto_to_alphabet("全o", mapping) == "ĉio"
    assert convert_kanji_esperanto_to_alphabet("全O", mapping) == "ĉio"
    assert convert_kanji_esperanto_to_alphabet("何A", mapping) == "kia"


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


def test_combining_breve_element_round_trips():
    # 金ᴱᵁ̆ (europium) encodes its identifier as MODIFIER LETTER CAPITAL U (U+1D41) + a separate
    # COMBINING BREVE (U+0306). The full multi-codepoint key must match — a regression guard so the
    # combining mark stays intact and a shorter key like 金ᴱ (erbium) does not shadow it.
    mapping = _mapping([("eŭropi", "金ᴱᵁ̆", 0), ("erbi", "金ᴱ", 1), ("or", "金", 2)])
    assert convert_kanji_esperanto_to_alphabet("金ᴱᵁ̆", mapping) == "eŭropi"
    assert convert_kanji_esperanto_to_alphabet("金ᴱ", mapping) == "erbi"


def test_dataframe_to_mapping_records_is_behaviour_preserving():
    # The vectorized records builder must produce the same (esperanto, kanji, priority) string
    # tuples a per-row construction would, including int priority coerced to str.
    df = pd.DataFrame({"esperanto": ["bon", "fic"], "kanji": ["良", "藻ᶠᶜ"], "priority": [0, 1]})
    assert dataframe_to_mapping_records(df) == (("bon", "良", "0"), ("fic", "藻ᶠᶜ", "1"))


def test_read_csv_2col_headerless(tmp_path):
    path = tmp_path / "d.csv"
    path.write_text("li,他\nmi,我\n", encoding="utf-8")
    df = read_assignment_csv(path)
    assert list(df["kanji"]) == ["他", "我"]
