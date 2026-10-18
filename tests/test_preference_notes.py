"""Owner-only note updates preserve other settings and remain private."""
from backend.repositories import get_user


def test_save_clear_and_preserve_all_other_settings(client):
    headers = {'X-Demo-User-Id':'demo-zaynah'}
    before = client.get('/users/me',headers=headers).json()
    note = 'Prefer a short walk over coffee; earlier in the day if possible.'
    response = client.patch('/users/me/preferences',headers=headers,json={'soft_preference_note':note})
    assert response.status_code == 200
    expected = before | {'preferences':before['preferences'] | {'soft_preference_note':note}}
    assert response.json() == expected
    assert get_user('demo-zaynah').preferences.soft_preference_note == note
    assert client.get('/users/me',headers=headers).json() == expected
    assert client.patch('/users/me/preferences',headers=headers,json={'soft_preference_note':note}).json() == expected
    assert client.patch('/users/me/preferences',headers=headers,json={'soft_preference_note':''}).json()['preferences']['soft_preference_note'] == ''


def test_note_validation_identity_and_public_privacy(client):
    headers = {'X-Demo-User-Id':'demo-zaynah'}
    original_other = get_user('demo-daniella')
    assert client.patch('/users/me/preferences',json={'soft_preference_note':'x'}).status_code == 401
    for body in [{}, {'soft_preference_note':'x'*1001}, {'soft_preference_note':'x','user_id':'demo-daniella'}]:
        assert client.patch('/users/me/preferences',headers=headers,json=body).status_code == 422
    note = 'OWNER_ONLY_TEST_NOTE'
    assert client.patch('/users/me/preferences',headers=headers,json={'soft_preference_note':note}).status_code == 200
    assert get_user('demo-daniella') == original_other
    other_headers = {'X-Demo-User-Id':'demo-daniella'}
    assert note not in client.get('/users',headers=other_headers).text
    schedule = client.get('/users/demo-zaynah/schedule',headers=other_headers,params={'start':'2026-10-18T00:00:00Z','end':'2026-10-19T00:00:00Z'})
    assert schedule.status_code == 200 and note not in schedule.text
    preflight = client.options('/users/me/preferences',headers={'Origin':'http://localhost:5173','Access-Control-Request-Method':'PATCH','Access-Control-Request-Headers':'Content-Type,X-Demo-User-Id'})
    assert preflight.status_code == 200
