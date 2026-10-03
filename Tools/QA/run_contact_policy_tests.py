"""Compile actual engine-independent runtime policy; no Unreal SDK required.

Uses CXX or clang++/g++/c++; run from a C++17 toolchain environment.
Build outputs are temporary, outside the source package.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, help='Write the successful portable check record as JSON')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    compiler = os.environ.get('CXX') or next((shutil.which(x) for x in ('clang++', 'g++', 'c++') if shutil.which(x)), None)
    if not compiler:
        raise SystemExit('C++17 compiler missing. Set CXX to its executable path; Unreal is not needed for this check.')
    public = root/'IntegrationDraft/IronEchoVisuals/Source/IronEchoVisuals/Public'
    source = root/'Tools/QA/contact_policy_tests.cpp'
    with tempfile.TemporaryDirectory(prefix='iron-echo-contact-') as build:
        binary = Path(build)/('contact_policy_tests.exe' if os.name == 'nt' else 'contact_policy_tests')
        if Path(compiler).stem.lower() == 'cl':
            command = [compiler, '/nologo', '/std:c++17', '/EHsc', '/W4', '/WX', '/I'+str(public), str(source), '/Fe:'+str(binary)]
        else:
            command = [compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror', '-pedantic', '-I', str(public), str(source), '-o', str(binary)]
        subprocess.run(command, cwd=build, check=True)
        result = subprocess.run([str(binary)], cwd=build, check=True, capture_output=True, text=True)
        print(result.stdout, end='')
        if args.report:
            files = [public/'IEContactPolicy.h', source, Path(__file__).resolve()]
            record = {
                'checked_at_utc': datetime.now(timezone.utc).isoformat(),
                'status': 'PASS',
                'scope': 'Compiled engine-independent policy used by the runtime sources; 10 behavioral scenarios',
                'compiler': Path(compiler).name,
                'stdout': result.stdout.strip(),
                'source_sha256': {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
                'unreal_module_compiled': False,
                'uht_checked': False,
                'anim_graph_checked': False,
                'windows_runtime_checked': False,
            }
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


if __name__ == '__main__':
    main()
