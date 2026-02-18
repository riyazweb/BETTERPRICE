from flask import Blueprint, current_app, jsonify, request
from pydantic import ValidationError

from .models import SearchHistory
from .schemas import PriceRequest, ProductResponse
from .services import (
    BotDetectionError,
    MarketplaceScraper,
    PriceComparisonService,
    ScraperError,
    UnsupportedMarketplaceError,
    UpstreamNotFoundError,
    UpstreamTimeoutError,
)

api_blueprint = Blueprint("api", __name__)


def _build_service() -> PriceComparisonService:
    scraper = MarketplaceScraper(config=current_app.config, logger=current_app.logger)
    return PriceComparisonService(scraper=scraper, logger=current_app.logger)


@api_blueprint.get("/health")
def health() -> tuple:
    return jsonify({"status": "ok"}), 200


@api_blueprint.get("/history")
def get_history() -> tuple:
    records = SearchHistory.query.order_by(SearchHistory.timestamp.desc()).limit(10).all()
    return jsonify([
        {
            "id": r.id,
            "url": r.url,
            "marketplace": r.marketplace,
            "detected_price": r.detected_price,
            "status": r.status,
            "timestamp": r.timestamp.isoformat(),
        }
        for r in records
    ]), 200


@api_blueprint.post("/compare")
def compare_price() -> tuple:
    payload = request.get_json(silent=True) or {}

    try:
        validated_request = PriceRequest.model_validate(payload)
    except ValidationError as exc:
        details = []
        for issue in exc.errors():
            if "ctx" in issue and isinstance(issue["ctx"], dict):
                issue["ctx"] = {key: str(value) for key, value in issue["ctx"].items()}
            details.append(issue)
        return jsonify({"error": "Validation failed", "details": details}), 400

    service = _build_service()
    url = str(validated_request.url)

    try:
        result = service.compare(url=url, marketplace=validated_request.marketplace)
        validated_response = ProductResponse.model_validate(result)
        return jsonify(validated_response.model_dump(mode="json")), 200
    except UnsupportedMarketplaceError as exc:
        response = ProductResponse(
            title="N/A",
            price=None,
            image_url=None,
            source="buyhatke",
            marketplace=validated_request.marketplace or "unknown",
            tracker_url=None,
            alternatives_count=0,
            alternatives=[],
            status="Failed",
            error=str(exc),
        )
        return jsonify(response.model_dump(mode="json")), 400
    except UpstreamNotFoundError as exc:
        response = ProductResponse(
            title="N/A",
            price=None,
            image_url=None,
            source="buyhatke",
            marketplace=validated_request.marketplace or "unknown",
            tracker_url=None,
            alternatives_count=0,
            alternatives=[],
            status="Failed",
            error=str(exc),
        )
        return jsonify(response.model_dump(mode="json")), 404
    except (UpstreamTimeoutError, BotDetectionError) as exc:
        response = ProductResponse(
            title="N/A",
            price=None,
            image_url=None,
            source="buyhatke",
            marketplace=validated_request.marketplace or "unknown",
            tracker_url=None,
            alternatives_count=0,
            alternatives=[],
            status="Failed",
            error=str(exc),
        )
        return jsonify(response.model_dump(mode="json")), 503
    except ScraperError as exc:
        response = ProductResponse(
            title="N/A",
            price=None,
            image_url=None,
            source="buyhatke",
            marketplace=validated_request.marketplace or "unknown",
            tracker_url=None,
            alternatives_count=0,
            alternatives=[],
            status="Failed",
            error=str(exc),
        )
        return jsonify(response.model_dump(mode="json")), 502
