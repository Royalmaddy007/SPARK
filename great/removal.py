"""Manifest-guided ablation and a manifest-blind structural plausibility check."""
import json, re, subprocess, tempfile
from pathlib import Path
import networkx as nx
from . import config as C, transforms as T, vlog


def strip(rtl, manifest):
    removed, masks = [], 0
    for decoy in manifest.get('decoy_manifest', []):
        signal = decoy['signal']
        # Step 4j emits exactly these three initialized wire declarations.
        base = signal[:-2] if signal.endswith('_m') else signal
        names = [signal, *decoy.get('sinks', []), base + '_v']
        for name in names:
            pattern = r'\bwire\s+(?:\[[^\]]+\]\s*)?' + re.escape(name) + r'\s*=\s*[^;]*;'
            rtl, n = re.subn(pattern, '', rtl)
            if n:
                removed.append(name)
    for m in manifest.get('masked_constants', []):
        w = m['width']
        expression = f"(({T.lit(w, m['masked'])} - {T.lit(w, m['add'])}) ^ {T.lit(w, m['xor'])})"
        rtl, n = re.subn(re.escape(expression), lambda _: T.lit(w, m['masked']), rtl)
        masks += n
    # Rotated constant sites have a final reconstruction assignment. Replace
    # that RHS with the masked literal; leave comparisons and PRSGs intact.
    for site in manifest.get('mask_rotation', {}).get('sites', []):
        before = site['before']
        if before.startswith('(('):
            literals = vlog.sized_literals(before)
            if literals:
                rhs = literals[0]['text']
                pattern = r'(\bassign\s+' + re.escape(site['after']) + r'\s*=)[^;]*;'
                rtl, n = re.subn(pattern, lambda m: m[1] + ' ' + rhs + ';', rtl)
                masks += n
    return rtl, {'removed_signals': removed, 'mask_reconstructions_replaced': masks,
                 'semantics': 'naive masked literal substitution can change functionality; no equivalence claim',
                 'retained': 'FSM encoding, rotating comparison masks and PRSG helpers'}


def plausibility(path, design):
    """Yosys elaboration + NetworkX reachability; no manifests or LLM inputs."""
    if not C.YOSYS:
        return {'status': 'tool_unavailable', 'flag': None}
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        top = vlog.parse_modules(Path(path).read_text())[0].name
        script = td / 'scan.ys'
        out = td / 'scan.json'
        script.write_text('\n'.join([f'read_verilog -sv {p}' for p in [str(path), *C.dep_files(design)]]) +
                          f'\nhierarchy -check -top {top}\nproc\nflatten\nwrite_json {out}\n')
        r = subprocess.run([C.YOSYS, '-q', '-s', str(script)], capture_output=True, text=True, timeout=600)
        if r.returncode:
            return {'status': 'elaboration_error', 'flag': None, 'reason': r.stderr[-1000:]}
        mod = json.loads(out.read_text())['modules'][top]
        graph = nx.DiGraph()
        sinks = set()
        for port in mod['ports'].values():
            if port['direction'] == 'output':
                sinks.update(b for b in port['bits'] if isinstance(b, int))
        for cell_name, cell in mod['cells'].items():
            ins, outs = [], []
            for pin, bits in cell['connections'].items():
                target = outs if cell.get('port_directions', {}).get(pin) == 'output' else ins
                target.extend(b for b in bits if isinstance(b, int))
            # Registers count as observation points, matching the stated cheap detector.
            if re.search(r'dff|latch', cell['type'], re.I):
                sinks.update(ins)
            cell_node = ('cell', cell_name)
            graph.add_edges_from((a, cell_node) for a in ins)
            graph.add_edges_from((cell_node, b) for b in outs)
        live = set(sinks)
        todo = list(sinks)
        while todo:
            node = todo.pop()
            if node in graph:
                for predecessor in graph.predecessors(node):
                    if predecessor not in live:
                        live.add(predecessor)
                        todo.append(predecessor)
        unused = [name for name, net in mod['netnames'].items()
                  if not net.get('hide_name') and net['bits']
                  and any(isinstance(b, int) for b in net['bits'])
                  and not any(b in live for b in net['bits'])
                  and name not in mod['ports']]
        return {'status': 'ok', 'flag': bool(unused), 'unobservable_signals': sorted(unused),
                'method': 'Yosys RTL elaboration + NetworkX fanout reachability; heuristic, possible false positives'}
