import yaml
import logging
import requests
from bs4 import BeautifulSoup

log = logging.getLogger("call_bot")


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def format_message(template: str, job_posting: dict) -> str:
    return template.format(**job_posting)


def fetch_job_description(url: str) -> str:
    """Fetch job posting URL and extract text content."""
    try:
        resp = requests.get(url, timeout=15, headers={
            "User-Agent": "Mozilla/5.0 (compatible; JobeeBot/1.0)"
        })
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Remove scripts, styles, nav, footer
        for tag in soup(["script", "style", "nav", "footer", "header", "iframe"]):
            tag.decompose()

        text = soup.get_text(separator="\n", strip=True)

        # Collapse blank lines
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        result = "\n".join(lines)

        # Limit to 3000 chars to keep prompt reasonable
        if len(result) > 3000:
            result = result[:3000] + "\n..."

        log.info(f"Fetched job description from {url} ({len(result)} chars)")
        return result
    except Exception as e:
        log.warning(f"Failed to fetch job description from {url}: {e}")
        return ""
