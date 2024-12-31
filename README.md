# streamlit-rag-app
本リポジトリは、RAGやKendra検索を簡単に試すことができるサンプルアプリです。

## Setup
本リポジトリではPythonパッケージツールである`rye`を使用しています。[rye 公式ページ](https://rye.astral.sh/guide/installation/)を参照し、ryeの初期導入を行う必要があります。
```bash
curl -sSf https://rye.astral.sh/get | bash
```
上記コマンドでインストールができます。

### 使用方法（ローカル）
```bash
source .venv/bin/activate
```
上記コマンドで仮想環境に入ることができます。

```bash
rye sync
```
`pyproject.toml`があるディレクトリまで移動し、`rye sync` を実行することで、プロジェクトに必要なライブラリを一括でインストールすることができます。（事前に仮想環境に入った状態で行います。）


#### アプリの起動
```bash
streamlit run app.py
```
を実行すると、`localhost:8501`でブラウザが立ち上がります。

<img width="1462" alt="スクリーンショット 2024-12-31 22 54 00" src="https://github.com/user-attachments/assets/6e550934-f4dc-4696-ac59-9210c1d00aa7" />

#### 注意点
- Kendraのindex及びそれに必要なデータソースに必要なS3バケットは各自作成する必要があります。