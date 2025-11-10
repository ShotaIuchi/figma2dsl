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


if __name__ == "__main__":
    unittest.main()
