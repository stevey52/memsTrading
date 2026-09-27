from concurrent.futures import ThreadPoolExecutor, as_completed
import re
import requests
from config import (
    REQUIRE_SOCIALS,
    REQUIRE_TWITTER,
    REQUIRE_TELEGRAM,
    REQUIRE_WEBSITE,
)

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
IPFS_GATEWAYS = [
    "https://cf-ipfs.com/ipfs/",
    "https://ipfs.io/ipfs/",
    "https://gateway.pinata.cloud/ipfs/",
    "https://dweb.link/ipfs/",
]

session = requests.Session()
session.headers.update(HEADERS)


def resolve_ipfs_url(uri: str) -> list[str]:
    """
    Returns candidate URLs across multiple IPFS gateways.
    """
    if not uri:
        return []

    uri = uri.strip()
    if uri.startswith("ipfs://"):
        cid_path = uri.replace("ipfs://", "")
        return [f"{gw}{cid_path}" for gw in IPFS_GATEWAYS]

    # If already an HTTP link to an IPFS gateway
    for gw in ["ipfs.io/ipfs/", "cf-ipfs.com/ipfs/", "gateway.pinata.cloud/ipfs/", "dweb.link/ipfs/"]:
        if gw in uri:
            cid_path = uri.split(gw)[-1]
            return [uri] + [f"{g}{cid_path}" for g in IPFS_GATEWAYS if g not in uri]

    return [uri]


def _fetch_single_gateway(url: str, timeout: float) -> dict | None:
    try:
        res = session.get(url, timeout=timeout)
        if res.status_code == 200:
            data = res.json()
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return None


def fetch_ipfs_metadata(uri: str, timeout: float = 3.0) -> dict | None:
    """
    Fetches token metadata JSON with concurrent multi-gateway failover.
    Returns the first successful response across all gateways (< 800ms typically).
    """
    candidate_urls = resolve_ipfs_url(uri)
    if not candidate_urls:
        return None

    if len(candidate_urls) == 1:
        return _fetch_single_gateway(candidate_urls[0], timeout)

    with ThreadPoolExecutor(max_workers=min(len(candidate_urls), 4)) as executor:
        futures = {executor.submit(_fetch_single_gateway, url, timeout): url for url in candidate_urls}
        for future in as_completed(futures):
            try:
                result = future.result()
                if result is not None:
                    return result
            except Exception:
                continue
    return None


def is_valid_twitter(url: str | None) -> tuple[bool, str]:
    """
    Validates a Twitter / X URL.
    Returns (is_valid, handle_or_error).
    """
    if not url or not isinstance(url, str):
        return False, "Empty or missing URL"

    url = url.strip()
    # Reject placeholder roots
    if url in ["https://x.com", "https://x.com/", "https://twitter.com", "https://twitter.com/", "x.com", "twitter.com"]:
        return False, "Placeholder root URL without handle"

    pattern = r"https?://(?:www\.)?(?:twitter\.com|x\.com)/([a-zA-Z0-9_]{1,30})"
    match = re.search(pattern, url, re.IGNORECASE)
    if not match:
        return False, f"Not a valid Twitter/X profile link: {url}"

    handle = match.group(1).lower()
    if handle in ["home", "explore", "search", "settings", "messages", "intent", "hashtag"]:
        return False, f"Reserved path '{handle}' is not a user handle"

    return True, f"@{match.group(1)}"


def is_valid_telegram(url: str | None) -> tuple[bool, str]:
    """
    Validates a Telegram URL.
    Returns (is_valid, channel_or_error).
    """
    if not url or not isinstance(url, str):
        return False, "Empty or missing URL"

    url = url.strip()
    if url in ["https://t.me", "https://t.me/", "t.me", "t.me/"]:
        return False, "Placeholder root URL without group/channel name"

    pattern = r"https?://(?:www\.)?(?:t\.me|telegram\.me)/([a-zA-Z0-9_]{4,64})"
    match = re.search(pattern, url, re.IGNORECASE)
    if not match:
        return False, f"Not a valid Telegram portal link: {url}"

    channel = match.group(1).lower()
    if channel in ["joinchat", "share"]:
        # Standard invite links like t.me/joinchat/... or t.me/+...
        return True, "Invite link"

    return True, f"t.me/{match.group(1)}"


def is_valid_website(url: str | None) -> tuple[bool, str]:
    """
    Validates a custom project website URL.
    """
    if not url or not isinstance(url, str):
        return False, "Empty or missing URL"

    url = url.strip()
    # Reject generic platforms
    blacklisted = ["pump.fun", "dexscreener.com", "solscan.io", "birdeye.so", "raydium.io"]
    if any(b in url.lower() for b in blacklisted):
        return False, f"Website points to generic platform: {url}"

    pattern = r"https?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
    if not re.search(pattern, url):
        return False, f"Invalid website URL format: {url}"

    return True, url


def check_token_socials(
    uri: str | None,
    symbol: str = "TOKEN",
    name: str = "Unknown",
    require_socials: bool = REQUIRE_SOCIALS,
    require_twitter: bool = REQUIRE_TWITTER,
    require_telegram: bool = REQUIRE_TELEGRAM,
    require_website: bool = REQUIRE_WEBSITE,
) -> tuple[bool, str, dict]:
    """
    Inspects token IPFS metadata and enforces presence and validity of social links.
    Returns (is_approved: bool, reason: str, social_data: dict).
    """
    if not require_socials and not require_twitter and not require_telegram and not require_website:
        return True, "Social filters disabled", {}

    if not uri:
        return False, "No metadata URI provided (Zero social footprint)", {}

    metadata = fetch_ipfs_metadata(uri)
    if not metadata:
        return False, "Could not fetch IPFS metadata from gateways", {}

    twitter = metadata.get("twitter")
    telegram = metadata.get("telegram")
    website = metadata.get("website")
    description = (metadata.get("description") or "").strip()
    image = metadata.get("image")

    social_data = {
        "twitter": twitter,
        "telegram": telegram,
        "website": website,
        "description": description,
        "image": image,
    }

    tw_valid, tw_info = is_valid_twitter(twitter)
    tg_valid, tg_info = is_valid_telegram(telegram)
    web_valid, web_info = is_valid_website(website)

    social_data["twitter_handle"] = tw_info if tw_valid else None
    social_data["telegram_group"] = tg_info if tg_valid else None

    # Check strict requirements
    if require_twitter and not tw_valid:
        return False, f"Missing or invalid Twitter/X: {tw_info}", social_data

    if require_telegram and not tg_valid:
        return False, f"Missing or invalid Telegram: {tg_info}", social_data

    if require_website and not web_valid:
        return False, f"Missing or invalid Website: {web_info}", social_data

    # Check general REQUIRE_SOCIALS (must have at least Twitter or Telegram)
    if require_socials and not (tw_valid or tg_valid):
        return False, "Token has neither valid Twitter/X nor Telegram", social_data

    # Spam description check
    if len(description) < 10 and not (tw_valid and tg_valid):
        return False, "Suspicious empty/minimal description with incomplete socials", social_data

    summary_parts = []
    if tw_valid:
        summary_parts.append(f"Twitter: {tw_info}")
    if tg_valid:
        summary_parts.append(f"TG: {tg_info}")
    if web_valid:
        summary_parts.append(f"Web: {web_info}")

    return True, f"Verified socials ({', '.join(summary_parts)})", social_data
