import types
from runtime_identity import signature

def test_runtime_comparison_ignores_storage_identity_and_source_lines():
    a=compile('def value():\n    return "hello"\n','first.py','exec').co_consts[0]
    b=compile('\n\ndef value():\n    return "hello"\n','second.py','exec').co_consts[0]
    assert signature(a)==signature(b)
    c=compile('def value():\n    return "changed"\n','first.py','exec').co_consts[0]
    assert signature(a)!=signature(c)
