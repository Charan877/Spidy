import unittest
from backend.core.openrouter_client import parse_json_response


class TestJsonParser(unittest.TestCase):
    def test_prose_preamble(self):
        raw_prose = "User Safety: safe"
        res = parse_json_response(raw_prose)
        self.assertIsInstance(res, dict)
        self.assertIn("project_name", res)

    def test_mixed_json(self):
        raw_mixed = 'User Safety: safe\n\n```json\n{"project_name": "Messi 3D Statue", "detected_language": "HTML/CSS/JS"}\n```'
        res = parse_json_response(raw_mixed)
        self.assertEqual(res["project_name"], "Messi 3D Statue")


if __name__ == "__main__":
    unittest.main()
