import os
import urllib

import boto3
from app_config import AppConfig
from botocore.client import Config
from dotenv import load_dotenv

"""
Step2 Kendra RAG検索/マルチモーダル
参照ソース:https://github.com/ryanadoty/Amazon-Bedrock-RAG-Kendra-POC/blob/main/kendra_bedrock_query.py
        https://github.com/aws-samples/genai-quickstart-pocs/tree/main/genai-quickstart-pocs-python/amazon-bedrock-claude3-multi-modal-poc


"""

# 環境変数の読み込み
load_dotenv()


# boto3セッションの定義
boto3_session = boto3.session.Session(profile_name=os.getenv("profile_name"))


# リトライ設定の作成（Amazon Bedrock ConverseAPI利用時のThrottlingエラー回避策）
retries_config = Config(AppConfig.RETRY_CONFIGS)


# Bedrock clientの初期化
bedrock = boto3_session.client(
    "bedrock-runtime",
    region_name=AppConfig.REGION_NAME_DICT["oregon"],
    config=retries_config,
)
# デバッグ用
# print(bedrock)


# RAG検索を行う関数
def ragSearch(
    question, history, selected_model_id, selected_temperature, selected_category_key
):
    """
    Kendraの query APIを使用して、その回答をLLMに渡す関数
    :param question: ユーザーの質問
    :param history: ユーザーの会話履歴
    :param selected_model_id ユーザーが画面で選択したClaudeのモデル
    :param selected_temperature ユーザーが画面で選択した「振る舞い」（temperature）の値
    :param selected_category_key 画面上で選択された検索対象のドキュメントのkey（KendraのAttributeFilterで絞り込みに使用される値)
    :return: 過去の会話履歴+ユーザーの質問を踏まえて、LLMによって生成された回答
    """

    # kendra clientの初期化
    kendra = boto3_session.client(
        "kendra", region_name=AppConfig.REGION_NAME_DICT["oregon"]
    )

    # ユーザーが選択したカテゴリの値に応じて、検索条件を動的に構築
    # デフォルトは検索条件の絞り込みなし（_language_codeの絞り込みのみ）
    attribute_filter = {
        "AndAllFilters": [
            {"EqualsTo": {"Key": "_language_code", "Value": {"StringValue": "ja"}}}
        ]
    }
    # 絞込み条件の追加
    additional_attribute_filter = {
        "OrAllFilters": [
            {
                "EqualsTo": {
                    "Key": "_category",
                    "Value": {"StringValue": selected_category_key},
                }
            }
        ]
    }
    # 「全て」以外が選択された時は検索条件の絞り込みを行う
    if selected_category_key != "all":
        attribute_filter["AndAllFilters"].append(additional_attribute_filter)

    # queryAPIを使ってKendraを呼び出す
    kendra_response = kendra.query(
        IndexId=os.getenv("kendra_index"),  # Put INDEX in .env file
        QueryText=question,
        PageNumber=1,
        PageSize=30,
        AttributeFilter=attribute_filter,
    )

    # デバッグ用:print(kendra_response)

    # ドキュメントのメタデータを取得し、署名付きURLを生成
    signed_urls = generateSignedUrls(kendra_response)
    # デバッグ用
    # print(signed_urls)

    # 参照ドキュメントを生成 回答の参照ドキュメントが画面に出力されてしまうためマークダウンで表示できるよう整形
    document_references = "\n".join(
        [f"- [{doc['document_name']}]({doc['signed_url']})" for doc in signed_urls]
    )

    # Claudeモデルに渡すシステムプロンプトを定義
    system_prompt = AppConfig.SYSTEM_PROMPT

    # 会話の順番が`user`と`assistant`となるように制御
    for i in range(len(history) - 1):
        if history[i]["role"] == history[i + 1]["role"]:
            raise ValueError(
                "会話履歴のロールはuserとassistantで交互である必要があります。"
            )
    # デバッグ用
    # print(f"messages:{messages}")

    # 現在の質問と検索結果を会話履歴に追加
    context_message = {
        "role": "assistant",
        "content": [{"text": f"Kendra検索結果:\n\n{document_references}"}],
    }
    history.append(context_message)

    question_message = {"role": "user", "content": [{"text": question}]}
    history.append(question_message)

    # デバッグ用（会話履歴の確認
    print("-----------------------")
    print(f"history:{history}")
    print("-----------------------")

    # # デバッグ用
    # # print(bedrock)

    # ConverseAPIに会話履歴を渡した上で質問を行う
    response = bedrock.converse(
        modelId=selected_model_id,
        messages=history,
        system=system_prompt,
        inferenceConfig={"temperature": selected_temperature},
    )
    # デバッグ用
    # print(f"Converse API response: {response}")
    # レスポンスの中身チェック
    if (
        "content" not in response["output"]["message"]
        or not response["output"]["message"]["content"]
    ):
        raise ValueError("Bedrock response content is empty.")

    # 最終的に画面に表示する回答
    answer = response["output"]["message"]["content"][0]["text"]
    return answer, signed_urls


# Kendra検索時に使用する関数
def kendraSearch(kendra_query, selected_category_key):
    """
    Kendra検索用の関数
    queryAPIを使った検索のみを行い、検索結果と、メタデータから署名付きURLを生成し、返却する
    :param question: ユーザーが画面で入力した質問
    :param selected_category_key 画面上で選択された検索対象のドキュメントのkey（KendraのAttributeFilterで絞り込みに使用される値)
    :return: 署名つきURL
    """

    # Kendra clientの初期化
    kendra = boto3_session.client(
        "kendra", region_name=AppConfig.REGION_NAME_DICT["oregon"]
    )

    # ユーザーが選択したカテゴリの値に応じて、検索条件を動的に構築
    # デフォルトは検索条件の絞り込みなし（_language_codeの絞り込みのみ）
    attribute_filter = {
        "AndAllFilters": [
            {"EqualsTo": {"Key": "_language_code", "Value": {"StringValue": "ja"}}}
        ]
    }
    # 絞込み条件の追加
    additional_attribute_filter = {
        "OrAllFilters": [
            {
                "EqualsTo": {
                    "Key": "_category",
                    "Value": {"StringValue": selected_category_key},
                }
            }
        ]
    }
    # 「全て」以外が選択された時は検索条件の絞り込みを行う
    if selected_category_key != "all":
        attribute_filter["AndAllFilters"].append(additional_attribute_filter)
    # Kendraの queryAPIの呼び出し
    kendra_response = kendra.query(
        IndexId=os.getenv("kendra_index"),  # Put INDEX in .env file
        QueryText=kendra_query,
        PageNumber=1,
        PageSize=30,
        AttributeFilter=attribute_filter,
    )

    # デバッグ用
    # print(kendra_response)
    # 署名付きURLを取得
    signed_urls = generateSignedUrls(kendra_response)
    # デバッグ用
    # print(f"署名つきURL:{signed_urls}")

    return signed_urls


# 署名付きURLを返却する関数（Kendra検索, RAG検索共通
def generateSignedUrls(kendra_response):
    """
    Kendraの検索結果から署名付きURLを生成する
    :param kendra_response: Kendraの検索結果
    :return: Kendra検索結果のドキュメントの署名付きURLのリスト
    """
    # プロファイルを元にセッションを確立
    boto3_session = boto3.session.Session(profile_name=os.getenv("profile_name"))
    s3_client = boto3_session.client(
        "s3",
        region_name=AppConfig.REGION_NAME_DICT["oregon"],
        config=Config(signature_version="s3v4"),
        verify=False,
    )
    signed_urls = []

    for result in kendra_response.get("ResultItems", []):
        # ドキュメントのパスの存在確認
        if (
            "DocumentURI" in result
            and "s3.us-west-2.amazonaws.com" in result["DocumentURI"]
        ):
            # 検索結果のS3ドキュメントのURIを取得
            s3_url = result["DocumentURI"]
            try:
                # Debug: print the DocumentURI to verify its structure
                # print(f"DocumentURI: {s3_url}")
                # Parse S3 bucket and key from the DocumentURI

                # プロトコル部分を取り除く
                s3_path = s3_url.replace("https://", "")

                # パスをバケット名とオブジェクトキーに分割
                parts = s3_path.split("/", 1)
                if len(parts) == 2:
                    bucket_name = os.getenv("bucket_name")
                    # オブジェクトキーを取得（取得時はすでにエンコードされている）
                    object_key_encoded = parts[1]

                    # 取得したオブジェクトキーをデコード（オブジェクトキーが日本語だと二重でエンコードされてしまい、エラーとなってしまうため）
                    # 参照: https://github.com/aws-samples/generative-ai-use-cases-jp/issues/189
                    object_key = urllib.parse.unquote(object_key_encoded)
                    # print(f"Decoded Object Key: {object_key}")
                    if object_key.startswith("transcription/") and object_key.endswith(
                        ".txt"
                    ):
                        txt_file_name = object_key.split("/")[-1]  # XXXX.txt
                        pdf_object_key = f"hogehoge/{
                           txt_file_name.replace('.txt', '.pdf')}"

                        # .txtファイルの名前と同名の.pdfファイルが存在するかを確認し、存在する場合はそちらを署名付きURLに変換して返却
                        try:
                            s3_client.head_object(
                                Bucket=bucket_name, Key=pdf_object_key
                            )
                            print(f"PDF file exists: {pdf_object_key}")

                            # 署名付きURLを生成
                            signed_url = s3_client.generate_presigned_url(
                                "get_object",
                                Params={"Bucket": bucket_name, "Key": pdf_object_key},
                                ExpiresIn=3600,
                            )
                            signed_urls.append(
                                {
                                    "document_name": txt_file_name.replace(
                                        ".txt", ".pdf"
                                    ),
                                    "signed_url": signed_url,
                                }
                            )
                        except s3_client.exceptions.ClientError as e:
                            if e.response["Error"]["Code"] == "404":
                                print(f"PDF file not found: {pdf_object_key}")
                            else:
                                raise
                    else:
                        # 同名のファイルが存在しない場合は検索結果のファイルをそのまま署名付きURLに変換
                        signed_url = s3_client.generate_presigned_url(
                            "get_object",
                            Params={"Bucket": bucket_name, "Key": object_key},
                            ExpiresIn=3600,  # URL valid for 1 hour
                        )
                        signed_urls.append(
                            {
                                "document_name": result.get(
                                    "DocumentTitle", "Unknown Document"
                                ).get("Text"),
                                "signed_url": signed_url,
                            }
                        )
                    print(f"signed_urls: {signed_urls}")
                else:
                    print(f"Unexpected S3 path format: {s3_url}")
            except Exception as e:
                print(f"Error generating signed URL: {e}")

    return signed_urls


def invokeLLMWithFile(question, uploaded_file, messages):
    """
    マルチモーダルでのBedrock呼び出しを行う
    ファイルがアップロードされなかった場合、通常のチャットとして動作する
    :param question: ユーザーの質問
    :param uploaded_file: アップロードされたファイル
    :param messages:  過去の会話履歴
    :return answer: LLMからの回答
    """
    # モデルIDと推論パラメータのセット
    model_id = AppConfig.MODEL_ID_DICT["claude_3_haiku"]
    inference_config = AppConfig.INFERENCE_CONFIG_DICT

    # マルチモーダルでサポートされるファイル形式
    supported_formats_dict = AppConfig.SUPPORTED_FORMATS

    if uploaded_file:
        # ファイル形式を判別
        file_format = supported_formats_dict.get(uploaded_file.type)
        if not file_format:
            raise ValueError(
                f"サポートされていないファイル形式です。以下の形式に対応しています: {
                   ', '.join(supported_formats_dict.values())}"
            )

        # ファイルの内容を読み込む
        file_content = uploaded_file.getvalue()

        # 画像のバリデーションと処理
        if file_format in ["png", "jpeg"]:
            file_message = {
                "image": {"format": file_format, "source": {"bytes": file_content}}
            }
            default_question = (
                f"アップロードされた画像（{file_format}）の内容を要約してください。"
            )
        elif file_format == "pdf":
            # PDFの処理
            # TODO nameの部分に関して、ファイル名の名前を使用するとなぜかconverseAPIのエラーになってしまうため決めうちで指定
            file_message = {
                "document": {
                    "format": "pdf",
                    "name": "pdf",
                    "source": {"bytes": file_content},
                }
            }
            default_question = f"アップロードされたPDF（{uploaded_file.name}）の内容を要約してください。"
        else:
            raise ValueError("サポートされていないファイル形式です。")

        # `question` が空の場合、デフォルトの質問を使用
        question = question if question.strip() else default_question

        # メッセージの構築
        user_message = {
            "role": "user",
            "content": [
                {"text": f"Uploaded {file_format} content:"},
                file_message,
                {"text": question},
            ],
        }
    else:
        # ファイルがない場合の処理
        user_message = {
            "role": "user",
            "content": [
                {"text": question if question.strip() else "質問が入力されていません。"}
            ],
        }

    # メッセージを追加
    if messages and messages[-1]["role"] != "assistant":
        messages.append({"role": "assistant", "content": [{"text": "準備中..."}]})
    messages.append(user_message)

    # Bedrock API呼び出し
    try:
        response = bedrock.converse(
            modelId=model_id, messages=messages, inferenceConfig=inference_config
        )
        answer = response["output"]["message"]["content"][0]["text"]
    except Exception as e:
        answer = f"エラーが発生しました: {e}"

    return answer


def invokeLLMWithoutFile(history):
    """
    通常のLLMとのチャットを行う関数（会話履歴を考慮した回答をさせる）
    :param history: ユーザーの会話履歴
    :return answer: 過去の会話履歴を踏まえて、LLMによって生成された回答
    """

    # モデルIDと推論パラメータのセット
    model_id = AppConfig.MODEL_ID_DICT["claude_3_5_sonnet"]
    inference_config = AppConfig.INFERENCE_CONFIG_DICT

    # ConverseAPIに会話履歴を渡した上で質問を行う
    response = bedrock.converse(
        modelId=model_id, messages=history, inferenceConfig=inference_config
    )
    # デバッグ用
    # print(f"Converse API response: {response}")
    # レスポンスの中身チェック
    if (
        "content" not in response["output"]["message"]
        or not response["output"]["message"]["content"]
    ):
        raise ValueError("Bedrock response content is empty.")

    # 最終的に画面に表示する回答
    answer = response["output"]["message"]["content"][0]["text"]
    print(answer)
    return answer
