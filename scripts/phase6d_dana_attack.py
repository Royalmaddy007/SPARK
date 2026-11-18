#!/usr/bin/env python3
"""DANA-inspired register connectivity clustering (NOT the hal/DANA plugin)."""
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from great import config as C, netlist as N, overhead, util
import networkx as nx


def cluster(graph):
    seq = graph.graph['seq_cells']
    registers = nx.Graph()
    registers.add_nodes_from(seq)
    for source in seq:
        todo, seen = list(graph.successors(source)), set()
        while todo:
            node = todo.pop()
            if node in seen:
                continue
            seen.add(node)
            if node in seq:
                registers.add_edge(source, node)
            elif graph.nodes[node].get('kind') == 'cell':
                todo.extend(graph.successors(node))
    return sorted([len(c) for c in nx.connected_components(registers)], reverse=True)


def analyse(design):
    result = {'design': design, 'method': 'DANA-inspired, not the hal plugin',
              'scoring_library': 'networkx.connected_components',
              'status': 'error', 'cluster_count': None, 'runtime_s': None}
    try:
        mapping = overhead.redacted_mapping(design)
        start = time.monotonic()
        graph = N.build_graph(mapping['mapped_json'])
        sizes = cluster(graph)
        result.update(status='ok', cluster_count=len(sizes), cluster_sizes=sizes,
                      n_registers=len(graph.graph['seq_cells']),
                      runtime_s=time.monotonic()-start,
                      artifact_sha256=overhead.digest(overhead.inputs(design)[0]))
    except (OSError, ValueError, RuntimeError) as exc:
        result['reason'] = str(exc)
    util.write_json(C.phase_dir('6d') / f'{design}.dana.json', result)
    return result


def main():
    ap = util.design_args(__doc__)
    ap.add_argument('--strict', action='store_true', help='exit nonzero for unavailable/failed measurements')
    args = ap.parse_args()
    results = [analyse(p.stem) for p in util.resolve_designs(args)]
    for r in results:
        util.info(str(r))
    return int(args.strict and any(r['status'] != 'ok' for r in results))

if __name__ == '__main__':
    raise SystemExit(main())
