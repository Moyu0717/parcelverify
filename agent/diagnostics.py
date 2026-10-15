"""Safe provider error excerpts, never response bodies or reflected evidence."""
import re
from datetime import datetime,timezone,timedelta
from email.utils import parsedate_to_datetime

SAFE_CODES={'json_validate_failed','tool_use_failed','model_not_found','model_decommissioned','model_permission_blocked','invalid_api_key','rate_limit_exceeded','context_length_exceeded','invalid_request_error'}
SAFE_TYPES={'invalid_request_error','authentication_error','permission_error','rate_limit_error','server_error','tokens','requests'}
SAFE_FIELDS={'messages','response_format','json_object','json_schema','reasoning_effort','reasoning_format','include_reasoning','max_completion_tokens','model','tools','tool_choice','stream','temperature','low','medium','high','raw','parsed','hidden','json'}

def safe_provider_message(message):
    """Retain recognized API wording; remove values that could echo user records.

    Unknown prose is withheld rather than logging an arbitrary reflected prompt.
    This is an excerpt, not a claim about the cause of an older HTTP-only run.
    """
    if not isinstance(message,str):return None
    patterns=[
        r'Failed to generate (?:JSON|a valid JSON|tool calls?)[^.]*\.',
        r'Please adjust your prompt\.',
        r'See [\x27\"]?failed_generation[\x27\"]? for more details\.',
        r'(?:maximum|context|token|rate) limit (?:reached|exceeded)',
    ]
    excerpts=[]
    for pattern in patterns:
        for match in re.finditer(pattern,message,re.I):
            part=match.group(0)
            # Only the fixed, non-reflective part of the first pattern is safe.
            part=re.sub(r'(Failed to generate (?:JSON|a valid JSON|tool calls?)).*',r'\1.',part,flags=re.I)
            excerpts.append(part)
    # API parameter errors: quoted unknown values and everything outside a small
    # vocabulary are removed. Never store failed_generation or nested objects.
    if not excerpts and any(field in message for field in SAFE_FIELDS):
        vocabulary=SAFE_FIELDS|set('must contain the word in some form to use of type is not supported with for this required invalid parameter value cannot be used together mutually exclusive property schema missing an array object expected unsupported allowed only are a valid json please check request format does support'.split())
        words=re.findall(r'[A-Za-z_]+|[.,:;()]',message[:600])
        excerpts=[' '.join(w if w.lower() in vocabulary or w in '.,:;()' else '[redacted]' for w in words)]
    return ' '.join(excerpts)[:500] if excerpts else '[Provider message withheld: unrecognized format]'

def provider_metadata(response):
    result={'http_status':response.status_code}
    request_id=response.headers.get('x-request-id','')
    if re.fullmatch(r'req_[A-Za-z0-9_-]{1,100}',request_id):result['provider_request_id']=request_id
    try:
        error=response.json().get('error',{})
        code=error.get('code')
        if code in SAFE_CODES:result['provider_code']=code
        kind=error.get('type')
        if kind in SAFE_TYPES:result['provider_type']=kind
        if error.get('message'):result['provider_message']=safe_provider_message(error['message'])
    except (ValueError,AttributeError,TypeError):pass
    retry=response.headers.get('retry-after','')
    try:
        seconds=float(retry)
    except ValueError:
        try:seconds=(parsedate_to_datetime(retry)-datetime.now(timezone.utc)).total_seconds()
        except (ValueError,TypeError,OverflowError):seconds=-1
    if 0<=seconds<=86400:
        result['retry_at']=(datetime.now(timezone.utc)+timedelta(seconds=seconds)).isoformat()
    return result
