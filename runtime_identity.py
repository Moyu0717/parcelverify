"""Compare loaded Python functions with source without executing source or reloading state."""
import inspect
import sys
import types
from pathlib import Path

ROOT=Path(__file__).resolve().parent

def signature(code):
    constants=tuple(signature(value) if isinstance(value,types.CodeType) else value for value in code.co_consts)
    return (code.co_code,constants,code.co_names,code.co_varnames,code.co_freevars,code.co_cellvars,code.co_argcount,code.co_posonlyargcount,code.co_kwonlyargcount,code.co_flags)

def loaded_source_status():
    stale=[]
    for name,module in list(sys.modules.items()):
        if name not in ('release_info','workspace','seed','db','contracts','demo_fixtures') and not name.startswith(('agent.','services.','ui.')):continue
        filename=getattr(module,'__file__',None)
        if not filename:continue
        path=Path(filename)
        if ROOT not in path.parents or path.suffix!='.py':continue
        try:
            expected=compile(path.read_text(encoding='utf-8-sig'),str(path),'exec')
            for code in expected.co_consts:
                if not isinstance(code,types.CodeType) or code.co_name.startswith('<'):continue
                value=getattr(module,code.co_name,None)
                if isinstance(value,type):continue
                value=inspect.unwrap(value) if value else None
                actual=getattr(value,'__code__',None)
                if actual is None or signature(actual)!=signature(code):
                    stale.append(name);break
        except (OSError,SyntaxError,ValueError):stale.append(name)
    return sorted(set(stale))
