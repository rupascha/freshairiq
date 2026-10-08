"""Definite-assignment check for the coordinator phases (0.26.3.2).

Added after a refactoring step lost the fallback value of ``status`` (read via
``status = ... or status``) without any scenario noticing.
Reports names that are read at a point where they are not bound on every path
(top-level flow of the function body; compound statements bind only 'maybe')."""
import ast, sys, symtable
SCOPES=(ast.ListComp,ast.SetComp,ast.DictComp,ast.GeneratorExp,ast.Lambda,ast.FunctionDef,ast.AsyncFunctionDef)
def loads(node):
    out=[]
    def rec(n):
        if isinstance(n,ast.Name) and isinstance(n.ctx,ast.Load): out.append(n)
        for ch in ast.iter_child_nodes(n):
            if isinstance(ch,SCOPES):
                inner={x.id for x in ast.walk(ch) if isinstance(x,ast.Name) and isinstance(x.ctx,ast.Store)}
                if hasattr(ch,'args'): inner|={a.arg for a in ch.args.args+ch.args.kwonlyargs}
                out.extend(x for x in ast.walk(ch) if isinstance(x,ast.Name) and isinstance(x.ctx,ast.Load) and x.id not in inner)
                continue
            rec(ch)
    rec(node); return out
def definite_binds(st):
    if isinstance(st,(ast.Assign,)): return {x.id for t in st.targets for x in ast.walk(t) if isinstance(x,ast.Name)}
    if isinstance(st,ast.AnnAssign) and st.value is not None: return {x.id for x in ast.walk(st.target) if isinstance(x,ast.Name)}
    if isinstance(st,(ast.FunctionDef,ast.AsyncFunctionDef)): return {st.name}
    if isinstance(st,(ast.Import,ast.ImportFrom)): return {(a.asname or a.name).split('.')[0] for a in st.names}
    if isinstance(st,ast.If) and st.orelse:  # bound in both branches
        return block_binds(st.body) & block_binds(st.orelse)
    if isinstance(st,ast.Try) and not st.finalbody:
        b=block_binds(st.body+st.orelse)
        for h in st.handlers: b&=block_binds(h.body)
        return b
    return set()
def block_binds(stmts):
    b=set()
    for st in stmts: b|=definite_binds(st)
    return b
def check(path, fname):
    src=open(path,encoding='utf-8').read(); t=ast.parse(src)
    fn=[n for n in ast.walk(t) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==fname][0]
    locals_={x.id for x in ast.walk(fn) if isinstance(x,ast.Name) and isinstance(x.ctx,ast.Store)} | {n.name for n in fn.body if isinstance(n,(ast.FunctionDef,))}
    bound={a.arg for a in fn.args.args+fn.args.kwonlyargs}
    findings=set()
    for st in fn.body:
        if isinstance(st,(ast.FunctionDef,ast.AsyncFunctionDef)): bound.add(st.name); continue
        # names this statement binds before reading inside itself (loops/with targets etc.) are approximated:
        inner_binds={x.id for x in ast.walk(st) if isinstance(x,ast.Name) and isinstance(x.ctx,ast.Store)} if isinstance(st,(ast.For,ast.AsyncFor,ast.While,ast.If,ast.With,ast.Try)) else set()
        for n in loads(st):
            if n.id in locals_ and n.id not in bound and n.id not in inner_binds:
                findings.add(n.id)
        bound|=definite_binds(st)
    return findings
