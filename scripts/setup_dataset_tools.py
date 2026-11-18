#!/usr/bin/env python3
"""Check the tools required by the native-Verilog OpenCores dataset."""
import shutil


def main():
    missing = []
    for name in ('git', 'svn', 'iverilog', 'vvp', 'yosys', '7z'):
        path = shutil.which(name)
        print(f'{name}: {path or "missing"}')
        if not path: missing.append(name)
    if missing:
        raise SystemExit('Missing dataset tools: ' + ', '.join(missing) + '; run make setup')


if __name__ == '__main__': main()
