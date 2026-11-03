"""Install a reviewed navigation candidate into a stopped M1 lab only."""
import argparse
from contextlib import ExitStack
import importlib.util
import json
from pathlib import Path
from unittest.mock import patch

import m1_lab as lab
from translation_integration import select_profile, _validate_profile

CANDIDATE = Path(__file__).with_name('antigravity-2.28.2.candidate.json')


SYNC_RESULT = 'return { value, matched: value !== text || Object.prototype.hasOwnProperty.call(dictionary, text.trim()) };'


def controlled_dom(source):
    if source.count(SYNC_RESULT) != 1:
        raise ValueError('Controlled preload seam changed; refusing to install')
    return source.replace(SYNC_RESULT,
                          "if (text.trim() === 'Automations') return {value: text, matched: false};\n        " + SYNC_RESULT, 1)


def install(root, reset=False, controlled=False):
    root = lab.lab_root(root)
    target = lab.installation(root)
    if (root / 'launch.lock').exists():
        raise ValueError('Stop the isolated launcher and wait for exit before installing')
    lab.check_tree(target / 'resources')
    candidate = json.loads(lab.regular(CANDIDATE).read_text(encoding='utf-8'))
    if candidate.get('scope') != 'isolated-lab-only' or candidate.get('acceptanceStatus') != 'pending-runtime-verification':
        raise ValueError('Not an isolated acceptance candidate')
    profile = candidate['profile']
    _validate_profile(profile)
    if profile['id'] != 'm1-lab-antigravity-2.28.2-navigation':
        raise ValueError('Unexpected candidate identifier')
    if controlled:
        profile['id'] = 'm1-lab-antigravity-2.28.2-controlled'
    spec = importlib.util.spec_from_file_location('m1_patcher', lab.REPOSITORY / 'src/localization/Antigravity-Patcher.py')
    patcher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(patcher)

    def select(stage, resources_root=None):
        matched = select_profile(stage, profiles=[profile], resources_root=resources_root)
        if matched is None:
            raise ValueError('Candidate fingerprint mismatch; isolated install was not switched')
        return matched

    # Test-only seam; keep controlled experiments independent of the registry. Use the production
    # staging, validation, atomic switching and rollback implementation unchanged.
    override = patch.object(patcher, '_inject', lambda stage, resources_root=None: None) if reset else patch.object(patcher, 'select_profile', select)
    with ExitStack() as stack:
        stack.enter_context(override)
        if controlled and not reset:
            original_builder = patcher.build_dom_injection
            stack.enter_context(patch.object(patcher, 'build_dom_injection',
                                            lambda p: controlled_dom(original_builder(p))))
        patcher.apply_patch(str(target), no_launch=True)
    print('LAB ONLY: pristine app rebuilt from original archive.' if reset else
          'LAB ONLY: test candidate installed; this run still requires manual verification.')
    print('Next: python -B tests/manual/m1_lab.py launch --allow-login --refresh-package --duration 1800' +
          (' --translation-test success' if controlled and not reset else ''))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['install', 'reset'])
    parser.add_argument('--lab', default=str(lab.REPOSITORY / '.m1-lab'))
    parser.add_argument('--controlled', action='store_true', help='Lab only: force Automations to miss the builtin dictionary')
    args = parser.parse_args()
    try:
        install(args.lab, reset=args.command == 'reset', controlled=args.controlled)
    except (OSError, ValueError, RuntimeError) as error:
        parser.exit(2, 'M1 bridge: ' + str(error) + '\n')


if __name__ == '__main__':
    main()
