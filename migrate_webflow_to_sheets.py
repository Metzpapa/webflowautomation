#!/usr/bin/env python
"""
One‑shot migration: Webflow CMS -> Google Sheets (Framer pipeline)

Run:  python migrate_webflow_to_sheets.py  [--dry-run]
"""

import os, sys, json, datetime as dt, argparse, requests, markdown
from io import BytesIO

# --- internal helpers you already have ---
from sheets_client import upsert as sheets_upsert
from s3_client import upload_png

# --- ENV ---
W_API_KEY   = os.getenv("WEBFLOW_API_KEY_RO")
SITE_ID     = os.getenv("WEBFLOW_SITE_ID")
COLLECTION  = os.getenv("WEBFLOW_BLOG_COLLECTION_ID")

if not all([W_API_KEY, SITE_ID, COLLECTION]):
    sys.exit("Missing Webflow env‑vars. Aborting.")

# --- args ---
parser = argparse.ArgumentParser()
parser.add_argument("--dry-run", action="store_true")
args = parser.parse_args()

# --- 1. Get all items from Webflow ---
print("Fetching items from Webflow...")
headers = {
    "Authorization": f"Bearer {W_API_KEY}",
    "accept": "application/json"
}
items_url = f"https://api.webflow.com/v2/collections/{COLLECTION}/items"

all_items = []
cursor = None
while True:
    url = items_url + (f"?cursor={cursor}" if cursor else "")
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    data = resp.json()
    all_items.extend(data["items"])
    cursor = data.get("nextCursor")
    if not cursor:
        break
print(f"Retrieved {len(all_items)} Webflow items.")

# --- 2. Transform + push to Sheets ---
def get_field(item, slug):
    return item["fieldData"].get(slug)

def download_and_upload(img_info):
    if not img_info:
        return ""
    url = img_info.get("url") or img_info.get("fileId")
    if not url:
        return ""
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        return upload_png(r.content)
    except Exception as e:
        print(f"  ! image failed: {e}")
        return ""

MISSING = []
for it in all_items:
    fd = it["fieldData"]

    slug  = fd.get("slug") or it["slug"]
    title = fd.get("name") or "Untitled"

    body_html_webflow = fd.get("post-body") or ""
    # Webflow stored HTML; Framer also wants HTML, so minimal cleaning:
    body_html = body_html_webflow.replace("\n","")

    # Reading time: attempt to reuse else calculate basic
    reading_time = fd.get("post-reading-time-minutes") or max(len(body_html.split())//200,1)

    img_url = ""
    if fd.get("post-main-image"):
        img_url = download_and_upload(fd["post-main-image"])

    row = dict(
        name             = title,
        slug             = slug,
        excerpt_page     = fd.get("post-excerpt-post-page") or "",
        excerpt_featured = fd.get("post-excerpt-post-featured") or "",
        reading_time     = reading_time,
        body_html        = body_html,
        image_url        = img_url,
        draft            = str(it.get("isDraft", False)).upper(),
        created_at       = it.get("createdOn") or dt.datetime.utcnow().isoformat()
    )

    print(f"→ {slug:40}", end="")
    if args.dry_run:
        print("  (dry‑run)")
    else:
        try:
            sheets_upsert(row)
            print("  ✓ migrated")
        except Exception as e:
            print("  ✗ FAILED")
            MISSING.append((slug,e))

if MISSING:
    print("\nSome rows failed:")
    for slug, err in MISSING:
        print(f"  {slug}: {err}")
else:
    print("\nAll done! 🎉")
