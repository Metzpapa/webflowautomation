# webflowautomation/tests/test_framer_provider.py

import unittest
from unittest.mock import patch
from cms_providers.framer_sheets_provider import FramerSheetsProvider

class TestFramerSheetsProvider(unittest.TestCase):
    """
    Unit tests for the FramerSheetsProvider.
    These tests verify that the provider correctly formats data for Google Sheets
    and explicitly ignores image data, as per the new requirements.
    """

    def setUp(self):
        """Set up a new FramerSheetsProvider instance for each test."""
        self.provider = FramerSheetsProvider()

    @patch('cms_providers.framer_sheets_provider.sheets_upsert')
    def test_publish_formats_row_correctly_and_ignores_image(self, mock_sheets_upsert):
        """
        Verify that publish() creates a correct row for Google Sheets,
        converts markdown to HTML, and sets image_url to an empty string
        even when image_bytes are provided.
        """
        # Arrange: Mock the sheets client and prepare test data
        mock_sheets_upsert.return_value = "test-slug-1"
        
        slug = "test-slug-1"
        html_body = "# Test Header\n\nThis is a test."
        metadata = {
            "title": "Test Post Title",
            "excerpt_page": "This is the page excerpt.",
            "excerpt_featured": "This is the featured excerpt.",
            "reading_time": 3,
        }
        # Provide image bytes to ensure they are explicitly ignored by the method
        image_bytes = b"some_fake_image_data"
        
        # Act: Call the publish method
        result = self.provider.publish(
            slug=slug,
            html_body=html_body,
            metadata=metadata,
            image_bytes=image_bytes
        )
        
        # Assert: Check the results and the data passed to the mock
        self.assertEqual(result, "test-slug-1")
        
        mock_sheets_upsert.assert_called_once()
        # Get the dictionary that was passed to sheets_upsert
        call_args = mock_sheets_upsert.call_args[0][0]
        
        self.assertEqual(call_args["name"], "Test Post Title")
        self.assertEqual(call_args["slug"], "test-slug-1")
        self.assertEqual(call_args["excerpt_page"], "This is the page excerpt.")
        self.assertEqual(call_args["reading_time"], 3)
        self.assertEqual(call_args["body_html"], "<h1>Test Header</h1>\n<p>This is a test.</p>")
        
        # This is the most important assertion for the new logic:
        # Verify the image_url is an empty string, proving S3 upload was skipped.
        self.assertEqual(call_args["image_url"], "")
        
        self.assertIn("created_at", call_args)

    @patch('cms_providers.framer_sheets_provider.sheets_upsert')
    def test_publish_handles_draft_status_true(self, mock_sheets_upsert):
        """
        Verify that if metadata contains `_draft: True`, the row's 'draft'
        field is set to "TRUE".
        """
        # Arrange
        slug = "test-slug-draft"
        metadata = {
            "title": "Draft Post",
            "_draft": True,
            "excerpt_page": "", "excerpt_featured": "", "reading_time": 1
        }
        
        # Act
        self.provider.publish(slug=slug, html_body="", metadata=metadata, image_bytes=None)
        
        # Assert
        mock_sheets_upsert.assert_called_once()
        call_args = mock_sheets_upsert.call_args[0][0]
        self.assertEqual(call_args["draft"], "TRUE")

    @patch('cms_providers.framer_sheets_provider.sheets_upsert')
    def test_publish_defaults_to_draft_true(self, mock_sheets_upsert):
        """
        Verify that if metadata does NOT contain a `_draft` key, the row's
        'draft' field defaults to "TRUE".
        """
        # Arrange
        slug = "test-slug-default-draft"
        # Metadata dictionary without the '_draft' key
        metadata = {
            "title": "Default Draft Post",
            "excerpt_page": "", "excerpt_featured": "", "reading_time": 1
        }
        
        # Act
        self.provider.publish(slug=slug, html_body="", metadata=metadata, image_bytes=None)
        
        # Assert
        mock_sheets_upsert.assert_called_once()
        call_args = mock_sheets_upsert.call_args[0][0]
        self.assertEqual(call_args["draft"], "TRUE")

    @patch('cms_providers.framer_sheets_provider.sheets_upsert')
    def test_publish_handles_draft_status_false(self, mock_sheets_upsert):
        """
        Verify that if metadata contains `_draft: False`, the row's 'draft'
        field is set to "FALSE".
        """
        # Arrange
        slug = "test-slug-published"
        metadata = {
            "title": "Published Post",
            "_draft": False,
            "excerpt_page": "", "excerpt_featured": "", "reading_time": 1
        }
        
        # Act
        self.provider.publish(slug=slug, html_body="", metadata=metadata, image_bytes=None)
        
        # Assert
        mock_sheets_upsert.assert_called_once()
        call_args = mock_sheets_upsert.call_args[0][0]
        self.assertEqual(call_args["draft"], "FALSE")


if __name__ == '__main__':
    unittest.main()