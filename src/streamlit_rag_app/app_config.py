class AppConfig:
    # リージョン名
    REGION_NAME_DICT = {
        "oregon": "us-west-2",
        "verginia": "us-east-1",
        "tokyo": "ap-northeast-1",
    }
    # Amazon BedrockのモデルID（Claude3.5 Sonnet, Claude3 Sonnet, Claude3 Haiku）
    MODEL_ID_DICT = {
        "claude_3_5_sonnet": "anthropic.claude-3-5-sonnet-20240620-v1:0",
        "claude_3_sonnet": "anthropic.claude-3-sonnet-20240229-v1:0",
        "claude_3_haiku": "anthropic.claude-3-haiku-20240307-v1:0",
    }

    # Claudeモデルの、推論時の各種パラメータ（追加したいパラメータを下記に追記していく）
    INFERENCE_CONFIG_DICT = {
        "maxTokens": 4096,
        "temperature": 0.5,
        # topP = 0.999（デフォルト）,
        # stopSequences = ['</output>']
    }
    # アプリ名称
    APP_NAME = "Kendra-Bedrock-RAG検証"
    # 各タブで利用される文言
    WORDS_USED_IN_EACH_TAB_DICT = {
        "rag_search": "RAG検索",
        "kendra_search": "Kendra検索",
        "multi_modal": "マルチモーダル",
    }
    # リトライ設定
    # botocoreのリトライ設定の作成(Throttlingエラー回避策)
    RETRY_CONFIGS = {
        "max_attempts": 10,  # 最大10回のリトライ
        "mode": "adaptive",  # リトライモード
    }

    # システムプロンプト
    SYSTEM_PROMPT = [
        {
            "text": f"""
       【指示】:
       - 以下の「質問」と「検索結果」、過去の会話履歴に基づいて、ユーザーの質問に正確に回答してください。
       - 検索結果に回答が含まれていない場合は、「該当する情報は見つかりませんでした」と明示してください。
       - ユーザーから表形式での出力が要求された場合、Markdown形式で表を作成してください。
       - 表の列名を明確に指定し、回答に関連する情報を整然と整理してください。
       """
        }
    ]

    # 生成AIの振る舞いの値
    TEMPERATURE_OPTIONS = {"厳密に": 0.2, "バランスよく": 0.5, "創造的に": 0.8}
    # カテゴリの絞り込みに使うためのカテゴリの辞書（検索条件の絞り込みの際使用する）
    # NOTE 使用するドキュメントに合わせて設定してください
    CATEGORY_LABELS = {
        "all": "全て",
        "ministry-of-health-labour-and-welfare": "厚生労働省",
        "ministry-of-land-infrastructure-transport-and-tourism": "国土交通省",
    }

    # マルチモーダル問い合わせの場合の、サポートされるファイル形式を定義
    # サポートされるファイル形式
    SUPPORTED_FORMATS = {
        "application/pdf": "pdf",
        "text/csv": "csv",
        "application/msword": "doc",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
        "application/vnd.ms-excel": "xls",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
        "text/html": "html",
        "text/plain": "txt",
        "text/markdown": "md",
        "image/png": "png",
        "image/jpeg": "jpeg",
    }

    # 各種機能の使い方を定義
    # NOTE 半角スペースを2つ入れると、改行が入ります
    # RAG検索
    HOW_TO_USE_RAG_SEARCH = """
   ここでは、Amazon Bedrockを使用して、文書の検索結果を、生成AIによる回答の形式で得ることができます。


   1. :red[**検索したい資料のカテゴリを選択**]  
   検索対象のドキュメントの種類をラジオボタンで選択してください。デフォルトでは、「全て」が選択されています。 
   2. :red[**生成AIが生成する回答の振る舞いを選択**]  
   生成AIが生成する回答の振る舞いを選択してください。デフォルトでは、"厳密に"（より事実に即した回答をさせる）が選択されています。 
   3. :red[**質問文の入力**]  
   画面下部の入力欄に質問文を入力してください。 


   ※期待する結果が返ってこない場合は、以下の方法をお試しください。  
   1. :blue[**質問文や検索対象のカテゴリの設定を見直す**]  
   より具体的な質問や適切なカテゴリ設定を行うと、検索結果が改善される可能性があります。 
   2. :blue[**質問を深掘りする**]  
   より詳細な情報を求める質問を入力することで、期待する回答を得られる可能性があります。
   """

    # Kendra検索
    HOW_TO_USE_KENDRA_SEARCH = """
   ここでは、Amazon Kendraを使用して、文書の検索を行うことができます。


   1. :red[**検索したい資料のカテゴリを選択**]   
   検索対象のドキュメントの種類をラジオボタンで選択してください。デフォルトでは、「全て」が選択されています。 
   2. :red[**検索キーワードの入力**]   
   画面下部の入力欄に検索キーワードを入力してください。   


   ※検索結果がない場合は、検索キーワードや検索対象のカテゴリの設定を見直して再度検索をお試しください。
   """

    # マルチモーダル
    HOW_TO_USE_MULTI_MODAL = """
   ここでは、Amazon Bedrockを用いて、テキストと、画像やPDFファイルなどのアップロードされたファイルを組み合わせて生成AIに質問を行うことができます。


   1. :red[**ファイルアップロード**]  
   画像や（PNG、JPEG）、PDFファイルなどをアップロードします。
   2. :red[**質問の入力**]  
   画面下部の入力欄に質問を入力します。  
   例）「この画像から読み取ることのできる情報を全てテキストで書き起こしてください」  
   3. :red[**通常のチャット**]   
   ファイルをアップロードせずにテキストのみで生成AIに質問を行うことも可能です。


   """
