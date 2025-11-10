# figma2dsl

FigmaのデザインファイルをDSL形式に変換するツール。

JetpackCompose / SwiftUI への変換を前提とした、軽量な中間DSLを生成します。

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

## DSL 出力仕様

### ノードタイプ

- **TEXT**: テキストノード
  - `text`: 表示文字列
  - `style`: テキストスタイル（fontSize, fontWeight, color, textAlign）

- **FRAME**: コンテナノード（FRAME, RECTANGLE, ELLIPSE, GROUP など）
  - `layout`: AutoLayout 情報（direction, spacing, padding, width/height モード）
  - `style`: ビジュアルスタイル（backgroundColor, cornerRadius）
  - `children`: 子ノード配列

- **INSTANCE**: コンポーネントインスタンス
  - `componentId`: コンポーネントの一意ID（Android/iOS 側で対応実装が必要）
  - `componentName`: コンポーネント名（例: "Za/Button/Primary"）
  - `props`: バリアントプロパティ（variant, size など）

### スタイル情報

DSL は必要最小限のスタイル情報のみを出力します：

**TEXT ノード:**
- `fontSize`: フォントサイズ（整数）
- `fontWeight`: フォントウェイト（400, 700 など）
- `color`: テキスト色（#RRGGBB 形式）
- `textAlign`: テキスト整列（CENTER/RIGHT/JUSTIFIED のみ、LEFT はデフォルトなので省略）

**FRAME ノード:**
- `backgroundColor`: 背景色（#RRGGBB 形式、単色のみ）
- `cornerRadius`: 角丸（整数、0 は省略）

**共通:**
- `opacity`: 不透明度（0.5 以下の場合のみ出力）

### 設計思想

- **コンポーネント = ブラックボックス**: INSTANCE は `componentId` + `props` で識別し、内部構造は Android/iOS 側で実装
- **レイアウト優先**: Auto Layout 情報を中心に、絶対座標は最小限
- **基本スタイルのみ**: 複雑なエフェクト（blur, 多重シャドウ等）は対象外
- **情報の簡潔性**: デフォルト値は省略し、DSL サイズを最小化

## テスト

ユニットテストを実行：

```bash
python3 -m unittest test_figma2dsl.py -v
```

全36テストが実行されます。

## APIキーテスト（figma2dsl未使用）

現在の実装では `X-Figma-Token` ヘッダーを使用してFigma APIにアクセスします。

直接APIを呼び出す場合の例：

```bash
curl -i -H "X-Figma-Token: $FIGMA_TOKEN" \
  "https://api.figma.com/v1/files/<FILE_KEY>"
```
