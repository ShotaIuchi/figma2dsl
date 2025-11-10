pip install requests
export FIGMA_TOKEN=xxxxxx

# ファイル全体 → ページ直下のFrame群をざっくりDSL化
python3 figma2dsl.py --file-key <FILE_KEY> --pretty > dsl.json

# 特定Frameだけ（ノードIDはFigmaで Copy as → Copy link から取得可）
python3 figma2dsl.py --file-key <FILE_KEY> --node-id <NODE_ID> --pretty > frame.json

# 複数Frame
python3 figma2dsl.py --file-key <FILE_KEY> --node-id ID_A;ID_B --pretty > frames.json

# 現在の実装では X-Figma-Token を使用 ⭐️
curl -i -H "X-Figma-Token: $FIGMA_TOKEN" \
  "https://api.figma.com/v1/files/<FILE_KEY>"
