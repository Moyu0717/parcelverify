"""Groq-only configuration; legacy provider settings cannot enable inference."""
import os

DEFAULT_MODEL = 'openai/gpt-oss-20b'
GROQ_ENDPOINT = 'https://api.groq.com/openai/v1/chat/completions'
CONFIG_KEYS = ('AI_PROVIDER','GROQ_API_KEY','GROQ_MODEL','GROQ_WORKSPACE_HOURLY','GROQ_GLOBAL_DAILY')

def load_server_configuration(secrets):
    """Streamlit server secrets override environment; .env is not auto-loaded."""
    for name in CONFIG_KEYS:
        if name in secrets: os.environ[name]=str(secrets[name])

def provider_settings():
    provider=os.getenv('AI_PROVIDER','groq').strip().lower()
    return {'provider':provider,'model':os.getenv('GROQ_MODEL',DEFAULT_MODEL).strip(),
            'configured':bool(os.getenv('GROQ_API_KEY','').strip()),'enabled':provider=='groq'}

def bounded_setting(name, default, maximum):
    try:return max(1,min(maximum,int(os.getenv(name,str(default)))))
    except ValueError:return default
