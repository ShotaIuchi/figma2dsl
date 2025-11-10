#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Figma REST API から DOM を取得して、独自 DSL(JSON) に変換する最小CLI。

Usage:
  export FIGMA_TOKEN=xxxxx            # or --token
  python3 figma_to_dsl.py --file-key <FILE_KEY>                 > out.json
  python3 figma_to_dsl.py --file-key <FILE_KEY> --node-id <ID>  > out.json
  # 複数Frame抽出
  python3 figma_to_dsl.py --file-key <FILE_KEY> --node-id A;B;C > out.json

オプション:
  --file-key: Figmaファイルのキー（URLの .../file/<FILE_KEY>/...）
  --node-id : 変換起点のノードID（;区切りで複数）。未指定なら全ページ先頭Frameを列挙
  --token   : Figma Personal Access Token（未指定は FIGMA_TOKEN 環境変数）
  --pretty  : 整形出力
"""

import os, sys, json, argparse, requests
from typing import Any, Dict, List, Optional

API_BASE = "https://api.figma.com/v1"

def _auth_headers(token:str)->Dict[str,str]:
    # Figma API の認証には X-Figma-Token ヘッダーを使用
    return {"X-Figma-Token": token}

def fetch_file(file_key:str, token:str)->Dict[str,Any]:
    r = requests.get(f"{API_BASE}/files/{file_key}", headers=_auth_headers(token))
    r.raise_for_status()
    return r.json()

def fetch_nodes(file_key:str, node_ids:List[str], token:str)->Dict[str,Any]:
    ids = ",".join(node_ids)
    r = requests.get(f"{API_BASE}/files/{file_key}/nodes", params={"ids": ids}, headers=_auth_headers(token))
    r.raise_for_status()
    return r.json()

#-------------------------
# Figma → DSL マッピング
#-------------------------

def px_to_int(v: Optional[float]) -> Optional[int]:
    if v is None: return None
    try:
        return int(round(float(v)))
    except Exception:
        return None

def map_layout_from_autolayout(node:Dict[str,Any]) -> Dict[str,Any]:
    """
    Auto Layout 情報を DSL の layout に写す。
    - direction  : VERTICAL/HORIZONTAL
    - spacing    : itemSpacing
    - padding    : [L,T,R,B]
    - width/height.mode : FILL | FIXED | HUG
      簡易規則:
       * layoutMode != NONE のとき:
           primaryAxisSizingMode/counterAxisSizingMode が AUTO → HUG、FIXED → FIXED
       * layoutGrow == 1 の子は FILL
       * それ以外は HUG（固定サイズがあるなら FIXED）
    """
    layout: Dict[str,Any] = {}
    mode = node.get("layoutMode")  # "HORIZONTAL" | "VERTICAL" | "NONE"
    if mode and mode != "NONE":
        layout["direction"] = "HORIZONTAL" if mode == "HORIZONTAL" else "VERTICAL"
        # spacing
        spacing = px_to_int(node.get("itemSpacing"))
        if spacing: layout["spacing"] = spacing
        # padding
        padL = px_to_int(node.get("paddingLeft"))
        padT = px_to_int(node.get("paddingTop"))
        padR = px_to_int(node.get("paddingRight"))
        padB = px_to_int(node.get("paddingBottom"))
        if any(x is not None for x in [padL,padT,padR,padB]):
            layout["padding"] = [padL or 0, padT or 0, padR or 0, padB or 0]

        # container 自身の size モード推定
        prim = node.get("primaryAxisSizingMode")     # "FIXED" | "AUTO"
        cnt  = node.get("counterAxisSizingMode")     # "FIXED" | "AUTO"
        # primary/counter → width/height は layoutMode による
        def mkmode(sizing:str, fixed_val:Optional[int]):
            if sizing == "AUTO":  # HUG
                return {"mode": "HUG"}
            if sizing == "FIXED":
                return {"mode": "FIXED", "value": fixed_val} if fixed_val else {"mode": "FIXED"}
            return {"mode": "HUG"}

        abs_box = node.get("absoluteBoundingBox") or {}
        w_fixed = px_to_int(abs_box.get("width"))
        h_fixed = px_to_int(abs_box.get("height"))
        if mode == "HORIZONTAL":
            layout["width"]  = mkmode("FIXED",  w_fixed) # 横方向は通常親次第だが、素朴にFIXED寄りに
            layout["height"] = mkmode(cnt or "AUTO", h_fixed)
        else:  # VERTICAL
            layout["width"]  = mkmode(cnt or "AUTO", w_fixed)
            layout["height"] = mkmode("FIXED", h_fixed)
    else:
        # AutoLayout無し → サイズだけ推定
        abs_box = node.get("absoluteBoundingBox") or {}
        w_fixed = px_to_int(abs_box.get("width"))
        h_fixed = px_to_int(abs_box.get("height"))
        if w_fixed or h_fixed:
            layout["width"]  = {"mode":"FIXED","value":w_fixed} if w_fixed else {"mode":"HUG"}
            layout["height"] = {"mode":"FIXED","value":h_fixed} if h_fixed else {"mode":"HUG"}

    return layout

def map_instance_props(node:Dict[str,Any]) -> Dict[str,Any]:
    """
    Instance（コンポーネント配置）の props を抽出。
    - variantProperties: { "Type":"Primary", "Size":"Md" } → props.variant/size へ落とす例
    - 文字列/数値/真偽はそのまま
    """
    props: Dict[str,Any] = {}

    # テキストオーバーライドなどは 'componentProperties' に来る場合あり
    # ここでは variantProperties を優先して分かりやすく落とす
    vprops = node.get("variantProperties") or {}
    # よくあるキー名を標準化
    if "Type" in vprops:
        props["variant"] = vprops["Type"]
    if "Variant" in vprops and "variant" not in props:
        props["variant"] = vprops["Variant"]
    if "Size" in vprops:
        props["size"] = vprops["Size"]
    # そのまま全部入れたい場合は下を有効化
    # for k, v in vprops.items():
    #     props.setdefault(k.lower(), v)

    return props

def extract_component_info(node:Dict[str,Any]) -> Dict[str,Any]:
    """
    INSTANCE ノードからコンポーネント識別情報を抽出。
    - componentId: コンポーネントの一意ID
    - componentName: コンポーネントの階層名（Za/Button など）
    """
    info: Dict[str,Any] = {}

    # componentId の取得
    comp_id = node.get("componentId")
    if comp_id:
        info["componentId"] = comp_id

    # componentName の取得（name から推定、または別フィールドがあれば使用）
    # Figma では INSTANCE の name にコンポーネント名が入ることが多い
    name = node.get("name")
    if name:
        info["componentName"] = name

    return info

def extract_color(fills: Optional[List[Dict[str,Any]]]) -> Optional[str]:
    """
    fills 配列から単色を抽出して #RRGGBB 形式で返す。
    複数色やグラデーション等は対応しない。
    """
    if not fills or len(fills) == 0:
        return None

    # 最初の visible な fill を使用
    for fill in fills:
        if fill.get("visible") == False:
            continue
        if fill.get("type") == "SOLID":
            color = fill.get("color", {})
            r = int(color.get("r", 0) * 255)
            g = int(color.get("g", 0) * 255)
            b = int(color.get("b", 0) * 255)
            return f"#{r:02X}{g:02X}{b:02X}"

    return None

def extract_text_style(node:Dict[str,Any]) -> Dict[str,Any]:
    """
    TEXT ノードから基本スタイル情報を抽出。
    - fontSize: フォントサイズ（整数）
    - fontWeight: フォントウェイト（数値、例: 400, 700）
    - color: テキスト色（#RRGGBB 形式）
    - textAlign: テキスト整列（LEFT/CENTER/RIGHT/JUSTIFIED）
    """
    style: Dict[str,Any] = {}

    # フォントサイズ
    font_size = node.get("style", {}).get("fontSize")
    if font_size:
        style["fontSize"] = px_to_int(font_size)

    # フォントウェイト
    font_weight = node.get("style", {}).get("fontWeight")
    if font_weight:
        style["fontWeight"] = int(font_weight)

    # テキスト色
    fills = node.get("fills")
    color = extract_color(fills)
    if color:
        style["color"] = color

    # テキスト整列
    text_align = node.get("style", {}).get("textAlignHorizontal")
    if text_align and text_align != "LEFT":  # LEFT はデフォルトなので省略
        style["textAlign"] = text_align

    return style

def extract_frame_style(node:Dict[str,Any]) -> Dict[str,Any]:
    """
    FRAME ノードから基本スタイル情報を抽出。
    - backgroundColor: 背景色（#RRGGBB 形式）
    - cornerRadius: 角丸（整数、0 なら省略）
    """
    style: Dict[str,Any] = {}

    # 背景色
    fills = node.get("fills")
    bg_color = extract_color(fills)
    if bg_color:
        style["backgroundColor"] = bg_color

    # 角丸
    corner_radius = node.get("cornerRadius")
    if corner_radius:
        radius = px_to_int(corner_radius)
        if radius and radius > 0:
            style["cornerRadius"] = radius

    return style

def to_dsl(node:Dict[str,Any]) -> Optional[Dict[str,Any]]:
    ntype = node.get("type")
    name  = node.get("name") or ntype

    if ntype in ("TEXT",):
        # TEXT ノード
        d = {"type":"TEXT", "name": name, "text": node.get("characters", "")}

        # テキストスタイルを追加
        style = extract_text_style(node)
        if style:
            d["style"] = style

        # opacity を追加（0.5以下の場合のみ）
        opacity = node.get("opacity")
        if opacity is not None and opacity <= 0.5:
            if "style" not in d:
                d["style"] = {}
            d["style"]["opacity"] = round(opacity, 2)

        return d

    if ntype in ("FRAME","COMPONENT","COMPONENT_SET","GROUP","INSTANCE","SECTION","ELLIPSE","RECTANGLE","VECTOR","BOOLEAN_OPERATION","STAR","POLYGON","LINE","SLICE"):
        # まず基本形
        d: Dict[str,Any] = {"type":"FRAME", "name": name}
        # INSTANCE は type を INSTANCE に
        if ntype == "INSTANCE":
            d["type"] = "INSTANCE"
            d["name"] = name  # 例: "Za/Button/Primary"

            # コンポーネント識別情報を追加
            comp_info = extract_component_info(node)
            if comp_info.get("componentId"):
                d["componentId"] = comp_info["componentId"]
            if comp_info.get("componentName"):
                d["componentName"] = comp_info["componentName"]

            # バリアント等の props を追加
            props = map_instance_props(node)
            if props: d["props"] = props
        elif ntype in ("ELLIPSE","RECTANGLE"):
            # 四角/円は簡略化して FRAME として扱い、背景は実装側でスタイル
            d["type"] = "FRAME"
        elif ntype == "GROUP":
            # GROUP は構造上のまとまりとして FRAME に寄せる
            d["type"] = "FRAME"
        else:
            d["type"] = "FRAME"

        # AutoLayout → layout
        layout = map_layout_from_autolayout(node)
        if layout: d["layout"] = layout

        # INSTANCE 以外の FRAME 系ノードにはスタイル情報を追加
        if ntype != "INSTANCE":
            frame_style = extract_frame_style(node)
            if frame_style:
                # style が既にあれば上書き、なければ新規作成
                if "style" not in d:
                    d["style"] = {}
                d["style"].update(frame_style)

        # 子ノード
        children = []
        for ch in node.get("children") or []:
            mapped = to_dsl(ch)
            if mapped:
                children.append(mapped)
        if children:
            d["children"] = children

        # opacity を追加（0.5以下の場合のみ）
        opacity = node.get("opacity")
        if opacity is not None and opacity <= 0.5:
            if "style" not in d:
                d["style"] = {}
            d["style"]["opacity"] = round(opacity, 2)

        return d

    # 未対応タイプはコメント化
    return {"type":"FRAME","name":f"UNSUPPORTED:{name}","children":[{"type":"TEXT","name":"note","text":f"(unsupported type: {ntype})"}]}

def pick_top_frames(file_json:Dict[str,Any])->List[Dict[str,Any]]:
    """ページ直下のFrameだけ拾う（ざっくり）。"""
    res = []
    doc = file_json.get("document", {})
    for page in doc.get("children", []) or []:   # type == "CANVAS"
        for n in page.get("children", []) or []:
            if n.get("type") in ("FRAME","COMPONENT","INSTANCE","GROUP"):
                res.append(n)
    return res

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--file-key", required=True)
    p.add_argument("--node-id",  default="")
    p.add_argument("--token",    default=os.getenv("FIGMA_TOKEN",""))
    p.add_argument("--pretty",   action="store_true")
    args = p.parse_args()

    if not args.token:
        print("Error: Figma token is required (set --token or FIGMA_TOKEN).", file=sys.stderr)
        sys.exit(2)

    # ノード指定があれば /nodes、なければ /files からトップFrame群を拾う
    if args.node_id.strip():
        ids = [s for s in args.node_id.replace(",", ";").split(";") if s]
        data = fetch_nodes(args.file_key, ids, args.token)
        dsl_roots: List[Dict[str,Any]] = []
        nodes = (data.get("nodes") or {})
        for node_id, payload in nodes.items():
            doc = payload.get("document")
            if not doc: continue
            mapped = to_dsl(doc)
            if mapped:
                dsl_roots.append(mapped)
        out = dsl_roots[0] if len(dsl_roots)==1 else {"type":"DOCUMENT","children":dsl_roots}
    else:
        file_json = fetch_file(args.file_key, args.token)
        frames = pick_top_frames(file_json)
        dsl_roots: List[Dict[str,Any]] = []
        for fr in frames:
            mapped = to_dsl(fr)
            if mapped: dsl_roots.append(mapped)
        out = {"type":"DOCUMENT","children":dsl_roots}

    print(json.dumps(out, ensure_ascii=False, indent=2 if args.pretty else None))

if __name__ == "__main__":
    main()
