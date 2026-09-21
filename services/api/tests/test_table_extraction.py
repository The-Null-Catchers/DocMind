from .conftest import register


def test_csv_tables_are_preserved_and_authorized(client):
    owner = register(client, "tables-owner@example.com")
    headers = {"Authorization": f"Bearer {owner['access_token']}"}
    workspace = client.post(
        "/api/v1/workspaces",
        headers=headers,
        json={"name": "Tables", "kind": "personal"},
    ).json()

    csv_data = "item,qty,price\nApples,2,3.50\nOranges,4,5.00\n"
    upload = client.post(
        "/api/v1/documents/upload",
        headers=headers,
        data={"workspace_id": workspace["id"]},
        files={"file": ("invoice.csv", csv_data.encode(), "text/csv")},
    )
    assert upload.status_code == 202, upload.text
    document = upload.json()

    tables = client.get(
        f"/api/v1/documents/{document['id']}/tables",
        headers=headers,
    )
    assert tables.status_code == 200, tables.text
    payload = tables.json()
    assert len(payload) == 1
    assert payload[0]["page_number"] == 1
    assert payload[0]["row_count"] == 3
    assert payload[0]["column_count"] == 3
    assert payload[0]["truncated"] is False
    assert payload[0]["rows"] == [
        ["item", "qty", "price"],
        ["Apples", "2", "3.50"],
        ["Oranges", "4", "5.00"],
    ]

    stranger = register(client, "tables-stranger@example.com")
    denied = client.get(
        f"/api/v1/documents/{document['id']}/tables",
        headers={"Authorization": f"Bearer {stranger['access_token']}"},
    )
    assert denied.status_code == 403


def test_table_question_is_grounded_and_authorized(client):
    owner = register(client, "table-ai-owner@example.com")
    headers = {"Authorization": f"Bearer {owner['access_token']}"}
    workspace = client.post(
        "/api/v1/workspaces",
        headers=headers,
        json={"name": "Table AI", "kind": "personal"},
    ).json()
    csv_data = "metric,value\nRevenue,1250\nExpenses,900\n"
    upload = client.post(
        "/api/v1/documents/upload",
        headers=headers,
        data={"workspace_id": workspace["id"]},
        files={"file": ("metrics.csv", csv_data.encode(), "text/csv")},
    )
    assert upload.status_code == 202, upload.text
    document = upload.json()

    response = client.post(
        "/api/v1/ai/table",
        headers=headers,
        json={
            "workspace_id": workspace["id"],
            "document_id": document["id"],
            "page_number": 1,
            "table_index": 1,
            "question": "What revenue is shown?",
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["citation"]["document_id"] == document["id"]
    assert payload["citation"]["page_number"] == 1
    assert payload["citation"]["table_index"] == 1
    assert "Revenue" in payload["citation"]["source_excerpt"]

    missing = client.post(
        "/api/v1/ai/table",
        headers=headers,
        json={
            "workspace_id": workspace["id"],
            "document_id": document["id"],
            "page_number": 1,
            "table_index": 99,
            "question": "What is here?",
        },
    )
    assert missing.status_code == 404

    stranger = register(client, "table-ai-stranger@example.com")
    denied = client.post(
        "/api/v1/ai/table",
        headers={"Authorization": f"Bearer {stranger['access_token']}"},
        json={
            "workspace_id": workspace["id"],
            "document_id": document["id"],
            "page_number": 1,
            "table_index": 0,
            "question": "What revenue is shown?",
        },
    )
    assert denied.status_code == 403
