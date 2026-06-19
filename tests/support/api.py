from typing import Any

from httpx import Response


class ApiAssertions:
    @staticmethod
    def assert_status(response: Response, status_code: int) -> Any:
        assert response.status_code == status_code, (
            f"Expected HTTP {status_code}, got {response.status_code}: {response.text}"
        )
        if not response.content:
            return None
        return response.json()

    @staticmethod
    def assert_error(
        response: Response,
        *,
        status_code: int,
        code: str,
    ) -> dict[str, Any]:
        payload = ApiAssertions.assert_status(response, status_code)
        assert payload is not None
        assert payload["error"]["code"] == code
        assert payload["meta"]["request_id"] == response.headers["X-Request-ID"]
        assert payload["meta"]["path"]
        return payload

    @staticmethod
    def assert_validation_error(
        response: Response,
        location: list[str],
    ) -> dict[str, Any]:
        payload = ApiAssertions.assert_error(
            response,
            status_code=422,
            code="VALIDATION_ERROR",
        )
        assert any(item["loc"] == location for item in payload["error"]["details"])
        return payload
