"""Validate explicit clock ranges independently of advisory model interpretation."""
import re

from backend.models import IntentInterpretation

_CLOCK = r'(?:noon|midnight|\d{1,2}(?::\d{2})?\s*(?:am|pm)?)'
_RANGE = re.compile(rf'\b(?:between\s+({_CLOCK})\s+and|from\s+({_CLOCK})\s+to)\s+({_CLOCK})\b', re.I)


def _clock(value: str) -> str:
    value = value.lower().replace(' ', '')
    if value in ('noon', 'midnight'):
        return '12:00' if value == 'noon' else '00:00'
    match = re.fullmatch(r'(\d{1,2})(?::(\d{2}))?(am|pm)?', value)
    hour, minute, period = int(match[1]), int(match[2] or 0), match[3]
    if minute > 59 or (period and not 1 <= hour <= 12) or (not period and (hour > 23 or ':' not in value)):
        raise ValueError('Specify valid times with AM/PM or a 24-hour clock, such as 7am and 12pm.')
    if period:
        hour = hour % 12 + (12 if period == 'pm' else 0)
    return f'{hour:02d}:{minute:02d}'


def enforce_explicit_range(message: str, parsed: IntentInterpretation) -> IntentInterpretation:
    matches = list(_RANGE.finditer(message))
    if not matches:
        if re.search(r'\bbetween\b', message, re.I):
            return parsed.model_copy(update={'clarification': 'Please specify the time range, for example between 7am and 12pm.'})
        return parsed
    try:
        if len(matches) != 1:
            raise ValueError('Please use one required time range per request.')
        match = matches[0]
        earliest, latest = _clock(match[1] or match[2]), _clock(match[3])
        if earliest >= latest:
            raise ValueError('Use a time range that ends later on the same day.')
        # Multiple required rules need clarification rather than silent relaxation.
        remainder = message[:match.start()] + message[match.end():]
        if re.search(r'\b(before|after|except|only|cannot|never)\b|can.t', remainder, re.I):
            raise ValueError('Please use one required time range per request.')
        if re.search(r'\b(prefer|ideally)\b|if possible', message[max(0, message.rfind('.', 0, match.start()) + 1):match.start()], re.I):
            raise ValueError('Is that time range required or just preferred? Use “between 7am and 12pm” for a requirement.')
    except ValueError as error:
        return parsed.model_copy(update={'clarification': str(error)})
    # Preserve unrelated questions. Mock interpreter cannot handle ranges itself.
    clarification = parsed.clarification
    if clarification and 'simplify your required time limit' in clarification:
        clarification = None
    return parsed.model_copy(update={'earliest': earliest, 'latest': latest, 'clarification': clarification})
