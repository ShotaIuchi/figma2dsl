# figma2dsl

FigmaのデザインファイルをDSL形式に変換するツール。

## インストール

必要なパッケージをインストール：

```bash
pip install requests
```

## セットアップ

FigmaのPersonal Access Tokenを環境変数に設定：

```bash
export FIGMA_TOKEN=xxxxxx
```

トークンは[Figmaの設定ページ](https://www.figma.com/settings)から取得できます。

## 使い方

### ファイル全体を変換

ページ直下のFrame群をDSL化：

```bash
python3 figma2dsl.py --file-key <FILE_KEY> --pretty > dsl.json
```

### 特定のFrameだけ変換

ノードIDを指定して特定のFrameを変換（ノードIDはFigmaで `Copy as → Copy link` から取得可）：

```bash
python3 figma2dsl.py --file-key <FILE_KEY> --node-id <NODE_ID> --pretty > frame.json
```

### 複数のFrameを変換

セミコロン区切りで複数のノードIDを指定：

```bash
python3 figma2dsl.py --file-key <FILE_KEY> --node-id ID_A;ID_B --pretty > frames.json
```

## テスト

ユニットテストを実行：

```bash
python3 -m unittest test_figma2dsl.py -v
```

全18テストが実行されます。

## APIキーテスト（figma2dsl未使用）

現在の実装では `X-Figma-Token` ヘッダーを使用してFigma APIにアクセスします。

直接APIを呼び出す場合の例：

```bash
curl -i -H "X-Figma-Token: $FIGMA_TOKEN" \
  "https://api.figma.com/v1/files/<FILE_KEY>"
```
