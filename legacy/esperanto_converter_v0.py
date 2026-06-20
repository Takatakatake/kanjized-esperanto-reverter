import streamlit as st
import pandas as pd
import io
import re

# ページ設定
st.set_page_config(
    page_title="漢字化エスペラント → アルファベット変換",
    page_icon="🔤",
    layout="wide"
)

def load_default_csv():
    """デフォルトのCSVファイルを読み込む"""
    default_csv_path = "./エスペラント語根-漢字対応表_スニペット用最小限.csv"
    try:
        df = pd.read_csv(default_csv_path, header=None, names=['esperanto', 'kanji'])
        return df
    except Exception as e:
        st.error(f"デフォルトCSVファイルの読み込みに失敗しました: {e}")
        return None

def create_kanji_to_esperanto_dict(df):
    """漢字→エスペラント語根の辞書を作成"""
    kanji_dict = {}
    for _, row in df.iterrows():
        esperanto = str(row['esperanto']).strip()
        kanji = str(row['kanji']).strip()
        
        # 空の値や nan をスキップ
        if pd.isna(kanji) or kanji == '' or kanji == 'nan':
            continue
            
        # 漢字とその後の特殊文字を一緒にキーとする
        kanji_dict[kanji] = esperanto
    
    return kanji_dict

def convert_kanji_esperanto_to_alphabet(text, kanji_dict):
    """漢字化エスペラントをアルファベットのエスペラントに変換"""
    result = []
    i = 0
    
    while i < len(text):
        # 空白文字はそのまま保持
        if text[i].isspace():
            result.append(text[i])
            i += 1
            continue
        
        # ASCII文字（アルファベット、数字、記号）はそのまま保持
        if ord(text[i]) < 128 or text[i] in '.,!?;:\'"()[]{}+-*/<>=':
            result.append(text[i])
            i += 1
            continue
        
        # エスペラントの特殊文字（ĉ, ĝ, ĥ, ĵ, ŝ, ŭなど）もそのまま保持
        if text[i] in 'ĉĈĝĜĥĤĵĴŝŜŭŬ':
            result.append(text[i])
            i += 1
            continue
        
        # 漢字とその後の特殊文字を探す
        found = False
        # 最大5文字先まで確認（漢字 + 特殊文字の可能性）
        for length in range(min(5, len(text) - i), 0, -1):
            substring = text[i:i+length]
            if substring in kanji_dict:
                result.append(kanji_dict[substring])
                i += length
                found = True
                break
        
        if not found:
            # 辞書に見つからない場合はそのまま保持
            result.append(text[i])
            i += 1
    
    # すべて小文字に変換
    converted_text = ''.join(result).lower()
    return converted_text

# タイトル
st.title("🔤 漢字化エスペラント → アルファベット変換")
st.markdown("---")

# サイドバー
with st.sidebar:
    st.header("📋 CSVファイル設定")
    
    use_custom_csv = st.checkbox("カスタムCSVファイルを使用", value=False)
    
    if use_custom_csv:
        uploaded_file = st.file_uploader(
            "エスペラント語根-漢字対応表をアップロード",
            type=['csv'],
            help="CSV形式: エスペラント語根,漢字"
        )
    else:
        uploaded_file = None
        st.info("デフォルトのCSVファイルを使用します")
    
    st.markdown("---")
    st.markdown("### 📖 使い方")
    st.markdown("""
    1. **CSVファイル**: デフォルトまたはカスタムCSVを選択
    2. **入力**: 漢字化エスペラント文を入力
    3. **変換**: 変換ボタンをクリック
    4. **結果**: アルファベットのエスペラントが表示されます
    """)

# メインコンテンツ
col1, col2 = st.columns(2)

with col1:
    st.subheader("📝 入力（漢字化エスペラント）")
    
    # デフォルトの例文
    default_text = """我 听is, ke 间 反更 比 周o 和 从 二 多样aj 人ʜoj 内 反同aj 处ʟoj, ke kumino 很 好e 适as 为 la 羊物a 大盘o "jingisukan".
我 实际e 试is kuminon 共 jingisukan, 和 我 全e 同意as: kumino 真e 好e 协议as kun la 羊物a 大盘o.
从 今, 何时 我 吃os jingisukan, 我 决is 全时 辛i la 肉ᴠon 以 kumino."""
    
    input_text = st.text_area(
        "漢字化エスペラント文を入力してください",
        value=default_text,
        height=300,
        help="漢字とアルファベットが混在した文章を入力してください"
    )

with col2:
    st.subheader("✅ 出力（アルファベット）")
    
    # CSVファイルの読み込み
    if use_custom_csv and uploaded_file is not None:
        try:
            df = pd.read_csv(uploaded_file, header=None, names=['esperanto', 'kanji'])
            st.success("✓ カスタムCSVファイルを読み込みました")
        except Exception as e:
            st.error(f"CSVファイルの読み込みに失敗: {e}")
            df = None
    else:
        df = load_default_csv()
        if df is not None:
            st.success("✓ デフォルトCSVファイルを読み込みました")
    
    # 変換処理
    if df is not None and st.button("🔄 変換する", type="primary", use_container_width=True):
        with st.spinner("変換中..."):
            kanji_dict = create_kanji_to_esperanto_dict(df)
            
            if kanji_dict:
                converted_text = convert_kanji_esperanto_to_alphabet(input_text, kanji_dict)
                
                st.text_area(
                    "変換結果",
                    value=converted_text,
                    height=300,
                    help="すべて小文字のエスペラント文"
                )
                
                # ダウンロードボタン
                st.download_button(
                    label="📥 テキストをダウンロード",
                    data=converted_text,
                    file_name="converted_esperanto.txt",
                    mime="text/plain",
                    use_container_width=True
                )
                
                # 統計情報
                st.markdown("---")
                st.markdown("### 📊 統計")
                col_stat1, col_stat2, col_stat3 = st.columns(3)
                with col_stat1:
                    st.metric("入力文字数", len(input_text))
                with col_stat2:
                    st.metric("出力文字数", len(converted_text))
                with col_stat3:
                    st.metric("辞書エントリ数", len(kanji_dict))
            else:
                st.error("辞書の作成に失敗しました")
    else:
        st.info("👆 変換ボタンをクリックしてください")

# フッター
st.markdown("---")
with st.expander("ℹ️ このアプリについて"):
    st.markdown("""
    ### 漢字化エスペラント → アルファベット変換アプリ
    
    このアプリは、漢字で表現されたエスペラント語根を元のアルファベット表記に戻すツールです。
    
    **特徴:**
    - デフォルトの対応表を使用、またはカスタムCSVファイルをアップロード可能
    - 漢字とアルファベットが混在した文章に対応
    - 特殊文字（ʜ, ɪ, ʟ, ᴠなど）も正しく処理
    - 変換結果はすべて小文字で出力
    
    **CSVファイル形式:**
    ```
    エスペラント語根,漢字
    mi,我
    aŭd,听
    kun,共
    ```
    """)
