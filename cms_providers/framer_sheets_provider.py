# webflowautomation/cms_providers/framer_sheets_provider.py

import markdown
import datetime as dt
# The s3_client is no longer needed as we are skipping image uploads for Framer.
# from s3_client import upload_png
from sheets_client import upsert as sheets_upsert
from cms_providers import CMSProvider

class FramerSheetsProvider(CMSProvider):
    """
    A CMS Provider that publishes blog content to a Google Sheet,
    which is then used by Framer.

    This implementation intentionally skips image handling and sets the
    image_url to an empty string.
    """
    def publish(self, *, slug: str, html_body: str, metadata: dict, image_bytes: bytes | None) -> str | None:
        """
        Formats the post data and upserts it into a Google Sheet.

        Args:
            slug (str): The URL-friendly slug for the post.
            html_body (str): The main content of the post in Markdown format.
            metadata (dict): A dictionary containing post metadata like title, excerpts, etc.
            image_bytes (bytes | None): The raw bytes of a generated image. This argument
                                        is ignored by this provider.

        Returns:
            str | None: The slug of the post if the upsert is successful, otherwise None.
        """
        # Image handling is skipped. The image_url is always an empty string.
        image_url = ""

        # Convert the body from Markdown to HTML for the sheet.
        body_html_content = markdown.markdown(html_body, extensions=[])

        # Prepare the row dictionary with all required columns for the Google Sheet.
        row = dict(
            name=metadata.get("title", "Untitled Post"),
            slug=slug,
            excerpt_page=metadata.get("excerpt_page", ""),
            excerpt_featured=metadata.get("excerpt_featured", ""),
            reading_time=metadata.get("reading_time", 1),
            body_html=body_html_content,
            image_url=image_url,  # This will be an empty string
            draft=str(metadata.get("_draft", True)).upper(),
            created_at=dt.datetime.utcnow().isoformat()
        )

        # Call the sheets_client to add or update the row in the spreadsheet.
        # The sheets_upsert function is expected to return the slug on success.
        return sheets_upsert(row)