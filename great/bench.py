"""Scan-cut mapped JSON using Liberty FF boundaries, then let Yosys/ABC write BENCH."""
from __future__ import annotations
import json, re, shutil, subprocess
from pathlib import Path
from . import config as C, netlist as N


def convert(mapped_json, destination, port_names=None, identifier_names=None):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    data = N.load_mapped_json(mapped_json)
    top = next(iter(data['modules']))
    mod = data['modules'][top]
    mod['cells'] = {n: c for n, c in mod['cells'].items() if c['type'] != '$scopeinfo'}
    info = N.liberty_pins()
    graph = N.build_graph(str(mapped_json), info)
    ports = {}
    signature = {'input': [], 'output': []}
    def add(name, direction, bits):
        safe = re.sub(r'[^A-Za-z0-9_]', '_', name)
        if safe in ports:
            raise ValueError(f'BENCH port collision: {safe}')
        ports[safe] = {'direction': direction, 'bits': bits}
        signature[direction].extend(f'{safe}[{i}]' for i in range(len(bits)))
    for name, port in mod['ports'].items():
        if port['direction'] == 'inout':
            raise ValueError('inout ports unsupported')
        add((port_names or {}).get(name, name), port['direction'], port['bits'])
    public = {}
    for name, net in sorted(mod['netnames'].items()):
        if not net.get('hide_name'):
            name = (identifier_names or {}).get(name, name)
            for i, bit in enumerate(net['bits']):
                public.setdefault(bit, f'{name}_{i}')
    unresolved = []
    for node in sorted(graph.graph['seq_cells']):
        name = node[len('cell:'):]
        cell = mod['cells'].pop(name)
        if not info.get(cell['type'], {}).get('seq'):
            raise ValueError(f'unsupported sequential cell: {cell["type"]}')
        outputs = [bits for pin, bits in cell['connections'].items()
                   if info[cell['type']]['pins'].get(pin) == 'output']
        qbits = [b for bits in outputs for b in bits]
        label = public.get(qbits[0], '') if qbits else ''
        if not label:
            unresolved.append(name)
            label = 'unresolved_' + name
        for pin, bits in cell['connections'].items():
            direction = info[cell['type']]['pins'].get(pin)
            if direction == 'output':
                add(f'scan_q_{label}_{pin}', 'input', bits)
            elif direction == 'input':
                add(f'scan_d_{label}_{pin}', 'output', bits)
    mod['ports'] = ports
    scan = destination.with_suffix('.scan.json')
    scan.write_text(json.dumps(data))
    blif = destination.with_suffix('.blif')
    script = destination.with_suffix('.ys')
    script.write_text(f'read_liberty -ignore_miss_func {N.ASAP7_LIB}\nread_json {scan}\nhierarchy -top {top}\nflatten\nproc\ntechmap\nopt\nabc -g simple\nwrite_blif {blif}\n')
    abc = shutil.which('yosys-abc') or shutil.which('abc')
    if not C.YOSYS or not abc:
        raise FileNotFoundError('Yosys and ABC required for BENCH conversion')
    logs = []
    for cmd in ([C.YOSYS, '-s', str(script)], [abc, '-c', f'read_blif {blif}; strash; write_bench {destination}']):
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        logs.append(r.stdout + r.stderr)
        if r.returncode:
            destination.with_suffix('.conversion.log').write_text('\n'.join(logs))
            raise RuntimeError(f'BENCH conversion failed: {logs[-1][-1000:]}')
    destination.with_suffix('.conversion.log').write_text('\n'.join(logs))
    if not destination.exists():
        raise RuntimeError('ABC did not write BENCH')
    signature = {k: sorted(v) for k, v in signature.items()}
    return {'signature': signature, 'n_scan_cells': len(graph.graph['seq_cells']), 'unresolved_state_names': unresolved,
            'bench': str(destination)}
