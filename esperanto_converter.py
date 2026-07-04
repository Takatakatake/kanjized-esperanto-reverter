from __future__ import annotations

import string
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

import pandas as pd
import streamlit as st


ROOT = Path(__file__).resolve().parent
LEGACY_CSV = ROOT / "エスペラント語根-漢字対応表_スニペット用最小限.csv"
PEJVO_PIV_20260620_CSV = ROOT / "data" / "pejvo_piv_20260620_reverter.csv"

DICTIONARY_SOURCES = {
    "pejvo-piv-20260620": {
        "label": "PEJVO/PIV 2026-06-20",
        "path": PEJVO_PIV_20260620_CSV,
        "description": "新しい漢字割当案。上付き識別子を含む漢字表記から語根へ戻します。",
    },
    # ID は後方互換（セッションキー）のため "legacy-minimal" のまま。中身は
    # 2026-07-04 に現行の漢字割当（全語根）を2列スニペット形式で再生成済み。
    "legacy-minimal": {
        "label": "スニペット用2列CSV（現行割当）",
        "path": LEGACY_CSV,
        "description": "現行の漢字割当を2列（語根,漢字）で収めたスニペット用CSVです。変換結果は PEJVO/PIV 2026-06-20 版と同じになります。",
    },
}
DEFAULT_DICTIONARY_ID = "pejvo-piv-20260620"
CONVERTED_TEXT_KEY = "converted_text"
CONVERTED_INPUT_KEY = "converted_input_text"
CONVERTED_SOURCE_KEY = "converted_source_signature"

# Fold ONLY ASCII A-Z. The 20 correlative keys (何a/全o/无u/某e/那o …) store their suffix
# vowel in lowercase, so an uppercased vowel in the input (sentence-start / auto-capitalize)
# would otherwise fail to match. Verified that no dictionary key contains uppercase ASCII,
# so this never breaks a match; kanji and superscript identifiers (ᴬᴰ…) are left untouched.
_ASCII_LOWER = str.maketrans(string.ascii_uppercase, string.ascii_lowercase)

# Defensive cap for user-uploaded custom dictionaries (the bundled dict is ~0.17 MB).
# Streamlit's default maxUploadSize is 200 MB; a few-MB CSV can still hold millions of rows
# and freeze the worker, so reject oversized uploads before parsing.
MAX_UPLOAD_BYTES = 5 * 1024 * 1024


@dataclass(frozen=True)
class MappingEntry:
    kanji: str
    esperanto: str
    priority: int
    source_order: int


@dataclass(frozen=True)
class MappingIndex:
    by_length: Dict[int, Dict[str, str]]
    lengths_desc: List[int]
    entry_count: int

    @property
    def max_length(self) -> int:
        return self.lengths_desc[0] if self.lengths_desc else 0


def read_assignment_csv(source) -> pd.DataFrame:
    raw = pd.read_csv(source, header=None, dtype=str, keep_default_na=False)
    if raw.shape[1] < 2:
        raise ValueError("CSV must have at least two columns: esperanto, kanji")

    first_row = [str(value).strip().lower() for value in raw.iloc[0].tolist()]
    esperanto_headers = {"esperanto", "エスペラント語根", "語根"}
    kanji_headers = {"kanji", "漢字", "漢字表記"}
    priority_headers = {"priority", "優先順位", "漢字化優先順位"}
    has_header = any(value in esperanto_headers for value in first_row) and any(
        value in kanji_headers for value in first_row
    )
    if has_header:
        header = first_row
        raw = raw.iloc[1:].reset_index(drop=True)
        esperanto_col = next(index for index, value in enumerate(header) if value in esperanto_headers)
        kanji_col = next(index for index, value in enumerate(header) if value in kanji_headers)
        priority_col = next(
            (index for index, value in enumerate(header) if value in priority_headers),
            None,
        )
    else:
        esperanto_col = 0
        kanji_col = 1
        priority_col = 2 if raw.shape[1] >= 3 else None

    data = {
        "esperanto": raw.iloc[:, esperanto_col],
        "kanji": raw.iloc[:, kanji_col],
    }
    if priority_col is not None:
        data["priority"] = raw.iloc[:, priority_col]
    else:
        data["priority"] = range(len(raw))
    return pd.DataFrame(data)


@st.cache_data(show_spinner=False)
def read_assignment_csv_from_path(path_text: str, mtime_ns: int) -> pd.DataFrame:
    return read_assignment_csv(Path(path_text))


def load_dictionary_source(source_id: str) -> pd.DataFrame:
    source = DICTIONARY_SOURCES[source_id]
    path = source["path"]
    if not path.exists():
        raise FileNotFoundError(f"Dictionary file was not found: {path}")
    return read_assignment_csv_from_path(str(path), path.stat().st_mtime_ns)


def _priority(value, fallback: int) -> int:
    try:
        # Parse via float() so a custom CSV that writes priorities as '1.0' is honoured
        # rather than silently dropped to source order.
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return fallback


def create_mapping_entries(df: pd.DataFrame) -> List[MappingEntry]:
    entries: List[MappingEntry] = []
    for source_order, row in df.iterrows():
        esperanto = str(row.get("esperanto", "")).strip().lower()
        kanji = str(row.get("kanji", "")).strip()
        if not esperanto or not kanji or kanji.lower() == "nan":
            continue
        entries.append(
            MappingEntry(
                kanji=kanji,
                esperanto=esperanto,
                priority=_priority(row.get("priority"), int(source_order)),
                source_order=int(source_order),
            )
        )
    return entries


def build_mapping_index(df: pd.DataFrame) -> MappingIndex:
    entries = create_mapping_entries(df)
    entries.sort(key=lambda entry: (-len(entry.kanji), entry.priority, entry.source_order))

    by_length: Dict[int, Dict[str, str]] = {}
    for entry in entries:
        bucket = by_length.setdefault(len(entry.kanji), {})
        if entry.kanji not in bucket:
            bucket[entry.kanji] = entry.esperanto

    return MappingIndex(
        by_length=by_length,
        lengths_desc=sorted(by_length.keys(), reverse=True),
        entry_count=sum(len(bucket) for bucket in by_length.values()),
    )


def dataframe_to_mapping_records(df: pd.DataFrame) -> tuple[tuple[str, str, str], ...]:
    # Vectorized column extraction instead of df.iterrows() (which materialises a Series per
    # row). This builds the cache key on every Streamlit rerun, so it must be cheap; the
    # tuple output is byte-identical to the previous per-row construction.
    def column(name: str) -> list[str]:
        if name in df.columns:
            return [str(value) for value in df[name].tolist()]
        return [""] * len(df)

    return tuple(zip(column("esperanto"), column("kanji"), column("priority")))


@st.cache_data(show_spinner=False)
def build_mapping_index_cached(records: tuple[tuple[str, str, str], ...]) -> MappingIndex:
    df = pd.DataFrame(records, columns=["esperanto", "kanji", "priority"])
    return build_mapping_index(df)


def convert_kanji_esperanto_to_alphabet(text: str, mapping: MappingIndex) -> str:
    # Make the ASCII portion case-insensitive so uppercased correlative suffix vowels still
    # match (e.g. 全O -> ĉio, not the base 全 -> integro). The output is fully lowercased anyway.
    text = text.translate(_ASCII_LOWER)
    result: List[str] = []
    i = 0
    while i < len(text):
        matched = False
        for length in mapping.lengths_desc:
            if length > len(text) - i:
                continue
            substring = text[i : i + length]
            replacement = mapping.by_length[length].get(substring)
            if replacement is None:
                continue
            result.append(replacement)
            i += length
            matched = True
            break

        if not matched:
            result.append(text[i])
            i += 1

    return "".join(result).lower()


def load_selected_dataframe(source_id: str, uploaded_file) -> pd.DataFrame | None:
    try:
        if source_id == "custom":
            if uploaded_file is None:
                return None
            size = getattr(uploaded_file, "size", 0) or 0
            if size > MAX_UPLOAD_BYTES:
                st.error(
                    f"アップロードされたCSVが大きすぎます（{size / 1024 / 1024:.1f} MB）。"
                    f"{MAX_UPLOAD_BYTES // 1024 // 1024} MB 以下にしてください。"
                )
                return None
            return read_assignment_csv(uploaded_file)
        return load_dictionary_source(source_id)
    except Exception as exc:
        st.error(f"対応表の読み込みに失敗しました: {exc}")
        return None


def dictionary_options() -> List[str]:
    return list(DICTIONARY_SOURCES.keys()) + ["custom"]


def dictionary_label(source_id: str) -> str:
    if source_id == "custom":
        return "カスタム CSV"
    return DICTIONARY_SOURCES[source_id]["label"]


def selected_source_signature(source_id: str, uploaded_file) -> str:
    if source_id != "custom":
        # Fold the file mtime into the signature so an on-disk dictionary change invalidates a
        # previously-converted result (otherwise it would still show as "current").
        path = DICTIONARY_SOURCES.get(source_id, {}).get("path")
        try:
            return f"{source_id}:{path.stat().st_mtime_ns}" if path is not None else source_id
        except OSError:
            return source_id
    if uploaded_file is None:
        return "custom:none"
    size = getattr(uploaded_file, "size", "")
    name = getattr(uploaded_file, "name", "uploaded.csv")
    return f"custom:{name}:{size}"


def render_sidebar() -> tuple[str, object | None]:
    with st.sidebar:
        st.header("漢字割当案")
        source_id = st.selectbox(
            "変換に使う割当案",
            dictionary_options(),
            index=dictionary_options().index(DEFAULT_DICTIONARY_ID),
            format_func=dictionary_label,
        )

        uploaded_file = None
        if source_id == "custom":
            uploaded_file = st.file_uploader(
                "対応表 CSV をアップロード",
                type=["csv"],
                help="CSV形式: esperanto,kanji または esperanto,kanji,priority",
            )
        else:
            st.caption(DICTIONARY_SOURCES[source_id]["description"])

        st.markdown("---")
        st.markdown("### 使い方")
        st.markdown(
            """
            1. 割当案を選びます。
            2. 漢字化エスペラント文を入力します。
            3. 変換ボタンをクリックします。
            4. アルファベットの小文字語根へ戻します。
            """
        )
        st.caption("変換は、上付き識別子を含む漢字表記の長さ降順、同じ長さでは priority 昇順で行います。")

    return source_id, uploaded_file


def sample_text() -> str:
    return (
        "何时 西o 遇as 东on 和ᴷ 上置as 东an 衣on, 一 唯a 语o 获as 二 显ojn "
        "— 两 美ajn —, 和ᴷ 生成as 新a 解o."
    )


def main() -> None:
    st.set_page_config(
        page_title="漢字化エスペラント → アルファベット変換",
        page_icon="🔤",
        layout="wide",
    )

    st.title("漢字化エスペラント → アルファベット変換")
    st.markdown("---")

    source_id, uploaded_file = render_sidebar()
    df = load_selected_dataframe(source_id, uploaded_file)
    source_signature = selected_source_signature(source_id, uploaded_file)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("入力（漢字化エスペラント）")
        input_text = st.text_area(
            "漢字化エスペラント文",
            value=sample_text(),
            height=320,
            help="漢字とアルファベットが混在した文章を入力してください。",
        )

    with col2:
        st.subheader("出力（アルファベット）")
        if df is None:
            st.info("対応表を選択またはアップロードしてください。")
            return

        mapping = build_mapping_index_cached(dataframe_to_mapping_records(df))
        st.success(f"{dictionary_label(source_id)} を読み込みました")

        if st.button("変換する", type="primary", use_container_width=True):
            converted_text = convert_kanji_esperanto_to_alphabet(input_text, mapping)
            st.session_state[CONVERTED_TEXT_KEY] = converted_text
            st.session_state[CONVERTED_INPUT_KEY] = input_text
            st.session_state[CONVERTED_SOURCE_KEY] = source_signature

        converted_text = st.session_state.get(CONVERTED_TEXT_KEY, "")
        result_is_current = (
            st.session_state.get(CONVERTED_INPUT_KEY) == input_text
            and st.session_state.get(CONVERTED_SOURCE_KEY) == source_signature
        )

        if converted_text:
            if not result_is_current:
                st.warning("入力または割当案が変わっています。再変換してください。")
            st.text_area(
                "変換結果",
                value=converted_text,
                height=320,
                help="すべて小文字のエスペラント語根として出力します。",
            )
            st.download_button(
                label="テキストをダウンロード",
                data=converted_text,
                file_name="converted_esperanto.txt",
                mime="text/plain",
                use_container_width=True,
            )

            if result_is_current:
                st.markdown("---")
                col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
                col_stat1.metric("入力文字数", len(input_text))
                col_stat2.metric("出力文字数", len(converted_text))
                col_stat3.metric("辞書エントリ数", mapping.entry_count)
                col_stat4.metric("最長エントリ", f"{mapping.max_length}文字")
        else:
            st.info("変換ボタンをクリックしてください。")

    st.markdown("---")
    with st.expander("このアプリについて"):
        st.markdown(
            """
            このアプリは、漢字化エスペラントを元の小文字エスペラント語根へ戻すツールです。

            - 新しい `PEJVO/PIV 2026-06-20` 割当案に対応しています。
            - スニペット用2列CSV（現行割当）とカスタム CSV も選択できます。
            - 上付き識別子を含む漢字表記を、長いものから優先して戻します。
            - 同じ長さの候補は `priority` の小さいものを優先します。
            - 注意: 漢字には語根の区切りが無いため、隣接語根が連結して別の長いキーと一致する
              凝集複合語（例: 酸乳 = acid+lakt が jogurt と一致）は別の語に戻ることがあります。
            """
        )


if __name__ == "__main__":
    main()
