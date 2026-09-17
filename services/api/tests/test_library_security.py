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


def test_collection_rejects_cross_workspace_documents(client):
    auth = register(client, 'library-owner@example.com')
    headers = {'Authorization': f"Bearer {auth['access_token']}"}
    first = _workspace(client, headers, 'First library')
    second = _workspace(client, headers, 'Second library')
    foreign = _upload(client, headers, second['id'], 'foreign.txt', 'Foreign document')

    response = client.post('/api/v1/collections', headers=headers, json={
        'workspace_id': first['id'],
        'name': 'Scoped collection',
        'document_ids': [foreign['id']],
    })
    assert response.status_code == 400


def test_library_lists_are_workspace_scoped(client):
    auth = register(client, 'library-list@example.com')
    headers = {'Authorization': f"Bearer {auth['access_token']}"}
    first = _workspace(client, headers, 'First')
    second = _workspace(client, headers, 'Second')

    assert client.post('/api/v1/folders', headers=headers, json={'workspace_id': first['id'], 'name': 'First folder'}).status_code == 201
    assert client.post('/api/v1/folders', headers=headers, json={'workspace_id': second['id'], 'name': 'Second folder'}).status_code == 201
    assert client.post('/api/v1/tags', headers=headers, json={'workspace_id': first['id'], 'name': 'alpha'}).status_code == 201
    assert client.post('/api/v1/tags', headers=headers, json={'workspace_id': second['id'], 'name': 'beta'}).status_code == 201

    folders = client.get('/api/v1/folders', headers=headers, params={'workspace_id': first['id']})
    tags = client.get('/api/v1/tags', headers=headers, params={'workspace_id': first['id']})
    assert folders.status_code == 200
    assert [row['name'] for row in folders.json()] == ['First folder']
    assert tags.status_code == 200
    assert [row['name'] for row in tags.json()] == ['alpha']
