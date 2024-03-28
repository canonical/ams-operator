#!/usr/bin/env python3

import os
import yaml
import json
import logging

SUPPORTED_ARCHITECTURES = ('arm64', 'amd64')
RUNNER_LABELS = {
    'arm64': ["Ubuntu_ARM64_4C_16G_01"],
    'amd64': ["self-hosted", "linux", "X64", "jammy", "large"]
}

logging.basicConfig(level=logging.INFO)

def main() -> int:
    with open('charmcraft.yaml', 'r') as f:
        charmcraft_cfg = yaml.safe_load(f)
    data = []
    for base_idx, base in enumerate(charmcraft_cfg['bases']):
        for arch in base['architectures']:
            if arch not in SUPPORTED_ARCHITECTURES:
                raise ValueError(f'Base {base_idx} architecture: {arch} is not supported')
            data.append({
                "base_index": base_idx,
                "runner_labels": RUNNER_LABELS[arch],
                "arch": arch
            })
    logging.info(f'bases: {data}')
    with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
        f.write(f"bases={json.dumps(data)}")
    return 0

if __name__ == "__main__":
    SystemExit(main())
