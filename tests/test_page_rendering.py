import unittest

from pdf_extraction.page_rendering import parse_bbox, parse_pages


class PageRenderingTest(unittest.TestCase):
    def test_parse_bbox(self) -> None:
        self.assertEqual(parse_bbox("10,20,30,40"), (10.0, 20.0, 30.0, 40.0))

    def test_parse_bbox_rejects_inverted_coordinates(self) -> None:
        with self.assertRaises(ValueError):
            parse_bbox("10,20,5,40")

    def test_parse_pages(self) -> None:
        self.assertEqual(parse_pages("1,3-5,5"), [1, 3, 4, 5])

    def test_parse_pages_accepts_empty_value(self) -> None:
        self.assertIsNone(parse_pages(None))


if __name__ == "__main__":
    unittest.main()
