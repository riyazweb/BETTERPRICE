import pytest

from app import create_app, db
from app.models import SearchHistory
from app.services import (
    BotDetectionError,
    ScrapeResult,
    UpstreamNotFoundError,
    UpstreamTimeoutError,
)


@pytest.fixture()
def app_instance():
    app = create_app("config.TestingConfig")
    with app.app_context():
        db.drop_all()
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app_instance):
    return app_instance.test_client()


# ── Health ─────────────────────────────────────────────────────────────────────

def test_health_endpoint(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


# ── Interface Safety: request validation ───────────────────────────────────────

def test_compare_rejects_invalid_marketplace_url(client):
    payload = {"url": "https://example.com/product/123"}
    response = client.post("/api/v1/compare", json=payload)

    assert response.status_code == 400
    body = response.get_json()
    assert body["error"] == "Validation failed"


def test_compare_rejects_missing_url(client):
    """Request without a URL must return 400 — the field is required."""
    response = client.post("/api/v1/compare", json={})
    assert response.status_code == 400
    assert response.get_json()["error"] == "Validation failed"


def test_compare_rejects_extra_fields(client):
    """Extra fields must be rejected (PriceRequest has extra='forbid')."""
    payload = {"url": "https://www.amazon.in/dp/B0ABCDE123", "unknown_field": "x"}
    response = client.post("/api/v1/compare", json=payload)
    assert response.status_code == 400
    assert response.get_json()["error"] == "Validation failed"


# ── Success path ──────────────────────────────────────────────────────────────

def test_compare_success_returns_valid_contract(client, mocker):
    mocker.patch(
        "app.services.MarketplaceScraper.scrape",
        return_value=ScrapeResult(
            title="Sample Product",
            price=1499.0,
            image_url="https://images.example.com/sample.jpg",
            thumbnail_images=["https://images.example.com/sample.jpg"],
            source="buyhatke",
            marketplace="amazon",
            tracker_url="https://buyhatke.com/amazon-sample-product-price-in-india-1-2",
            alternatives=[
                {
                    "seller": "Flipkart",
                    "price": 1399.0,
                    "price_display": "₹1,399",
                    "link": "https://www.flipkart.com/example",
                    "logo_url": "https://images.example.com/flipkart.png",
                }
            ],
        ),
    )

    payload = {"url": "https://www.amazon.in/dp/B0ABCDE123"}
    response = client.post("/api/v1/compare", json=payload)

    assert response.status_code == 200
    body = response.get_json()
    assert body == {
        "title": "Sample Product",
        "price": 1499.0,
        "image_url": "https://images.example.com/sample.jpg",
        "thumbnail_images": ["https://images.example.com/sample.jpg"],
        "source": "buyhatke",
        "marketplace": "amazon",
        "tracker_url": "https://buyhatke.com/amazon-sample-product-price-in-india-1-2",
        "alternatives_count": 1,
        "alternatives": [
            {
                "seller": "Flipkart",
                "price": 1399.0,
                "price_display": "₹1,399",
                "link": "https://www.flipkart.com/example",
                "logo_url": "https://images.example.com/flipkart.png",
            }
        ],
        "status": "Success",
        "error": None,
    }


def test_compare_timeout_returns_503_and_logs_failure(client, app_instance, mocker):
    mocker.patch(
        "app.services.MarketplaceScraper.scrape",
        side_effect=UpstreamTimeoutError("Upstream request timed out"),
    )

    payload = {"url": "https://www.flipkart.com/product/p/itmdemo?pid=ABCD1234"}
    response = client.post("/api/v1/compare", json=payload)

    assert response.status_code == 503
    body = response.get_json()
    assert body["status"] == "Failed"
    assert body["error"] == "Upstream request timed out"

    with app_instance.app_context():
        rows = SearchHistory.query.all()
        assert len(rows) == 1
        assert rows[0].status == "Failed"


def test_compare_logs_success(client, app_instance, mocker):
    mocker.patch(
        "app.services.MarketplaceScraper.scrape",
        return_value=ScrapeResult(
            title="Another Product",
            price=999.0,
            image_url=None,
            thumbnail_images=[],
            source="buyhatke",
            marketplace="flipkart",
            tracker_url=None,
            alternatives=[],
        ),
    )

    payload = {"url": "https://www.flipkart.com/p/item?pid=XYZ987654"}
    response = client.post("/api/v1/compare", json=payload)

    assert response.status_code == 200

    with app_instance.app_context():
        rows = SearchHistory.query.all()
        assert len(rows) == 1
        assert rows[0].status == "Success"
        assert rows[0].detected_price == 999.0


# ── Upstream failure paths ─────────────────────────────────────────────────────

def test_compare_bot_detection_returns_503(client, mocker):
    """503 from upstream (bot-block) must surface as 503 to the caller."""
    mocker.patch(
        "app.services.MarketplaceScraper.scrape",
        side_effect=BotDetectionError("Upstream blocked request (possible bot detection)"),
    )
    payload = {"url": "https://www.amazon.in/dp/B0ABCDE123"}
    response = client.post("/api/v1/compare", json=payload)

    assert response.status_code == 503
    body = response.get_json()
    assert body["status"] == "Failed"
    assert "bot" in body["error"].lower()


def test_compare_not_found_returns_404(client, mocker):
    """Product not found on upstream must surface as 404."""
    mocker.patch(
        "app.services.MarketplaceScraper.scrape",
        side_effect=UpstreamNotFoundError("Upstream resource not found"),
    )
    payload = {"url": "https://www.amazon.in/dp/B0ABCDE123"}
    response = client.post("/api/v1/compare", json=payload)

    assert response.status_code == 404
    body = response.get_json()
    assert body["status"] == "Failed"


# ── Observability: history endpoint ────────────────────────────────────────────

def test_history_returns_empty_list_initially(client):
    """History endpoint must return an empty list when no searches have been made."""
    response = client.get("/api/v1/history")
    assert response.status_code == 200
    assert response.get_json() == []


def test_history_records_appear_after_search(client, app_instance, mocker):
    """A completed comparison must be visible in the history endpoint."""
    mocker.patch(
        "app.services.MarketplaceScraper.scrape",
        return_value=ScrapeResult(
            title="History Test Product",
            price=500.0,
            image_url=None,
            thumbnail_images=[],
            source="buyhatke",
            marketplace="amazon",
            tracker_url=None,
            alternatives=[],
        ),
    )

    client.post(
        "/api/v1/compare",
        json={"url": "https://www.amazon.in/dp/B0HISTORY1"},
    )

    response = client.get("/api/v1/history")
    assert response.status_code == 200
    records = response.get_json()
    assert len(records) == 1
    assert records[0]["status"] == "Success"
    assert records[0]["detected_price"] == 500.0
    assert "timestamp" in records[0]

