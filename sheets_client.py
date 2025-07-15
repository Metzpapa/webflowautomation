import os
import gspread
import datetime as dt
from google.oauth2.service_account import Credentials

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
creds = Credentials.from_service_account_file(
    os.environ["GOOGLE_SHEETS_CREDS_PATH"], scopes=SCOPES
)
ws = gspread.authorize(creds).open_by_key(
    os.environ["GOOGLE_SHEETS_DOC_ID"]
).worksheet("posts")

HEADERS = [
    "name", "slug", "excerpt_page", "excerpt_featured",
    "reading_time", "body_html", "image_url",
    "draft", "created_at"
]

def upsert(row: dict[str, str | int | bool]) -> str:
    slug = row["slug"]
    existing = {r["slug"]: idx+2 for idx, r in enumerate(ws.get_all_records())}
    if slug in existing:
        ws.update(f"A{existing[slug]}:I{existing[slug]}", [[row[h] for h in HEADERS]])
    else:
        ws.append_row([row[h] for h in HEADERS])
    return slug