import io
import urllib.request

import pytest

from .conftest import register


def extraction_request(client, schema):
    auth = register(client, "extraction-validation@example.com")
    headers = {"Authorization": f"Bearer {auth['access_token']}"}
    workspace = client.post(
        "/api/v1/workspaces",
        headers=headers,
        json={"name": "Extraction validation", "kind": "personal"},
    ).json()
    return client.post(
        "/api/v1/extract",
        headers=headers,
        json={
            "workspace_id": workspace["id"],
            "document_ids": ["missing-document"],
            "schema_definition": schema,
        },
    )


@pytest.mark.parametrize(
    "schema",
    [
        {"type": "unknown-type"},
        {"type": "object", "properties": {"amount": {"type": "unknown-type"}}},
        {"type": "object", "required": 42},
    ],
)
def test_invalid_extraction_schema_returns_validation_error(client, schema):
    response = extraction_request(client, schema)
    assert response.status_code == 422, response.text
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert error["message"].startswith("Invalid extraction schema:")


@pytest.mark.parametrize("types", [["integer", "number"], ["integer", "string"]])
def test_missing_non_nullable_union_field_returns_validation_error(client, types):
    response = extraction_request(
        client, {"type": "object", "properties": {"amount": {"type": types}}}
    )
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "validation_error"
    assert response.json()["error"]["message"].startswith("Extraction failed schema validation:")


def test_nullable_and_string_defaults_remain_supported(client):
    response = extraction_request(
        client,
        {
            "type": "object",
            "properties": {
                "amount": {"type": ["integer", "null"]},
                "name": {"type": "string"},
            },
        },
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"data": {"amount": None, "name": ""}, "sources": []}


@pytest.mark.parametrize(
    "reference",
    ["http://127.0.0.1/schema.json", "https://schemas.example.test/schema.json", "file:///tmp/schema.json"],
)
def test_external_schema_references_are_rejected_without_io(client, monkeypatch, reference):
    requests = []

    def fetch(request):
        requests.append(request.full_url)
        return io.BytesIO(b'{"type":"object"}')

    monkeypatch.setattr(urllib.request, "urlopen", fetch)
    response = extraction_request(client, {"$ref": reference})
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "validation_error"
    assert requests == []


def test_local_schema_references_remain_supported(client):
    response = extraction_request(
        client,
        {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "$defs": {"record": {"type": "object", "required": ["name"]}},
            "$ref": "#/$defs/record",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"] == {"name": ""}
