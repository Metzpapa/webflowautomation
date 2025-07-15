import unittest
from unittest.mock import patch, MagicMock
import datetime as dt
from cms_providers.framer_sheets_provider import FramerSheetsProvider


class TestFramerSheetsProvider(unittest.TestCase):
    def setUp(self):
        self.provider = FramerSheetsProvider()

    @patch('cms_providers.framer_sheets_provider.upload_png')
    @patch('cms_providers.framer_sheets_provider.sheets_upsert')
    def test_publish_with_image(self, mock_sheets_upsert, mock_upload_png):
        # Mock the upload_png function
        mock_upload_png.return_value = "https://example.com/image.png"
        mock_sheets_upsert.return_value = "test-slug"
        
        # Test data
        slug = "test-slug"
        html_body = "# Test Content\n\nThis is a test post."
        metadata = {
            "title": "Test Post",
            "excerpt_page": "Test excerpt for page",
            "excerpt_featured": "Test excerpt for featured",
            "reading_time": 5,
            "_draft": False
        }
        image_bytes = b"fake_image_bytes"
        
        # Call the publish method
        result = self.provider.publish(
            slug=slug,
            html_body=html_body,
            metadata=metadata,
            image_bytes=image_bytes
        )
        
        # Verify the result
        self.assertEqual(result, "test-slug")
        
        # Verify upload_png was called
        mock_upload_png.assert_called_once_with(image_bytes)
        
        # Verify sheets_upsert was called with correct data
        mock_sheets_upsert.assert_called_once()
        call_args = mock_sheets_upsert.call_args[0][0]
        
        self.assertEqual(call_args["name"], "Test Post")
        self.assertEqual(call_args["slug"], "test-slug")
        self.assertEqual(call_args["excerpt_page"], "Test excerpt for page")
        self.assertEqual(call_args["excerpt_featured"], "Test excerpt for featured")
        self.assertEqual(call_args["reading_time"], 5)
        self.assertEqual(call_args["image_url"], "https://example.com/image.png")
        self.assertEqual(call_args["draft"], "FALSE")
        self.assertIn("body_html", call_args)
        self.assertIn("created_at", call_args)

    @patch('cms_providers.framer_sheets_provider.upload_png')
    @patch('cms_providers.framer_sheets_provider.sheets_upsert')
    def test_publish_without_image(self, mock_sheets_upsert, mock_upload_png):
        # Mock the sheets_upsert function
        mock_sheets_upsert.return_value = "test-slug-no-image"
        
        # Test data
        slug = "test-slug-no-image"
        html_body = "# Test Content\n\nThis is a test post without image."
        metadata = {
            "title": "Test Post No Image",
            "excerpt_page": "Test excerpt for page",
            "excerpt_featured": "Test excerpt for featured",
            "reading_time": 3
        }
        image_bytes = None
        
        # Call the publish method
        result = self.provider.publish(
            slug=slug,
            html_body=html_body,
            metadata=metadata,
            image_bytes=image_bytes
        )
        
        # Verify the result
        self.assertEqual(result, "test-slug-no-image")
        
        # Verify upload_png was NOT called
        mock_upload_png.assert_not_called()
        
        # Verify sheets_upsert was called with correct data
        mock_sheets_upsert.assert_called_once()
        call_args = mock_sheets_upsert.call_args[0][0]
        
        self.assertEqual(call_args["name"], "Test Post No Image")
        self.assertEqual(call_args["slug"], "test-slug-no-image")
        self.assertEqual(call_args["image_url"], "")
        self.assertEqual(call_args["draft"], "TRUE")  # Default draft status

    @patch('cms_providers.framer_sheets_provider.upload_png')
    @patch('cms_providers.framer_sheets_provider.sheets_upsert')
    def test_publish_with_draft_status(self, mock_sheets_upsert, mock_upload_png):
        # Mock the sheets_upsert function
        mock_sheets_upsert.return_value = "test-slug-draft"
        
        # Test data
        slug = "test-slug-draft"
        html_body = "# Draft Content"
        metadata = {
            "title": "Draft Post",
            "excerpt_page": "Draft excerpt",
            "excerpt_featured": "Draft featured",
            "reading_time": 2,
            "_draft": True
        }
        image_bytes = None
        
        # Call the publish method
        result = self.provider.publish(
            slug=slug,
            html_body=html_body,
            metadata=metadata,
            image_bytes=image_bytes
        )
        
        # Verify the result
        self.assertEqual(result, "test-slug-draft")
        
        # Verify sheets_upsert was called with correct data
        mock_sheets_upsert.assert_called_once()
        call_args = mock_sheets_upsert.call_args[0][0]
        
        self.assertEqual(call_args["draft"], "TRUE")


if __name__ == '__main__':
    unittest.main()