import re

import streamlit as st
from app_config import AppConfig
from dotenv import load_dotenv
from kendra_bedrock_query import (
    invokeLLMWithFile,
    invokeLLMWithoutFile,
    kendraSearch,
    ragSearch,
)

# 環境変数をロード
load_dotenv()


# メッセージリストの順序を保証する関数
def ensure_alternating_roles(messages):
    """
    メッセージリストが `user` と `assistant` のロールが交互になるように調整する。
    """
    # メッセージリストが空の場合、エラー回避のためユーザーメッセージが必須
    if not messages:
        raise ValueError(
            "メッセージリストが空です。会話はユーザーメッセージから開始する必要があります。"
        )

    # 最後のメッセージが `assistant` でない場合に調整
    if messages[-1]["role"] != "assistant":
        messages.append({"role": "assistant", "content": [{"text": "準備中..."}]})
    return messages


# session_stateののメッセージを初期化
def initialize_session():
    if "tab_messages" not in st.session_state:
        st.session_state.tab_messages = {
            "rag_search": [],
            "kendra_search": [],
            "multi_modal": [],
        }


# チャットメッセージを表示
def display_tab_messages(
    tab_key, label="過去のやり取り", empty_message="履歴がありません"
):
    """
    過去のメッセージや履歴を折りたたみで表示する汎用関数。
    :param tab_key: session_stateのキー
    :param label: 折りたたみタイトル
    :param empty_message: メッセージが空の場合の表示内容
    """
    # チャット履歴が存在するか確認し、なければ履歴がない旨のメッセージを表示
    if not st.session_state.tab_messages[tab_key]:
        st.info(empty_message)
        return

    # 過去の会話/検索履歴を expander 内にまとめて表示
    with st.expander(label):
        for message in st.session_state.tab_messages[tab_key]:
            with st.chat_message(message["role"]):
                st.markdown(message["content"][0]["text"])


# モデル名の表示を整形
def format_model_key_for_display(key):
    formatted_model_name = key.replace("_", " ").title().replace("3 5 ", " 3.5 ")
    return formatted_model_name


def display_search_results(signed_urls):
    """
    検索結果を上位10件はそのまま表示し、残りは折りたたみで表示する。
    :param signed_urls: 検索結果（辞書のリスト形式）
    """
    if not signed_urls:
        st.info("関連ドキュメントが見つかりませんでした。")
        return

    # 検索結果が10件以下の場合
    if len(signed_urls) <= 10:
        st.write("#### 関連するドキュメント")
        for i, result in enumerate(signed_urls, 1):
            st.markdown(f"{i}. [{result['document_name']}]({result['signed_url']})")
    else:
        # 上位10件を表示
        st.write("#### 関連するドキュメント（上位10件）")
        for i, result in enumerate(signed_urls[:10], 1):
            st.markdown(f"{i}. [{result['document_name']}]({result['signed_url']})")

    # 残りの結果を折りたたみ表示
    if len(signed_urls) > 10:
        with st.expander(
            f"残りの関連ドキュメントを表示（※最大20件）（{len(signed_urls) - 10}件）"
        ):
            for i, result in enumerate(signed_urls[10:], 11):
                st.markdown(f"{i}. [{result['document_name']}]({result['signed_url']})")


# ファイル名のバリデーション
def is_valid_filename(filename):
    # アルファベット、数字、空白（1文字のみ）、ハイフン、括弧が含まれることを確認
    return bool(re.match(r"^[a-zA-Z0-9\s\-\.\(\)\[\]]+$", filename))


# ファイルのサイズチェック（Claudeが受け付ける4.5MBを超えているかどうか）
def is_file_size_valid(uploaded_file):
    return uploaded_file.size <= 4.5 * 1024 * 1024  # 4.5MB


# アプリの初期表示
st.title("Kendra-Bedrock-RAG検証")
initialize_session()


# 表示内容切り替えのためのプルダウン設定
tab_titles = AppConfig.WORDS_USED_IN_EACH_TAB_DICT
selected_tab = st.selectbox(
    "プルダウンで機能を選択",
    options=list(tab_titles.keys()),
    format_func=lambda x: tab_titles[x],
)


# プルダウンで選択された値によって、動的に表示される内容を変更
# RAG検索タブ
if selected_tab == "rag_search":
    st.header(tab_titles["rag_search"])

    # 使用するClaudeのモデルを選択できるようにする
    display_model_options = {
        format_model_key_for_display(k): k for k in AppConfig.MODEL_ID_DICT.keys()
    }
    selected_model_name = st.selectbox(
        "使用する生成AIモデルを選択してください",
        options=display_model_options.keys(),
        index=0,  # デフォルトは"Claude3.5 Sonnet"を選択
    )
    # 選択されたmodelIdを抽出
    selected_model_key = display_model_options[selected_model_name]
    selected_model_id = AppConfig.MODEL_ID_DICT[selected_model_key]

    # Select Temperature
    selected_temperature_key = st.radio(
        "生成AIの回答スタイルを選択してください",
        options=AppConfig.TEMPERATURE_OPTIONS.keys(),
        index=0,  # デフォルトは"厳密に"
    )
    selected_temperature = AppConfig.TEMPERATURE_OPTIONS[selected_temperature_key]

    # 検索対象のドキュメントを選択させる
    category_dict = AppConfig.CATEGORY_LABELS
    # ラジオボタンでカテゴリを選択
    category_labels_to_display = AppConfig.CATEGORY_LABELS.values()
    selected_category_value = st.radio(
        "検索したい資料のカテゴリを選択してください:", category_labels_to_display
    )

    # 選択された日本語ラベルから英語のキーを取得（バックエンドで、categoryをAttributeFilterで絞り込む際に使用。）
    selected_category_key = [
        category_key
        for category_key, category_value in category_dict.items()
        if category_value == selected_category_value
    ][0]

    # サイドバーにKendra検索タブの使い方を追加
    st.sidebar.markdown("### RAG検索の使い方")
    st.sidebar.markdown(AppConfig.HOW_TO_USE_RAG_SEARCH)

    # 会話履歴の表示
    display_tab_messages(
        tab_key="rag_search",
        label="過去の会話履歴",
        empty_message="まだ会話履歴がありません",
    )

    # ユーザーの入力
    user_input = st.chat_input("RAG検索クエリを入力してください")

    if user_input:
        # ユーザーの入力を session stateに格納
        input_msg = {"role": "user", "content": [{"text": user_input}]}
        st.session_state.tab_messages["rag_search"].append(input_msg)
        history = st.session_state.tab_messages["rag_search"]

        # ユーザーの入力を表示
        with st.chat_message("user"):
            st.markdown(user_input)

        try:
            # RAG検索を実行
            with st.spinner("RAG検索実行中..."):
                kendra_response, signed_urls = ragSearch(
                    user_input,
                    history,
                    selected_model_id,
                    selected_temperature,
                    selected_category_key,
                )

            # LLMからのレスポンスをsession stateに格納
            response_msg = {"role": "assistant", "content": [{"text": kendra_response}]}
            st.session_state.tab_messages["rag_search"].append(response_msg)

            # LLM からのレスポンスを表示
            with st.chat_message("assistant"):
                st.markdown(kendra_response)

            # 関連ドキュメントを表示
            display_search_results(signed_urls)

        except Exception as e:
            st.error(f"エラーが発生しました: {e}")


# Kendra検索タブ
elif selected_tab == "kendra_search":
    st.header(tab_titles["kendra_search"])

    # 検索対象のドキュメントを選択させる
    category_dict = AppConfig.CATEGORY_LABELS
    # ラジオボタンでカテゴリを選択
    category_labels_to_display = AppConfig.CATEGORY_LABELS.values()
    selected_category_value = st.radio(
        "検索したい資料のカテゴリを選択してください:", category_labels_to_display
    )

    # 選択された日本語ラベルから英語のキーを取得（バックエンドで、categoryをAttributeFilterで絞り込む際に使用。）
    selected_category_key = [
        category_key
        for category_key, category_value in category_dict.items()
        if category_value == selected_category_value
    ][0]

    # 会話履歴を表示
    display_tab_messages(
        tab_key="kendra_search",
        label="過去の検索結果",
        empty_message="まだ検索結果がありません",
    )

    # サイドバーにKendra検索タブの使い方を追加
    st.sidebar.markdown("### Kendra検索の使い方")
    st.sidebar.markdown(AppConfig.HOW_TO_USE_KENDRA_SEARCH)

    # ユーザーの入力
    user_input = st.chat_input("質問を入力してください")

    if user_input:
        input_msg = {"role": "user", "content": [{"text": user_input}]}
        st.session_state.tab_messages["kendra_search"].append(input_msg)
        with st.chat_message("user"):
            st.markdown(user_input)

        try:
            # Kendra検索実行
            with st.spinner("検索中..."):
                signed_urls = kendraSearch(user_input, selected_category_key)

            # 検索結果を表示
            display_search_results(signed_urls)

            # 検索結果をsession stateに格納
            response_content = "以下の関連ドキュメントが見つかりました"
            response_msg = {
                "role": "assistant",
                "content": [{"text": response_content}],
            }
            st.session_state.tab_messages["kendra_search"].append(response_msg)
        except Exception as e:
            st.error(f"エラーが発生しました: {e}")


# マルチモーダルタブ
elif selected_tab == "multi_modal":
    st.header(tab_titles["multi_modal"])

    # 会話履歴の表示
    display_tab_messages(
        tab_key="multi_modal",
        label="過去の会話履歴",
        empty_message="まだ会話履歴がありません",
    )

    # サイドバーにガイドを表示
    st.sidebar.markdown("### マルチモーダルの使い方")
    st.sidebar.markdown(AppConfig.HOW_TO_USE_MULTI_MODAL)

    # マルチモーダルでサポートされるファイル形式
    supported_formats_dict = AppConfig.SUPPORTED_FORMATS

    # ファイルアップローダーの表示
    uploaded_file = st.file_uploader(
        "ファイルをアップロードしてください", type=supported_formats_dict.values()
    )
    # ユーザーの質問の入力
    question = st.chat_input("質問を入力してください")

    # ファイルアップロードの有無をチェック
    if uploaded_file:
        st.markdown(f"アップロードされたファイル名: `{uploaded_file.name}`")

    # 処理条件: ファイルと質問が揃った場合のみ実行
    if uploaded_file and question:
        # ファイルが有効かチェック（名前、サイズなど）
        if not is_valid_filename(uploaded_file.name):
            st.error(
                "ファイル名にはアルファベット、数字、空白（1文字のみ）、ハイフン、括弧のみを使用してください。"
            )
        elif not is_file_size_valid(uploaded_file):
            st.error("アップロードできるファイルサイズは最大4.5MBまでです。")
        else:
            file_type = uploaded_file.type
            file_format = supported_formats_dict.get(file_type)

            if not file_format:
                st.error(
                    f"サポートされていないファイル形式です。以下の形式に対応しています: {', '.join(supported_formats_dict.values())}"
                )
            else:
                # ファイル形式に応じた表示
                if file_format in ["png", "jpeg"]:
                    st.image(
                        uploaded_file,
                        caption="アップロードされた画像",
                        use_column_width=True,
                    )

                # 入力メッセージをセッションに追加
                input_msg = {"role": "user", "content": [{"text": question}]}
                st.session_state.tab_messages["multi_modal"].append(input_msg)

                with st.chat_message("user"):
                    st.markdown(question)

                try:
                    # Bedrockモデルの呼び出し
                    with st.spinner("回答生成中..."):
                        response_content = invokeLLMWithFile(
                            question,
                            uploaded_file,
                            st.session_state.tab_messages["multi_modal"],
                        )
                    response_msg = {
                        "role": "assistant",
                        "content": [{"text": response_content}],
                    }

                    # LLMからのレスポンスをセッションに保存
                    st.session_state.tab_messages["multi_modal"].append(response_msg)

                    # LLMからのレスポンスを表示
                    with st.chat_message("assistant"):
                        st.markdown(response_content)
                except Exception as e:
                    st.error(f"ファイル処理中にエラーが発生しました: {e}")
    elif uploaded_file and not question:
        # ファイルがアップロードされているが質問が入力されていない場合
        # 質問が入力されているがファイルがアップロードされていない場合
        # 入力メッセージをセッションに追加
        input_msg = {"role": "user", "content": [{"text": question}]}
        st.session_state.tab_messages["multi_modal"].append(input_msg)

        with st.chat_message("user"):
            st.markdown(question)

        try:
            # Bedrockモデルの呼び出し
            with st.spinner("回答生成中..."):
                response_content = invokeLLMWithoutFile(
                    st.session_state.tab_messages["multi_modal"]
                )
            response_msg = {
                "role": "assistant",
                "content": [{"text": response_content}],
            }

            # LLMからのレスポンスをセッションに保存
            st.session_state.tab_messages["multi_modal"].append(response_msg)

            # LLMからのレスポンスを表示
            with st.chat_message("assistant"):
                st.markdown(response_content)
        except Exception as e:
            st.error(f"エラーが発生しました: {e}")
    elif question and not uploaded_file:
        # 質問が入力されているがファイルがアップロードされていない場合
        st.info("ファイルをアップロードしてください。")
    else:
        # 両方が未入力の場合
        st.info("ファイルをアップロードし、質問を入力してください。")
