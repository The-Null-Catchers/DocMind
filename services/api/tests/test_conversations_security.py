from .conftest import register


def _workspace(client, headers, name):
    response = client.post('/api/v1/workspaces', headers=headers, json={'name': name, 'kind': 'personal'})
    assert response.status_code == 201
    return response.json()


def _upload(client, headers, workspace_id, name, text):
    response = client.post(
        '/api/v1/documents/upload',
        headers=headers,
        data={'workspace_id': workspace_id},
        files={'file': (name, text.encode(), 'text/plain')},
    )
    assert response.status_code == 202, response.text
    return response.json()


def test_conversation_rejects_cross_workspace_document(client):
    auth = register(client, 'conversation-owner@example.com')
    headers = {'Authorization': f"Bearer {auth['access_token']}"}
    first = _workspace(client, headers, 'First')
    second = _workspace(client, headers, 'Second')
    foreign_document = _upload(client, headers, second['id'], 'foreign.txt', 'This belongs to the second workspace.')

    response = client.post('/api/v1/conversations', headers=headers, json={
        'workspace_id': first['id'],
        'title': 'Scoped chat',
        'document_ids': [foreign_document['id']],
    })
    assert response.status_code == 400


def test_conversation_history_is_owner_scoped(client):
    owner = register(client, 'history-owner@example.com')
    owner_headers = {'Authorization': f"Bearer {owner['access_token']}"}
    workspace = _workspace(client, owner_headers, 'History')
    document = _upload(client, owner_headers, workspace['id'], 'facts.txt', 'DocMind stores citation-grounded answers.')
    created = client.post('/api/v1/conversations', headers=owner_headers, json={
        'workspace_id': workspace['id'],
        'title': 'Facts',
        'document_ids': [document['id']],
    })
    assert created.status_code == 201
    conversation_id = created.json()['id']

    stranger = register(client, 'history-stranger@example.com')
    stranger_headers = {'Authorization': f"Bearer {stranger['access_token']}"}
    denied = client.get(f'/api/v1/conversations/{conversation_id}/messages', headers=stranger_headers)
    assert denied.status_code == 404

    history = client.get(f'/api/v1/conversations/{conversation_id}/messages', headers=owner_headers)
    assert history.status_code == 200
    assert history.json() == []
