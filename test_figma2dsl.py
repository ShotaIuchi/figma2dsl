#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
figma2dsl.py のユニットテスト
"""

import unittest
from unittest.mock import patch, MagicMock
import json
from figma2dsl import (
    _auth_headers,
    px_to_int,
    map_layout_from_autolayout,
    map_instance_props,
    extract_component_info,
    extract_color,
    extract_text_style,
    extract_frame_style,
    to_dsl,
    pick_top_frames,
    fetch_file,
    fetch_nodes
)


class TestAuthHeaders(unittest.TestCase):
    """
    _auth_headers 関数のテスト
    """
    def test_auth_headers(self):
        # トークンからヘッダーを生成
        token = "test_token_12345"
        headers = _auth_headers(token)
        self.assertEqual(headers, {"X-Figma-Token": "test_token_12345"})


class TestPxToInt(unittest.TestCase):
    """
    px_to_int 関数のテスト
    """
    def test_none_input(self):
        # None入力はNoneを返す
        self.assertIsNone(px_to_int(None))

    def test_float_input(self):
        # float入力は四捨五入してintに変換
        self.assertEqual(px_to_int(10.4), 10)
        self.assertEqual(px_to_int(10.6), 11)

    def test_int_input(self):
        # int入力はそのまま
        self.assertEqual(px_to_int(42), 42)

    def test_invalid_input(self):
        # 無効な入力はNoneを返す
        self.assertIsNone(px_to_int("invalid"))


class TestMapLayoutFromAutolayout(unittest.TestCase):
    """
    map_layout_from_autolayout 関数のテスト
    """
    def test_horizontal_layout(self):
        # HORIZONTAL レイアウトのテスト
        node = {
            "layoutMode": "HORIZONTAL",
            "itemSpacing": 8,
            "paddingLeft": 16,
            "paddingTop": 12,
            "paddingRight": 16,
            "paddingBottom": 12,
            "primaryAxisSizingMode": "FIXED",
            "counterAxisSizingMode": "AUTO",
            "absoluteBoundingBox": {"width": 320, "height": 48}
        }
        layout = map_layout_from_autolayout(node)
        self.assertEqual(layout["direction"], "HORIZONTAL")
        self.assertEqual(layout["spacing"], 8)
        self.assertEqual(layout["padding"], [16, 12, 16, 12])

    def test_vertical_layout(self):
        # VERTICAL レイアウトのテスト
        node = {
            "layoutMode": "VERTICAL",
            "itemSpacing": 12,
            "absoluteBoundingBox": {"width": 200, "height": 300}
        }
        layout = map_layout_from_autolayout(node)
        self.assertEqual(layout["direction"], "VERTICAL")
        self.assertEqual(layout["spacing"], 12)

    def test_no_autolayout(self):
        # AutoLayoutなしのテスト
        node = {
            "layoutMode": "NONE",
            "absoluteBoundingBox": {"width": 100, "height": 100}
        }
        layout = map_layout_from_autolayout(node)
        self.assertIn("width", layout)
        self.assertIn("height", layout)


class TestMapInstanceProps(unittest.TestCase):
    """
    map_instance_props 関数のテスト
    """
    def test_variant_properties(self):
        # variantPropertiesのマッピングテスト
        node = {
            "variantProperties": {
                "Type": "Primary",
                "Size": "Md"
            }
        }
        props = map_instance_props(node)
        self.assertEqual(props["variant"], "Primary")
        self.assertEqual(props["size"], "Md")

    def test_no_properties(self):
        # プロパティがない場合は空のdictを返す
        node = {}
        props = map_instance_props(node)
        self.assertEqual(props, {})


class TestToDsl(unittest.TestCase):
    """
    to_dsl 関数のテスト
    """
    def test_text_node(self):
        # TEXTノードの変換テスト
        node = {
            "type": "TEXT",
            "name": "Label",
            "characters": "Hello World"
        }
        dsl = to_dsl(node)
        self.assertEqual(dsl["type"], "TEXT")
        self.assertEqual(dsl["name"], "Label")
        self.assertEqual(dsl["text"], "Hello World")

    def test_frame_node(self):
        # FRAMEノードの変換テスト
        node = {
            "type": "FRAME",
            "name": "Container",
            "layoutMode": "VERTICAL",
            "children": []
        }
        dsl = to_dsl(node)
        self.assertEqual(dsl["type"], "FRAME")
        self.assertEqual(dsl["name"], "Container")
        self.assertIn("layout", dsl)

    def test_instance_node(self):
        # INSTANCEノードの変換テスト
        node = {
            "type": "INSTANCE",
            "name": "Button/Primary",
            "variantProperties": {
                "Type": "Primary"
            },
            "children": []
        }
        dsl = to_dsl(node)
        self.assertEqual(dsl["type"], "INSTANCE")
        self.assertEqual(dsl["name"], "Button/Primary")
        self.assertIn("props", dsl)

    def test_nested_children(self):
        # 子要素を持つノードのテスト
        node = {
            "type": "FRAME",
            "name": "Parent",
            "children": [
                {"type": "TEXT", "name": "Child", "characters": "Text"}
            ]
        }
        dsl = to_dsl(node)
        self.assertEqual(len(dsl["children"]), 1)
        self.assertEqual(dsl["children"][0]["type"], "TEXT")


class TestPickTopFrames(unittest.TestCase):
    """
    pick_top_frames 関数のテスト
    """
    def test_pick_frames(self):
        # ページ直下のFrameを抽出するテスト
        file_json = {
            "document": {
                "children": [
                    {
                        "type": "CANVAS",
                        "children": [
                            {"type": "FRAME", "name": "Frame1"},
                            {"type": "COMPONENT", "name": "Component1"},
                            {"type": "TEXT", "name": "ShouldBeIgnored"}
                        ]
                    },
                    {
                        "type": "CANVAS",
                        "children": [
                            {"type": "FRAME", "name": "Frame2"}
                        ]
                    }
                ]
            }
        }
        frames = pick_top_frames(file_json)
        self.assertEqual(len(frames), 3)
        self.assertEqual(frames[0]["name"], "Frame1")
        self.assertEqual(frames[1]["name"], "Component1")
        self.assertEqual(frames[2]["name"], "Frame2")


class TestFetchFile(unittest.TestCase):
    """
    fetch_file 関数のテスト（モックを使用）
    """
    @patch('figma2dsl.requests.get')
    def test_fetch_file_success(self, mock_get):
        # 正常レスポンスのテスト
        mock_response = MagicMock()
        mock_response.json.return_value = {"name": "Test File", "document": {}}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = fetch_file("test_file_key", "test_token")

        self.assertEqual(result["name"], "Test File")
        mock_get.assert_called_once()

    @patch('figma2dsl.requests.get')
    def test_fetch_file_error(self, mock_get):
        # エラーレスポンスのテスト
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = Exception("API Error")
        mock_get.return_value = mock_response

        with self.assertRaises(Exception):
            fetch_file("invalid_key", "invalid_token")


class TestFetchNodes(unittest.TestCase):
    """
    fetch_nodes 関数のテスト（モックを使用）
    """
    @patch('figma2dsl.requests.get')
    def test_fetch_nodes_success(self, mock_get):
        # 正常レスポンスのテスト
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "nodes": {
                "1:2": {"document": {"type": "FRAME", "name": "TestFrame"}}
            }
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = fetch_nodes("test_file_key", ["1:2"], "test_token")

        self.assertIn("nodes", result)
        self.assertIn("1:2", result["nodes"])
        mock_get.assert_called_once()


class TestExtractComponentInfo(unittest.TestCase):
    """
    extract_component_info 関数のテスト
    """
    def test_with_component_id_and_name(self):
        # componentId と name が両方ある場合
        node = {
            "componentId": "123:456",
            "name": "Za/Button/Primary"
        }
        info = extract_component_info(node)
        self.assertEqual(info["componentId"], "123:456")
        self.assertEqual(info["componentName"], "Za/Button/Primary")

    def test_without_component_id(self):
        # componentId がない場合
        node = {
            "name": "Za/Button/Primary"
        }
        info = extract_component_info(node)
        self.assertNotIn("componentId", info)
        self.assertEqual(info["componentName"], "Za/Button/Primary")

    def test_empty_node(self):
        # 空のノードの場合
        node = {}
        info = extract_component_info(node)
        self.assertEqual(info, {})


class TestExtractColor(unittest.TestCase):
    """
    extract_color 関数のテスト
    """
    def test_solid_color(self):
        # 単色の場合
        fills = [
            {
                "type": "SOLID",
                "color": {"r": 1.0, "g": 0.5, "b": 0.0}
            }
        ]
        color = extract_color(fills)
        self.assertEqual(color, "#FF7F00")

    def test_invisible_fill(self):
        # visible=False の fill がある場合
        fills = [
            {
                "type": "SOLID",
                "visible": False,
                "color": {"r": 1.0, "g": 0.0, "b": 0.0}
            },
            {
                "type": "SOLID",
                "color": {"r": 0.0, "g": 1.0, "b": 0.0}
            }
        ]
        color = extract_color(fills)
        self.assertEqual(color, "#00FF00")

    def test_no_fills(self):
        # fills がない場合
        color = extract_color(None)
        self.assertIsNone(color)

    def test_empty_fills(self):
        # fills が空配列の場合
        color = extract_color([])
        self.assertIsNone(color)


class TestExtractTextStyle(unittest.TestCase):
    """
    extract_text_style 関数のテスト
    """
    def test_full_text_style(self):
        # 全てのスタイル情報がある場合
        node = {
            "style": {
                "fontSize": 16,
                "fontWeight": 700,
                "textAlignHorizontal": "CENTER"
            },
            "fills": [
                {"type": "SOLID", "color": {"r": 0.0, "g": 0.0, "b": 0.0}}
            ]
        }
        style = extract_text_style(node)
        self.assertEqual(style["fontSize"], 16)
        self.assertEqual(style["fontWeight"], 700)
        self.assertEqual(style["color"], "#000000")
        self.assertEqual(style["textAlign"], "CENTER")

    def test_default_text_align(self):
        # textAlign が LEFT の場合は省略される
        node = {
            "style": {
                "fontSize": 14,
                "textAlignHorizontal": "LEFT"
            }
        }
        style = extract_text_style(node)
        self.assertNotIn("textAlign", style)

    def test_no_style(self):
        # スタイル情報がない場合
        node = {}
        style = extract_text_style(node)
        self.assertEqual(style, {})


class TestExtractFrameStyle(unittest.TestCase):
    """
    extract_frame_style 関数のテスト
    """
    def test_background_color_and_corner_radius(self):
        # 背景色と角丸がある場合
        node = {
            "fills": [
                {"type": "SOLID", "color": {"r": 1.0, "g": 1.0, "b": 1.0}}
            ],
            "cornerRadius": 8
        }
        style = extract_frame_style(node)
        self.assertEqual(style["backgroundColor"], "#FFFFFF")
        self.assertEqual(style["cornerRadius"], 8)

    def test_no_corner_radius(self):
        # 角丸が 0 の場合は省略される
        node = {
            "fills": [
                {"type": "SOLID", "color": {"r": 0.5, "g": 0.5, "b": 0.5}}
            ],
            "cornerRadius": 0
        }
        style = extract_frame_style(node)
        self.assertEqual(style["backgroundColor"], "#7F7F7F")
        self.assertNotIn("cornerRadius", style)

    def test_no_style(self):
        # スタイル情報がない場合
        node = {}
        style = extract_frame_style(node)
        self.assertEqual(style, {})


class TestToDslWithStyles(unittest.TestCase):
    """
    to_dsl 関数のスタイル関連テスト
    """
    def test_text_with_style(self):
        # スタイル付きTEXTノード
        node = {
            "type": "TEXT",
            "name": "StyledText",
            "characters": "Hello",
            "style": {
                "fontSize": 18,
                "fontWeight": 600
            },
            "fills": [
                {"type": "SOLID", "color": {"r": 0.2, "g": 0.4, "b": 0.6}}
            ]
        }
        dsl = to_dsl(node)
        self.assertEqual(dsl["type"], "TEXT")
        self.assertEqual(dsl["text"], "Hello")
        self.assertIn("style", dsl)
        self.assertEqual(dsl["style"]["fontSize"], 18)
        self.assertEqual(dsl["style"]["fontWeight"], 600)
        self.assertEqual(dsl["style"]["color"], "#336699")

    def test_frame_with_style(self):
        # スタイル付きFRAMEノード
        node = {
            "type": "FRAME",
            "name": "StyledFrame",
            "fills": [
                {"type": "SOLID", "color": {"r": 0.9, "g": 0.9, "b": 0.9}}
            ],
            "cornerRadius": 12,
            "children": []
        }
        dsl = to_dsl(node)
        self.assertEqual(dsl["type"], "FRAME")
        self.assertIn("style", dsl)
        self.assertEqual(dsl["style"]["backgroundColor"], "#E5E5E5")
        self.assertEqual(dsl["style"]["cornerRadius"], 12)

    def test_instance_with_component_info(self):
        # componentId/componentName 付きINSTANCEノード
        node = {
            "type": "INSTANCE",
            "name": "Button Instance",
            "componentId": "789:012",
            "variantProperties": {
                "Type": "Secondary",
                "Size": "Lg"
            },
            "children": []
        }
        dsl = to_dsl(node)
        self.assertEqual(dsl["type"], "INSTANCE")
        self.assertEqual(dsl["componentId"], "789:012")
        self.assertEqual(dsl["componentName"], "Button Instance")
        self.assertIn("props", dsl)
        self.assertEqual(dsl["props"]["variant"], "Secondary")
        self.assertEqual(dsl["props"]["size"], "Lg")

    def test_opacity(self):
        # opacity が 0.5 以下の場合
        node = {
            "type": "TEXT",
            "name": "FadedText",
            "characters": "Faded",
            "opacity": 0.3
        }
        dsl = to_dsl(node)
        self.assertIn("style", dsl)
        self.assertEqual(dsl["style"]["opacity"], 0.3)

    def test_opacity_above_threshold(self):
        # opacity が 0.5 より大きい場合は省略される
        node = {
            "type": "TEXT",
            "name": "NormalText",
            "characters": "Normal",
            "opacity": 0.8
        }
        dsl = to_dsl(node)
        # style が他の理由で追加されていない場合、opacity も追加されない
        if "style" in dsl:
            self.assertNotIn("opacity", dsl["style"])


if __name__ == "__main__":
    unittest.main()
