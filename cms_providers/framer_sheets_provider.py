import markdown
import datetime as dt
from s3_client import upload_png
from sheets_client import upsert as sheets_upsert
from cms_providers import CMSProvider

class FramerSheetsProvider(CMSProvider):
    def publish(self, *, slug, html_body, metadata, image_bytes):
        image_url = upload_png(image_bytes) if image_bytes else ""
        row = dict(
            name=metadata["title"],
            slug=slug,
            excerpt_page=metadata["excerpt_page"],
            excerpt_featured=metadata["excerpt_featured"],
            reading_time=metadata["reading_time"],
            body_html=markdown.markdown(html_body, extensions=[]),
            image_url=image_url,
            draft=str(metadata.get("_draft", True)).upper(),
            created_at=dt.datetime.utcnow().isoformat()
        )
        return sheets_upsert(row)  # returns slug