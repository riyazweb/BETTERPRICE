import json
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, quote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

# Known seller → BuyHatke CDN logo URLs (filenames confirmed from live HTML)
SELLER_LOGO_MAP: Dict[str, str] = {
    "amazon":           "https://compare.buyhatke.com/images/site_icons_m/amazon.png",
    "flipkart":         "https://compare.buyhatke.com/images/site_icons_m/flipkart1.png",
    "shopsy":           "https://compare.buyhatke.com/images/site_icons_m/shopsy.png",
    "myntra":           "https://compare.buyhatke.com/images/site_icons_m/myntra1.png",
    "ajio":             "https://compare.buyhatke.com/images/site_icons_m/ajio.png",
    "ajio lux":         "https://compare.buyhatke.com/images/site_icons_m/ajioLuxe.png",
    "tatacliq":         "https://compare.buyhatke.com/images/site_icons_m/tatacliq.png",
    "nykaa":            "https://compare.buyhatke.com/images/site_icons_m/nykaa.png",
    "jiomart":          "https://compare.buyhatke.com/images/site_icons_m/jiomart.png",
    "croma":            "https://compare.buyhatke.com/images/site_icons_m/croma.png",
    "blinkit":          "https://compare.buyhatke.com/images/site_icons_m/blinkit.png",
    "bigbasket":        "https://compare.buyhatke.com/images/site_icons_m/bigBasket.png",
    "zepto":            "https://compare.buyhatke.com/images/site_icons_m/zepto.png",
    "reliance digital": "https://compare.buyhatke.com/images/site_icons_m/reliancedigital.png",
    "vijay sales":      "https://compare.buyhatke.com/images/site_icons_m/vsales.png",
    "boat":             "https://compare.buyhatke.com/images/site_icons_m/boatLifestyle.png",
    "boat-lifestyle":   "https://compare.buyhatke.com/images/site_icons_m/boatLifestyle.png",
    "snapdeal":         "https://compare.buyhatke.com/images/site_icons_m/snapdeal.png",
    "meesho":           "https://compare.buyhatke.com/images/site_icons_m/meesho.png",
}

# Known seller position IDs used in BuyHatke tracking redirect URLs
# Pattern: https://tracking.buyhatke.com/Navigation/?pos={POS}&source=price-tracker&ext1=product_deal_card&ext2=&link={ENCODED_URL}
SELLER_POS_MAP: Dict[str, int] = {
    "amazon":           63,
    "flipkart":         2,
    "shopsy":           8702,
    "myntra":           111,
    "ajio":             76,
    "ajio lux":         76,
    "snapdeal":         18,
    "meesho":           8714,
    "nykaa":            8695,
    "tatacliq":         8703,
    "jiomart":          8708,
    "croma":            8704,
    "reliance digital": 8706,
    "vijay sales":      8707,
    "blinkit":          8710,
    "zepto":            8717,
    "bigbasket":        8711,
}

from . import db
from .models import SearchHistory
from .schemas import detect_marketplace


class ScraperError(Exception):
    pass


class UnsupportedMarketplaceError(ScraperError):
    pass


class UpstreamNotFoundError(ScraperError):
    pass


class BotDetectionError(ScraperError):
    pass


class UpstreamTimeoutError(ScraperError):
    pass


@dataclass(frozen=True)
class ScrapeResult:
    title: str
    price: Optional[float]
    image_url: Optional[str]
    thumbnail_images: List[str]
    source: str
    marketplace: str
    tracker_url: Optional[str]
    alternatives: List[Dict[str, Any]]


class BaseScraper(ABC):
    @abstractmethod
    def scrape(self, url: str, marketplace: Optional[str] = None) -> ScrapeResult:
        raise NotImplementedError


class MarketplaceScraper(BaseScraper):
    MARKETPLACE_POSITIONS = {
        "amazon": 63,
        "flipkart": 2,
    }

    def __init__(self, config: Dict[str, Any], logger: logging.Logger) -> None:
        self.timeout = config.get("REQUEST_TIMEOUT", 15)
        self.user_agent = config.get(
            "USER_AGENT",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )
        self.logger = logger

    def scrape(self, url: str, marketplace: Optional[str] = None) -> ScrapeResult:
        resolved_marketplace = marketplace or detect_marketplace(url)
        if resolved_marketplace not in self.MARKETPLACE_POSITIONS:
            raise UnsupportedMarketplaceError("Marketplace is not supported by current scraper")

        product_id = self._extract_product_id(url, resolved_marketplace)
        if not product_id:
            raise ScraperError("Could not extract product identifier from URL")

        api_url = (
            "https://buyhatke.com/api/productData"
            f"?pos={self.MARKETPLACE_POSITIONS[resolved_marketplace]}&pid={product_id}"
        )
        payload = self._get_json(api_url)

        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict):
            raise ScraperError("Unexpected upstream response structure")

        title = data.get("name") or "Unknown Product"
        price = self._to_float(data.get("cur_price"))
        site_pos = data.get("site_pos")
        internal_pid = data.get("internalPid")
        image_url = None
        thumbnail_images: List[str] = []
        raw_thumbnails = data.get("thumbnailImages")
        if isinstance(raw_thumbnails, list) and raw_thumbnails:
            thumbnail_images = [str(t) for t in raw_thumbnails if t]
            image_url = thumbnail_images[0]
        elif isinstance(data.get("image"), str):
            image_url = data.get("image")
            thumbnail_images = [image_url] if image_url else []

        tracker_url = self._build_tracker_url(
            marketplace=resolved_marketplace,
            title=title,
            site_pos=site_pos,
            internal_pid=internal_pid,
        )

        alternatives: List[Dict[str, Any]] = []
        if tracker_url:
            try:
                alternatives = self._scrape_alternatives(tracker_url)
            except ScraperError as exc:
                self.logger.warning(
                    "Alternative scraping failed",
                    extra={
                        "context": {
                            "tracker_url": tracker_url,
                            "error": str(exc),
                        }
                    },
                )

        return ScrapeResult(
            title=title,
            price=price,
            image_url=image_url,
            thumbnail_images=thumbnail_images,
            source="buyhatke",
            marketplace=resolved_marketplace,
            tracker_url=tracker_url,
            alternatives=alternatives,
        )

    def _build_tracker_url(
        self,
        marketplace: str,
        title: str,
        site_pos: Any,
        internal_pid: Any,
    ) -> Optional[str]:
        if site_pos is None or internal_pid in (None, ""):
            return None
        slug = re.sub(r"[^\w-]+", "-", str(title).lower()).strip("-")
        if not slug:
            slug = f"product-{internal_pid}"
        return f"https://buyhatke.com/{marketplace}-{slug}-price-in-india-{site_pos}-{internal_pid}"

    def _scrape_alternatives(self, tracker_url: str) -> List[Dict[str, Any]]:
        response = self._get_response(tracker_url)
        soup = BeautifulSoup(response.text, "html.parser")

        # ── Primary: SvelteKit bootstrap script has link + position + logo ────
        results = self._extract_from_sveltekit(soup)
        if results:
            return results

        # ── Fallback A: HTML extraction (logos/prices) + __NEXT_DATA__ links ──
        results = self._extract_from_html(soup, tracker_url)
        link_map = self._extract_link_map_from_next_data(soup)
        for entry in results:
            if not entry.get("link"):
                key = entry["seller"].lower().strip()
                entry["link"] = link_map.get(key)
                if not entry["link"]:
                    for lm_key, lm_url in link_map.items():
                        if key in lm_key or lm_key in key:
                            entry["link"] = lm_url
                            break
                if not entry["link"]:
                    entry["link"] = tracker_url
        if results:
            return results

        # ── Fallback B: __NEXT_DATA__ full extraction ─────────────────────────
        return self._extract_from_next_data(soup, tracker_url)

    # ── SvelteKit dealsList extraction ────────────────────────────────────────

    def _extract_from_sveltekit(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Parse the SvelteKit bootstrap script which contains a dealsList JS array
        with link, position, site_name, site_logo/site_image per seller."""
        for script in soup.find_all("script"):
            txt = script.string or ""
            if "dealsList:" not in txt:
                continue

            marker = "dealsList:["
            start = txt.find(marker)
            if start == -1:
                continue
            start += len(marker)

            # Walk forward to find the matching closing ]
            depth = 1
            i = start
            in_str = False
            escape_next = False
            while i < len(txt) and depth > 0:
                ch = txt[i]
                if escape_next:
                    escape_next = False
                elif ch == "\\" and in_str:
                    escape_next = True
                elif ch == '"' and not escape_next:
                    in_str = not in_str
                elif not in_str:
                    if ch == "[":
                        depth += 1
                    elif ch == "]":
                        depth -= 1
                i += 1

            deals_raw = txt[start: i - 1]
            items_raw = self._split_js_objects(deals_raw)

            results: List[Dict[str, Any]] = []
            seen: set = set()

            for item_str in items_raw:
                site_name_m = re.search(r'site_name:"([^"]*)"', item_str)
                link_m = re.search(r'\blink:"([^"]*)"', item_str)
                position_m = re.search(r'\bposition:(\d+)', item_str)
                price_m = re.search(r'\bprice:(\d+(?:\.\d+)?)', item_str)
                logo_m = (
                    re.search(r'site_logo:"([^"]*)"', item_str)
                    or re.search(r'site_image:"([^"]*)"', item_str)
                )

                if not (site_name_m and link_m and position_m):
                    continue

                seller = site_name_m.group(1).strip()
                product_url = link_m.group(1).strip()
                pos = int(position_m.group(1))
                price_val = self._to_float(price_m.group(1)) if price_m else None
                logo = logo_m.group(1).strip() if logo_m else self._resolve_logo_url(None, seller)

                tracking_link = (
                    f"https://tracking.buyhatke.com/Navigation/"
                    f"?pos={pos}&source=price-tracker"
                    f"&ext1=product_deal_card&ext2="
                    f"&link={quote(product_url, safe='')}"
                )

                fp = f"{seller}|{price_val}"
                if fp in seen:
                    continue
                seen.add(fp)

                if price_val is not None:
                    price_display = (
                        f"₹{int(price_val):,}" if price_val == int(price_val)
                        else f"₹{price_val:,.2f}"
                    )
                else:
                    price_display = "N/A"

                results.append({
                    "seller": seller,
                    "price": price_val,
                    "price_display": price_display,
                    "link": tracking_link,
                    "logo_url": logo,
                })

            results.sort(
                key=lambda e: (
                    e["price"] is None,
                    e["price"] if e["price"] is not None else float("inf"),
                )
            )
            return results

        return []

    @staticmethod
    def _split_js_objects(txt: str) -> List[str]:
        """Split a JS array body string into individual top-level object strings."""
        objects: List[str] = []
        depth = 0
        start: Optional[int] = None
        in_str = False
        escape_next = False
        for i, ch in enumerate(txt):
            if escape_next:
                escape_next = False
                continue
            if ch == "\\" and in_str:
                escape_next = True
                continue
            if ch == '"':
                in_str = not in_str
                continue
            if in_str:
                continue
            if ch == "{":
                if depth == 0:
                    start = i
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0 and start is not None:
                    objects.append(txt[start: i + 1])
                    start = None
        return objects

    # ── __NEXT_DATA__ link-map extraction ──────────────────────────────────────

    def _extract_link_map_from_next_data(self, soup: BeautifulSoup) -> Dict[str, str]:
        """Return {seller_name_lower: buy_url} by walking __NEXT_DATA__ JSON."""
        script = soup.find("script", id="__NEXT_DATA__")
        if not script or not script.string:
            return {}
        try:
            next_data = json.loads(script.string)
        except (ValueError, TypeError):
            return {}
        link_map: Dict[str, str] = {}
        self._walk_json_for_links(next_data, link_map, depth=0)
        return link_map

    def _walk_json_for_links(self, node: Any, out: Dict[str, str], depth: int) -> None:
        if depth > 15:
            return
        if isinstance(node, list):
            for item in node:
                self._walk_json_for_links(item, out, depth + 1)
        elif isinstance(node, dict):
            seller = (
                node.get("site_name") or node.get("siteName")
                or node.get("seller") or node.get("store")
                or node.get("source")
            )
            raw_url = (
                node.get("url") or node.get("buy_url") or node.get("buyUrl")
                or node.get("affiliate_url") or node.get("affiliateUrl")
                or node.get("offerUrl") or node.get("offer_url")
                or node.get("deep_link") or node.get("deeplink")
                or node.get("link")
            )
            # site_pos from __NEXT_DATA__ is the destination seller's tracking ID
            pos = node.get("site_pos") or node.get("sitePos") or node.get("pos")

            if seller and raw_url:
                key = str(seller).strip().lower()
                url_str = str(raw_url).strip()
                if url_str.startswith("//"):
                    url_str = f"https:{url_str}"
                if url_str.startswith("http") and key not in out:
                    resolved_pos = pos or SELLER_POS_MAP.get(key)
                    if resolved_pos:
                        out[key] = (
                            f"https://tracking.buyhatke.com/Navigation/"
                            f"?pos={resolved_pos}&source=price-tracker"
                            f"&ext1=product_deal_card&ext2="
                            f"&link={quote(url_str, safe='')}"
                        )
                    else:
                        out[key] = url_str
            for value in node.values():
                self._walk_json_for_links(value, out, depth + 1)

    # ── __NEXT_DATA__ full extraction (fallback only) ─────────────────────────

    def _extract_from_next_data(
        self, soup: BeautifulSoup, tracker_url: str
    ) -> List[Dict[str, Any]]:
        script = soup.find("script", id="__NEXT_DATA__")
        if not script or not script.string:
            return []
        try:
            next_data = json.loads(script.string)
        except (ValueError, TypeError):
            return []

        candidates: List[Dict[str, Any]] = []
        self._walk_json(next_data, candidates, depth=0)

        seen: set = set()
        results: List[Dict[str, Any]] = []
        for entry in candidates:
            fp = f"{entry['seller']}|{entry['price']}"
            if fp in seen:
                continue
            seen.add(fp)
            results.append(entry)

        results.sort(
            key=lambda e: (e["price"] is None, e["price"] if e["price"] is not None else float("inf"))
        )
        return results

    def _walk_json(self, node: Any, out: List[Dict], depth: int) -> None:
        if depth > 15:
            return
        if isinstance(node, list):
            # Check if this list looks like a price-comparison array
            parsed = [self._try_parse_price_node(item) for item in node]
            valid = [p for p in parsed if p is not None]
            if len(valid) >= 2:           # need at least 2 merchants to count
                out.extend(valid)
                return                    # don't recurse further inside
            for item in node:
                self._walk_json(item, out, depth + 1)
        elif isinstance(node, dict):
            for value in node.values():
                self._walk_json(value, out, depth + 1)

    def _try_parse_price_node(self, item: Any) -> Optional[Dict[str, Any]]:
        if not isinstance(item, dict):
            return None
        lowered = {str(k).lower(): v for k, v in item.items()}

        # Must have both a price-like field and a seller-like field
        price_val = self._to_float(
            lowered.get("price") or lowered.get("cur_price")
            or lowered.get("selling_price") or lowered.get("sp")
            or lowered.get("mrp")
        )
        seller = (
            item.get("site_name") or item.get("siteName")
            or item.get("seller") or item.get("store")
            or item.get("source") or item.get("name")
        )
        if price_val is None or not seller:
            return None
        seller = str(seller).strip()

        raw_link = (
            item.get("buy_url") or item.get("buyUrl")
            or item.get("link") or item.get("url")
            or item.get("deep_link") or item.get("deeplink")
            or item.get("affiliate_url") or item.get("affiliateUrl")
        )
        pos = item.get("site_pos") or item.get("sitePos") or item.get("pos")
        link: Optional[str] = None
        if raw_link:
            raw_link = str(raw_link).strip()
            if raw_link.startswith("//"):
                raw_link = f"https:{raw_link}"
            if raw_link.startswith("http"):
                resolved_pos = pos or SELLER_POS_MAP.get(seller.lower().strip())
                if resolved_pos:
                    link = (
                        f"https://tracking.buyhatke.com/Navigation/"
                        f"?pos={resolved_pos}&source=price-tracker"
                        f"&ext1=product_deal_card&ext2="
                        f"&link={quote(raw_link, safe='')}"
                    )
                else:
                    link = raw_link

        raw_logo = (
            item.get("logo") or item.get("logo_url") or item.get("logoUrl")
            or item.get("site_logo") or item.get("siteLogo")
            or item.get("icon") or item.get("image")
        )
        logo = self._resolve_logo_url(raw_logo, seller)

        price_display = f"₹{int(price_val):,}" if price_val == int(price_val) else f"₹{price_val:,.2f}"

        return {
            "seller": seller,
            "price": price_val,
            "price_display": price_display,
            "link": link,
            "logo_url": logo,
        }

    # ── HTML fallback extraction ───────────────────────────────────────────────

    def _extract_from_html(
        self, soup: BeautifulSoup, tracker_url: str
    ) -> List[Dict[str, Any]]:
        container = None
        section = soup.find("section", class_="grid")
        if section:
            container = section.find("div", class_="overflow-y-auto")
        if not container:
            for div in soup.find_all("div"):
                cls = div.get("class") or []
                if "overflow-y-auto" in cls and "scroll-hide" in cls:
                    container = div
                    break
        if not container:
            for div in soup.find_all("div", class_="overflow-y-auto"):
                if div.find(["button", "li"]):
                    container = div
                    break
        if not container:
            container = soup.find("ul")
        if not container:
            return []

        items = container.find_all("button", recursive=False) or container.find_all("button") or container.find_all("li")
        results: List[Dict[str, Any]] = []
        seen: set = set()

        for item in items:
            seller = self._extract_seller_html(item)
            price_value, price_display = self._extract_price_html(item)
            if seller == "N/A" and price_value is None:
                continue
            link = self._extract_link_html(item, tracker_url)
            logo = self._resolve_logo_url(self._raw_logo_url(item, tracker_url), seller)
            fp = f"{seller}|{price_display}"
            if fp in seen:
                continue
            seen.add(fp)
            results.append({"seller": seller, "price": price_value, "price_display": price_display, "link": link, "logo_url": logo})

        results.sort(key=lambda e: (e["price"] is None, e["price"] if e["price"] is not None else float("inf")))
        return results

    def _extract_product_id(self, url: str, marketplace: str) -> Optional[str]:
        if marketplace == "amazon":
            match = re.search(r"/(?:dp|gp/product)/([A-Z0-9]{10})", url)
            return match.group(1) if match else None

        if marketplace == "flipkart":
            parsed_url = urlparse(url)
            query_params = parse_qs(parsed_url.query)
            pid = query_params.get("pid", [None])[0]
            if pid:
                return pid
            match = re.search(r"pid=([A-Z0-9]+)", url)
            return match.group(1) if match else None

        return None

    def _get_json(self, url: str) -> Dict[str, Any]:
        response = self._get_response(url)
        try:
            return response.json()
        except ValueError as exc:
            raise ScraperError("Upstream returned invalid JSON") from exc

    def _get_response(self, url: str) -> requests.Response:
        headers = {"User-Agent": self.user_agent}
        try:
            response = requests.get(url, headers=headers, timeout=self.timeout)
        except requests.exceptions.Timeout as exc:
            raise UpstreamTimeoutError("Upstream request timed out") from exc
        except requests.exceptions.RequestException as exc:
            raise ScraperError("Upstream request failed") from exc

        if response.status_code == 404:
            raise UpstreamNotFoundError("Upstream resource not found")
        if response.status_code == 503:
            raise BotDetectionError("Upstream blocked request (possible bot detection)")

        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as exc:
            raise ScraperError(f"Upstream HTTP error: {response.status_code}") from exc

        return response

    # ── Logo resolution ────────────────────────────────────────────────────────

    @staticmethod
    def _resolve_logo_url(raw_url: Optional[str], seller: str) -> Optional[str]:
        """Return an absolute, working logo URL: scraped → CDN map → None."""
        if raw_url:
            url = str(raw_url).strip()
            if url.startswith("//"):
                url = f"https:{url}"
            elif url.startswith("/images/"):
                url = f"https://compare.buyhatke.com{url}"
            elif url.startswith("/"):
                url = f"https://buyhatke.com{url}"
            if url.startswith("http"):
                return url
        # Fall back to known CDN map
        normalized = seller.strip().lower()
        if normalized in SELLER_LOGO_MAP:
            return SELLER_LOGO_MAP[normalized]
        for key, logo in SELLER_LOGO_MAP.items():
            if key in normalized:
                return logo
        return None

    # ── HTML helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _extract_seller_html(item: Any) -> str:
        if not hasattr(item, "find"):
            return "N/A"
        img = item.find("img")
        if img:
            alt = (img.get("alt") or "").strip()
            if alt:
                return alt
        name_p = item.find("p", class_=re.compile(r"capitalize"))
        if name_p:
            text = name_p.get_text(strip=True)
            if text:
                return text
        return "N/A"

    @staticmethod
    def _extract_price_html(item: Any) -> Tuple[Optional[float], str]:
        if not hasattr(item, "find"):
            return None, "N/A"
        price_p = item.find("p", class_=re.compile(r"font-bold"))
        if price_p:
            raw = price_p.get_text(strip=True)
            m = re.search(r"[\d,]+(?:\.\d+)?", raw)
            if m:
                try:
                    val = float(m.group(0).replace(",", ""))
                    return val, f"₹{m.group(0)}"
                except ValueError:
                    pass
        text = item.get_text(" ", strip=True)
        m = re.search(r"₹\s*([\d,]+(?:\.\d+)?)", text)
        if m:
            try:
                val = float(m.group(1).replace(",", ""))
                return val, f"₹{m.group(1)}"
            except ValueError:
                return None, f"₹{m.group(1)}"
        return None, "N/A"

    @staticmethod
    def _extract_link_html(item: Any, tracker_url: str) -> Optional[str]:
        if hasattr(item, "name") and item.name == "a" and item.get("href"):
            return urljoin(tracker_url, item["href"])
        if hasattr(item, "find"):
            anchor = item.find("a", href=True)
            if anchor:
                return urljoin(tracker_url, anchor["href"])
        for attr in ("data-url", "data-href", "data-link"):
            val = item.get(attr) if hasattr(item, "get") else None
            if val:
                return urljoin(tracker_url, val)
        onclick = item.get("onclick") if hasattr(item, "get") else None
        if onclick:
            m = re.search(r"https?://[^'\")\s]+", onclick)
            if m:
                return m.group(0)
        return None

    @staticmethod
    def _raw_logo_url(item: Any, tracker_url: str) -> Optional[str]:
        if not hasattr(item, "find"):
            return None
        img = item.find("img")
        if not img:
            return None
        src = img.get("src") or img.get("data-src")
        if not src and img.get("srcset"):
            src = img.get("srcset").split(",")[0].strip().split(" ")[0]
        return src or None

    @staticmethod
    def _to_float(value: Any) -> Optional[float]:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None


class PriceComparisonService:
    def __init__(self, scraper: BaseScraper, logger: logging.Logger) -> None:
        self.scraper = scraper
        self.logger = logger

    def compare(self, url: str, marketplace: Optional[str] = None) -> Dict[str, Any]:
        self.logger.info(
            "Search started",
            extra={"context": {"url": url, "marketplace": marketplace or "auto-detect"}},
        )
        try:
            result = self.scraper.scrape(url=url, marketplace=marketplace)
            self._log_search(
                url=url,
                marketplace=result.marketplace,
                source=result.source,
                detected_price=result.price,
                status="Success",
            )
            self.logger.info(
                "Search succeeded",
                extra={
                    "context": {
                        "url": url,
                        "marketplace": result.marketplace,
                        "price": result.price,
                        "alternatives_count": len(result.alternatives),
                    }
                },
            )
            return {
                "title": result.title,
                "price": result.price,
                "image_url": result.image_url,
                "thumbnail_images": result.thumbnail_images,
                "source": result.source,
                "marketplace": result.marketplace,
                "tracker_url": result.tracker_url,
                "alternatives": result.alternatives,
                "alternatives_count": len(result.alternatives),
                "status": "Success",
                "error": None,
            }
        except ScraperError as exc:
            resolved_marketplace = marketplace or detect_marketplace(url) or "unknown"
            self._log_search(
                url=url,
                marketplace=resolved_marketplace,
                source="buyhatke",
                detected_price=None,
                status="Failed",
                error_message=str(exc),
            )
            self.logger.error(
                "Comparison failed",
                extra={
                    "context": {
                        "url": url,
                        "marketplace": resolved_marketplace,
                        "error": str(exc),
                    }
                },
            )
            raise

    def _log_search(
        self,
        url: str,
        marketplace: str,
        source: str,
        detected_price: Optional[float],
        status: str,
        error_message: Optional[str] = None,
    ) -> None:
        record = SearchHistory(
            url=url,
            marketplace=marketplace,
            source=source,
            detected_price=detected_price,
            status=status,
            error_message=error_message,
        )
        db.session.add(record)
        db.session.commit()
