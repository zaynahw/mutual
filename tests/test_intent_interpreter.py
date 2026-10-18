"""Guard explicit limits while leaving semantic interpretation with the agent."""
import json
from datetime import date, timedelta
import pytest
from agent.interpret import interpret_message
from agent.local_llm import LocalLLMUnavailable
from backend.models import HangoutIntentCreate


class Model:
    def __init__(self, **update): self.update=update
    def chat(self,*args,**kwargs):
        return json.dumps({**dict(activities=['coffee'],allowed_durations=[30,60],preferred_periods=['morning'],earliest=None,latest=None,clarification=None), **self.update})


def body(message):
    return HangoutIntentCreate(invitee_id='demo-daniella',days=[date.today()+timedelta(days=1)],message=message)


def test_explicit_clock_limit_cannot_be_dropped_by_model():
    result=interpret_message(body('Coffee only before noon'),'America/New_York',date.today(),llm=Model(),fallback_on_error=False)
    assert result.source=='local_agent' and result.interpretation.latest=='12:00'


def test_ambiguous_hard_clock_blocks_sending_even_if_model_ignores_it():
    result=interpret_message(body('Coffee only before 3'),'America/New_York',date.today(),llm=Model(),fallback_on_error=False)
    assert result.interpretation.clarification


def test_failure_labels_fallback_or_raises_when_disabled():
    class Broken:
        def chat(self,*args,**kwargs): raise LocalLLMUnavailable('private failure')
    result=interpret_message(body('Coffee'),'America/New_York',date.today(),llm=Broken(),fallback_on_error=True)
    assert result.source=='demo_fallback'
    with pytest.raises(LocalLLMUnavailable):
        interpret_message(body('Coffee'),'America/New_York',date.today(),llm=Broken(),fallback_on_error=False)


@pytest.mark.parametrize('message', [
    'Something chill, like a walk or food. I prefer earlier in the morning. Make sure its before 10pm tho, strict limit',
    'I prefer morning coffee, but only before 10pm',
    'I prefer morning coffee and before 10pm is a strict limit',
])
def test_soft_period_and_separate_hard_clock_are_independent(message):
    result=interpret_message(body(message),'America/New_York',date.today(),llm=Model(clarification='Is that time a strict limit, or just a preference?'),fallback_on_error=False)
    assert result.interpretation.preferred_periods == ['morning']
    assert result.interpretation.latest == '22:00'
    assert result.interpretation.clarification is None


def test_soft_clock_still_asks_when_exact_soft_times_are_unsupported():
    result=interpret_message(body('I prefer coffee before 10pm'),'America/New_York',date.today(),llm=Model(),fallback_on_error=False)
    assert result.interpretation.clarification
