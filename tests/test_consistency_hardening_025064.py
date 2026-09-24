from pathlib import Path
import ast
ROOT=Path(__file__).resolve().parents[1]

def test_feedback_uses_central_diagnostics_schema_constant():
    p=ROOT/'custom_components/freshairiq/telemetry.py'
    text=p.read_text(encoding='utf-8')
    assert 'DIAGNOSTICS_SCHEMA_VERSION' in text
    assert '"diagnostics_schema_version": DIAGNOSTICS_SCHEMA_VERSION' in text
    tree=ast.parse(text)
    # Guard against reintroducing a numeric feedback schema literal.
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for key,val in zip(node.keys,node.values):
                if isinstance(key,ast.Constant) and key.value=='diagnostics_schema_version':
                    assert not (isinstance(val,ast.Constant) and isinstance(val.value,int))
