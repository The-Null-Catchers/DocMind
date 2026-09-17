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


def test_conversation_update_rejects_cross_workspace_document(client):
    auth = register(client, 'context-owner@example.com')
    headers = {'Authorization': f"Bearer {auth['access_token']}"}
    first = _workspace(client, headers, 'First context')
    second = _workspace(client, headers, 'Second context')
    local_document = _upload(client, headers, first['id'], 'local.txt', 'Local source material.')
    foreign_document = _upload(client, headers, second['id'], 'foreign-context.txt', 'Foreign source material.')

    created = client.post('/api/v1/conversations', headers=headers, json={
        'workspace_id': first['id'],
        'title': 'Scoped context',
        'document_ids': [local_document['id']],
    })
    assert created.status_code == 201
    conversation_id = created.json()['id']

    denied = client.patch(
        f'/api/v1/conversations/{conversation_id}',
        headers=headers,
        json={'document_ids': [foreign_document['id']]},
    )
    assert denied.status_code == 400

    listed = client.get(
        '/api/v1/conversations',
        headers=headers,
        params={'workspace_id': first['id']},
    )
    assert listed.status_code == 200
    row = next(item for item in listed.json() if item['id'] == conversation_id)
    assert row['document_ids'] == [local_document['id']]


def test_stream_persists_complete_assistant_and_verified_citations(client):
    auth = register(client, 'stream-owner@example.com')
    headers = {'Authorization': f"Bearer {auth['access_token']}"}
    workspace = _workspace(client, headers, 'Streaming')
    document = _upload(
        client,
        headers,
        workspace['id'],
        'streaming.txt',
        'DocMind streaming answers retain server validated citation metadata.',
    )
    created = client.post('/api/v1/conversations', headers=headers, json={
        'workspace_id': workspace['id'],
        'title': 'Streaming chat',
        'document_ids': [document['id']],
    })
    assert created.status_code == 201
    conversation_id = created.json()['id']

    with client.stream(
        'POST',
        f'/api/v1/conversations/{conversation_id}/messages/stream',
        headers=headers,
        json={
            'message': 'What does the source say about streaming answers?',
            'document_ids': [document['id']],
            'language': 'auto',
        },
    ) as response:
        body = ''.join(response.iter_text())

    assert response.status_code == 200
    assert 'event: token' in body
    assert 'event: citations' in body
    assert 'event: done' in body

    history = client.get(
        f'/api/v1/conversations/{conversation_id}/messages',
        headers=headers,
    )
    assert history.status_code == 200
    messages = history.json()
    assert [message['role'] for message in messages] == ['user', 'assistant']
    assert messages[-1]['status'] == 'complete'
    assert messages[-1]['citations']
    assert messages[-1]['citations'][0]['document_id'] == document['id']
