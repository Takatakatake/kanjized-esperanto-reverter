from __future__ import annotations

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
    "legacy-minimal": {
        "label": "旧スニペット最小CSV",
        "path": LEGACY_CSV,
        "description": "このリポジトリに元から入っていた最小対応表です。",
    },
}
DEFAULT_DICTIONARY_ID = "pejvo-piv-20260620"


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


def load_dictionary_source(source_id: str) -> pd.DataFrame:
    source = DICTIONARY_SOURCES[source_id]
    path = source["path"]
    if not path.exists():
        raise FileNotFoundError(f"Dictionary file was not found: {path}")
    return read_assignment_csv(path)


def _priority(value, fallback: int) -> int:
    try:
        return int(str(value).strip())
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


def convert_kanji_esperanto_to_alphabet(text: str, mapping: MappingIndex) -> str:
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

        mapping = build_mapping_index(df)
        st.success(f"{dictionary_label(source_id)} を読み込みました")

        if st.button("変換する", type="primary", use_container_width=True):
            converted_text = convert_kanji_esperanto_to_alphabet(input_text, mapping)
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
            - 旧スニペット最小 CSV とカスタム CSV も選択できます。
            - 上付き識別子を含む漢字表記を、長いものから優先して戻します。
            - 同じ長さの候補は `priority` の小さいものを優先します。
            """
        )


if __name__ == "__main__":
    main()
