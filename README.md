# Blog Automation Workflow
python main.py --provider framer-sheets --auto

This tool supports publishing blog posts to either Webflow or Framer (via Google Sheets + S3).

## Environment Variables

Configure the following environment variables in your `.env` file:

### Webflow (default)
```
GEMINI_API_KEY=your_gemini_api_key_here
WEBFLOW_API_KEY=your_webflow_api_key_here
WEBFLOW_SITE_ID=your_webflow_site_id_here
OPENAI_API_KEY=your_openai_api_key_here
```

### Framer (Google Sheets + S3)
```
GOOGLE_SHEETS_CREDS_PATH=path_to_your_google_service_account_json
GOOGLE_SHEETS_DOC_ID=your_google_sheets_document_id
S3_BUCKET=your_s3_bucket_name
S3_REGION=us-east-1
AWS_ACCESS_KEY_ID=your_aws_access_key_id
AWS_SECRET_ACCESS_KEY=your_aws_secret_access_key
```

## Usage Examples

### Webflow (default)
```bash
python main.py
python main.py -n 3
python main.py --linkedin
python main.py --auto
python main.py -n 2 --auto --linkedin
```

### Deploy to Framer
```bash
python main.py --provider framer-sheets
python main.py --provider framer-sheets -n 3 --auto
python main.py --provider framer-sheets --auto --linkedin

python main.py --provider framer-sheets --auto
```

## Command Line Options

- `-n, --num-posts`: Number of posts to generate (default: 1)
- `-l, --linkedin`: Generate LinkedIn post drafts
- `-a, --auto`: Auto mode (skip confirmations)
- `--provider`: Choose CMS provider: `webflow` or `framer-sheets` (default: webflow)

## Framer Setup

1. Create a Google Sheets document with a worksheet named "posts"
2. Set up the required column headers: name, slug, excerpt_page, excerpt_featured, reading_time, body_html, image_url, draft, created_at
3. Create a Google Service Account and download the JSON credentials file
4. Set up an S3 bucket for image storage
5. Configure the environment variables listed above 

gcloud auth application-default login --scopes=openid,https://www.googleapis.com/auth/userinfo.email,https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/spreadsheets,https://www.googleapis.com/auth/drive.file