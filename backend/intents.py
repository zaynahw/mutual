"""Owner-only intent drafts. Raw request text never enters shared request JSON."""
from backend.database import connect
from backend.models import HangoutIntentDraft


def save_intent(draft: HangoutIntentDraft) -> None:
    with connect() as connection:
        connection.execute('INSERT INTO hangout_intents (id, owner_id, data) VALUES (?, ?, ?)',
                           (draft.id,draft.owner_id,draft.model_dump_json()))


def get_intent(intent_id: str, owner_id: str) -> HangoutIntentDraft | None:
    with connect() as connection:
        row = connection.execute('SELECT data, request_id FROM hangout_intents WHERE id = ? AND owner_id = ?', (intent_id,owner_id)).fetchone()
    if row is None: return None
    return HangoutIntentDraft.model_validate_json(row['data']).model_copy(update={'request_id':row['request_id']})


def mark_sent(intent_id: str, owner_id: str, request_id: str) -> None:
    with connect() as connection:
        connection.execute('UPDATE hangout_intents SET request_id = ? WHERE id = ? AND owner_id = ?', (request_id,intent_id,owner_id))


def request_intent(request_id: str, owner_id: str) -> HangoutIntentDraft | None:
    with connect() as connection:
        row = connection.execute('SELECT data FROM hangout_intents WHERE request_id = ? AND owner_id = ?', (request_id,owner_id)).fetchone()
    return HangoutIntentDraft.model_validate_json(row['data']) if row else None
