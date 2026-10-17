import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from backend.main import app
from backend.models import Interval, User, SocialWindow, BusyInterval, HangoutRequest, Proposal
from backend.services.scheduling import intersect_availability

def iv(a,b):
    return Interval(start=f"2026-10-18T{a}:00Z",end=f"2026-10-18T{b}:00Z")

def test_health():
    response=TestClient(app).get('/health')
    assert response.status_code == 200
    assert response.json() == {"status":"ok"}

def test_intersection_and_both_busy_sets():
    result=intersect_availability([iv('10:00','12:00'),iv('11:00','14:00')],[iv('11:00','15:00')],[iv('11:30','12:00')],[iv('13:00','13:30')],iv('10:00','16:00'),30)
    assert [(v.start,v.end) for v in result] == [(v.start,v.end) for v in [iv('11:00','11:30'),iv('12:00','13:00'),iv('13:30','14:00')]]

def test_empty_touching_fully_busy():
    s=iv('10:00','12:00')
    assert intersect_availability([], [s], [], [], s, 30) == []
    assert intersect_availability([s],[iv('12:00','13:00')],[],[],s,30)==[]
    assert intersect_availability([s],[s],[s],[],s,30)==[]

def test_offsets_clipping_duration():
    window=Interval(start='2026-10-18T06:00:00-04:00',end='2026-10-18T08:00:00-04:00')
    s=iv('10:30','11:00')
    result=intersect_availability([window],[window],[iv('10:00','10:30')],[],s,30)
    assert [(v.start,v.end) for v in result] == [(s.start,s.end)]
    assert intersect_availability([window],[window],[],[],s,31)==[]
    with pytest.raises(ValueError):
        intersect_availability([],[],[],[],s,0)

@pytest.mark.parametrize('start,end',[('2026-10-18T10:00:00','2026-10-18T11:00:00'),('2026-10-18T11:00:00Z','2026-10-18T10:00:00Z')])
def test_invalid_intervals(start,end):
    with pytest.raises(ValidationError):
        Interval(start=start,end=end)

def test_examples():
    data=json.loads(Path('contracts/examples.json').read_text())
    for key,model in [('users',User),('social_windows',SocialWindow),('busy_intervals',BusyInterval)]:
        for value in data[key]: model.model_validate(value)
    HangoutRequest.model_validate(data['request'])
    Proposal.model_validate(data['proposal'])
