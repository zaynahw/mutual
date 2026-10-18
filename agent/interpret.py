"""Interpret the requester's message; model output is confirmed before scheduling."""
import json
import re
from datetime import date, timedelta

from agent.config import prefer_local_fallback
from agent.local_llm import ChatMessage, LocalLLM, LocalLLMError
from backend.models import HangoutIntentCreate, IntentInterpretation, IntentInterpretationResult

SYSTEM = '''Convert ONE user's hangout message into the supplied JSON schema.
Selected dates and timezone are authoritative. Do not invent a person or change dates.
Map food/breakfast/lunch/dinner to meal; use only coffee, meal, walk, study, concert.
For a general chill request without named activities, suggest coffee, walk, meal.
Prefer/ideally/if possible are SOFT preferences: preferred_periods, NOT earliest/latest.
Only/must/cannot are HARD limits: earliest/latest in local HH:MM (24-hour clock).
Morning means before 12:00; afternoon 12:00-17:00; evening after 17:00.
Default durations [30,60]; honor explicit supported 30/60/90/120 minute requirements.
If unsupported activity/duration, ambiguous hard limit, conflicting date, multiple
incompatible time rules, or a non-scheduling instruction appears, set clarification
to ONE short question. Never silently drop an explicit requirement.
Extract ONLY activities and periods mentioned; do NOT list every allowed enum value.
When no duration is mentioned, allowed_durations MUST be [30,60].
Example message: "I prefer morning coffee or a walk"
Output: {"activities":["coffee","walk"],"allowed_durations":[30,60],"preferred_periods":["morning"],"earliest":null,"latest":null,"clarification":null}
Example message: "Coffee only before noon"
Output: {"activities":["coffee"],"allowed_durations":[30,60],"preferred_periods":[],"earliest":null,"latest":"12:00","clarification":null}
Example message: "Something chill like food in the evening if possible"
Output: {"activities":["meal"],"allowed_durations":[30,60],"preferred_periods":["evening"],"earliest":null,"latest":null,"clarification":null}
For valid requests clarification is null. Return only the interpretation object.
'''


def deterministic_interpret(body: HangoutIntentCreate, today: date) -> IntentInterpretation:
    """Conservative keyword preview for mock/error mode; unsupported rules ask back."""
    text = body.message.lower()
    activities = [activity for activity, pattern in [
        ('walk',r'\bwalk(?:ing)?\b'), ('meal',r'\b(food|meal|breakfast|lunch|dinner|eat)\b'),
        ('coffee',r'\b(coffee|cafe)\b'), ('study',r'\bstudy(?:ing)?\b'), ('concert',r'\bconcert\b'),
    ] if re.search(pattern,text)] or ['coffee','walk','meal']
    periods = [period for period in ['morning','afternoon','evening'] if period in text]
    earliest = latest = clarification = None
    durations = [30,60]
    duration = re.search(r'\b(\d+)\s*(?:minutes?|mins?)\b',text)
    if duration:
        value = int(duration.group(1))
        if value not in (30,60,90,120):
            clarification = 'Our demo supports 30, 60, 90, or 120 minutes. Which would work?'
        else:
            durations = [value]
    elif 'an hour' in text or 'one hour' in text:
        durations = [60]
    if re.search(r'\b(movie|bowling|hiking|games?|drinks|swim|gym)\b',text):
        clarification = 'Which supported activity would you like: coffee, meal, walk, study, or concert?'
    if 'tomorrow' in text and body.days != [today + timedelta(days=1)] or re.search(r'\btoday\b',text) and body.days != [today]:
        clarification = 'Your message and selected dates differ. Which dates should we use?'
    if re.search(r'\b(mon(?:day)?|tue(?:sday)?|wed(?:nesday)?|thu(?:rsday)?|fri(?:day)?|sat(?:urday)?|sun(?:day)?)\b',text):
        clarification = 'Please select the dates you mean and remove weekday names from the message for this demo.'
    hard_period = re.search(r'\bonly\s+(?:in\s+the\s+)?(morning|afternoon|evening)\b',text)
    if hard_period:
        earliest,latest = {'morning':(None,'12:00'),'afternoon':('12:00','17:00'),'evening':('17:00',None)}[hard_period.group(1)]
    if len(re.findall(r'\b(before|after)\b',text)) > 1:
        clarification = 'Please use one required time limit, or use the advanced manual search.'
    clock = re.search(r'\b(before|after)\s+(noon|\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\b',text)
    if clock:
        value = clock.group(2).replace(' ','')
        # Soft wording belongs to its own clause, not every time rule in the message.
        clause_start = 0
        clause_end = len(text)
        for separator in re.finditer(r'[.!?;]|\b(?:but|though|tho|and)\b', text):
            if separator.end() <= clock.start():
                clause_start = separator.end()
            elif separator.start() >= clock.end():
                clause_end = separator.start()
                break
        clause = text[clause_start:clause_end]
        soft_clock = re.search(r'\b(?:prefer|ideally)\b|if possible', clause)
        strict_clock = re.search(r'\b(?:only|must|strict|require|required)\b', clause)
        if soft_clock and not strict_clock:
            clarification = 'Is that time a strict limit, or just a preference?'
        elif value == 'noon':
            parsed = '12:00'
            if clock.group(1)=='before': latest=parsed
            else: earliest=parsed
        elif ':' not in value and not value.endswith(('am','pm')):
            clarification = 'Please specify AM or PM for the time limit.'
        else:
            match = re.fullmatch(r'(\d{1,2})(?::(\d{2}))?(am|pm)?',value)
            hour,minute,ampm = int(match.group(1)), int(match.group(2) or 0), match.group(3)
            if minute > 59 or ampm and not 1 <= hour <= 12 or not ampm and hour > 23:
                clarification = 'What valid time limit should we use?'
            else:
                if ampm: hour=hour%12+(12 if ampm=='pm' else 0)
                parsed=f'{hour:02d}:{minute:02d}'
                if clock.group(1)=='before': latest=parsed
                else: earliest=parsed
    if re.search(r"\b(can't|cannot|never|except|must|at|between)\b",text) or re.search(r'\bonly\b',text) and not (clock or hard_period):
        clarification = 'Please simplify your required time limit, for example “only before noon.”'
    if earliest and latest and earliest>=latest:
        clarification = 'Those time limits conflict. What time range should we consider?'
    return IntentInterpretation(activities=activities,allowed_durations=durations,preferred_periods=periods,
                                earliest=earliest,latest=latest,clarification=clarification)


def interpret_message(body: HangoutIntentCreate, timezone: str, today: date, *, llm=None, fallback_on_error=None) -> IntentInterpretationResult:
    fallback = prefer_local_fallback() if fallback_on_error is None else fallback_on_error
    try:
        raw = (llm or LocalLLM()).chat([
            ChatMessage(role='system',content=SYSTEM),
            ChatMessage(role='user',content=json.dumps({'selected_days':[day.isoformat() for day in body.days],
                'today':today.isoformat(),'timezone':timezone,'message':body.message})),
        ],format=IntentInterpretation.model_json_schema(),temperature=0,num_predict=450)
        parsed = IntentInterpretation.model_validate_json(raw)
        # The model interprets activities and intent; explicit clock constraints
        # are compiled deterministically so a small model cannot relax "only".
        text = body.message.lower()
        checked = deterministic_interpret(body,today)
        explicit_limit = re.search(r'\b(before|after)\s+(noon|\d)',text) or re.search(r'\bonly\s+(?:in\s+the\s+)?(?:morning|afternoon|evening)\b',text)
        if explicit_limit:
            if checked.clarification:
                parsed = parsed.model_copy(update={'clarification':checked.clarification})
            else:
                clarification = parsed.clarification
                # Resolve this particular question from the explicit clock clause;
                # retain unrelated model questions (activity, dates, etc.).
                if clarification and re.search(r'strict limit.*preference|preference.*strict limit', clarification.lower()):
                    clarification = None
                parsed = parsed.model_copy(update={'earliest':checked.earliest,'latest':checked.latest,'clarification':clarification})
        elif re.search(r'prefer|ideally|if possible',text) and checked.preferred_periods:
            parsed = parsed.model_copy(update={'earliest':None,'latest':None})
        return IntentInterpretationResult(source='local_agent',interpretation=parsed)
    except (LocalLLMError,ValueError):
        if not fallback: raise
        return IntentInterpretationResult(source='demo_fallback',interpretation=deterministic_interpret(body,today))
