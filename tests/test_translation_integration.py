"""Bridge integration tests use fake app bytes only, never a real installation."""
import copy
import hashlib
import importlib.util
import json
import shutil
import subprocess
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import translation_integration as bridge
import antigravity_common as common
from test_localization import make_archive

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('bridge_patcher', ROOT / 'Antigravity-Patcher.py')
PATCHER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PATCHER)


class BridgePackagingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='dragongirl-fixture-')
        self.addCleanup(self.temp.cleanup)
        self.stage = Path(self.temp.name)
        (self.stage / 'dist').mkdir()
        self.package = {'name': 'fixture-only', 'version': '0.0.0', 'main': 'dist/main.js'}
        (self.stage / 'package.json').write_text(json.dumps(self.package))
        for name in ('main.js', 'preload.js', 'menu.js', 'tray.js', 'ui.js'):
            (self.stage / 'dist' / name).write_text('// isolated ' + name)
        report = bridge.fingerprints(self.stage, ['dist/ui.js'])
        self.profile = dict(report, id='fixture-only', schemaVersion=1, verified=True,
                            preload='dist/preload.js', uiFiles=['dist/ui.js'],
                            trustedUrls=['https://fixture.invalid/ui'],
                            policy={'verified': True, 'rules': [{'selector': '#fixed-settings', 'contextKind': 'settings', 'text': True, 'attributes': ['title']}]})
        self.profile.pop('note')
        self.profile.pop('bridgeVerified')

    def test_shipped_registry_has_no_unverified_real_app_claim(self):
        self.assertIsNone(bridge.select_profile(self.stage))

    def test_fingerprint_does_not_mutate_or_authorize(self):
        before = {str(p): p.read_bytes() for p in self.stage.rglob('*') if p.is_file()}
        self.assertFalse(bridge.fingerprints(self.stage)['bridgeVerified'])
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.stage.rglob('*') if p.is_file()})

    def test_exact_profile_and_ui_digest_required(self):
        self.assertEqual(bridge.select_profile(self.stage, [self.profile])['id'], 'fixture-only')
        (self.stage / 'dist/ui.js').write_text('// different version')
        self.assertIsNone(bridge.select_profile(self.stage, [self.profile]))

    def test_symlink_and_traversal_rejected(self):
        with self.assertRaises(ValueError):
            bridge.fingerprints(self.stage, ['../outside'])
        (self.stage / 'linked').symlink_to(self.stage / 'dist/ui.js')
        with self.assertRaises(ValueError):
            bridge.fingerprints(self.stage, ['linked'])

    def test_unverified_esm_and_missing_ui_profile_rejected(self):
        for field, value in [('verified', False), ('moduleType', 'module'), ('uiFiles', []), ('trustedUrls', ['*'])]:
            with self.subTest(field=field):
                profile = dict(self.profile, **{field: value})
                with self.assertRaises(ValueError):
                    bridge.select_profile(self.stage, [profile])

    def test_ambiguous_profiles_rejected(self):
        with self.assertRaises(ValueError):
            bridge.select_profile(self.stage, [self.profile, self.profile])

    def test_unknown_app_legacy_only_preserves_main(self):
        PATCHER._inject(self.stage)
        self.assertEqual(json.loads((self.stage / 'package.json').read_text())['main'], 'dist/main.js')
        self.assertFalse((self.stage / '.dragongirl').exists())
        self.assertNotIn('dragongirl:v1', (self.stage / 'dist/preload.js').read_text())

    def test_reviewed_fixture_packages_runtime_and_private_preload(self):
        with mock.patch.object(PATCHER, 'select_profile', return_value=self.profile):
            PATCHER._inject(self.stage)
        self.assertEqual(json.loads((self.stage / 'package.json').read_text())['main'], '.dragongirl/bootstrap.cjs')
        self.assertEqual((self.stage / 'dist/main.js').read_text(), '// isolated main.js')
        for name in bridge.RUNTIME_FILES:
            self.assertTrue((self.stage / '.dragongirl' / name).is_file())
        preload = (self.stage / 'dist/preload.js').read_text()
        self.assertIn('dragongirl:v1:translate', preload)
        self.assertNotIn('exposeInMainWorld', preload)
        self.assertIn('value !== text', preload)

    @unittest.skipUnless(shutil.which('node'), 'Node required for isolated bootstrap execution')
    def test_packaged_bootstrap_keeps_original_entry_when_electron_unavailable(self):
        (self.stage / 'dist/main.js').write_text('process.stdout.write("ORIGINAL_FIXTURE_LOADED");')
        bridge.prepare_bridge(self.stage, self.profile)
        result = subprocess.run([shutil.which('node'), str(self.stage / '.dragongirl/bootstrap.cjs')],
                                capture_output=True, text=True, check=True, timeout=10)
        self.assertEqual(result.stdout, 'ORIGINAL_FIXTURE_LOADED')
        self.assertEqual(result.stderr, '')

    def test_existing_runtime_path_never_overwritten(self):
        (self.stage / '.dragongirl').mkdir()
        sentinel = self.stage / '.dragongirl/sentinel'
        sentinel.write_text('keep')
        with self.assertRaises(ValueError):
            bridge.prepare_bridge(self.stage, self.profile)
        self.assertEqual(sentinel.read_text(), 'keep')

    def test_full_fixture_patch_repeat_restore_preserves_user_data(self):
        restore_spec = importlib.util.spec_from_file_location('bridge_restore', ROOT / 'Restore.py')
        restore = importlib.util.module_from_spec(restore_spec)
        restore_spec.loader.exec_module(restore)
        installation = self.stage / 'installation'
        installation.mkdir()
        (installation / 'Antigravity.exe').write_bytes(b'never executed')
        resources = installation / 'resources'
        resources.mkdir()
        archive = resources / 'app.asar'
        files = {p.relative_to(self.stage).as_posix(): p.read_bytes()
                 for p in (self.stage / 'dist').iterdir()}
        files['package.json'] = (self.stage / 'package.json').read_bytes()
        make_archive(archive, files=files)
        user_data = self.stage / 'separate-user-data'
        user_data.mkdir()
        (user_data / 'config.json').write_text('{"enabled":false}')
        (user_data / 'personal-dictionary.json').write_text('{"sentinel":"保留"}')
        before = {p.name: p.read_bytes() for p in user_data.iterdir()}
        with mock.patch.object(common.sys, 'platform', 'win32'), \
                mock.patch.object(PATCHER, 'stop_application'), \
                mock.patch.object(restore, 'stop_application'), \
                mock.patch.object(PATCHER, 'select_profile', side_effect=lambda stage: bridge.select_profile(stage, [self.profile])):
            PATCHER.apply_patch(installation, no_launch=True)
            PATCHER.apply_patch(installation, no_launch=True)
            self.assertEqual(json.loads((resources / 'app/package.json').read_text())['main'], '.dragongirl/bootstrap.cjs')
            self.assertEqual(restore.restore(installation, launch=False), 0)
        self.assertTrue(archive.exists())
        self.assertFalse((resources / 'app').exists())
        self.assertEqual(before, {p.name: p.read_bytes() for p in user_data.iterdir()})

    def test_missing_runtime_never_changes_package_entry(self):
        empty = self.stage / 'no-runtime'
        empty.mkdir()
        with mock.patch.object(bridge, 'resource_root', return_value=empty):
            with self.assertRaises(ValueError):
                bridge.prepare_bridge(self.stage, self.profile)
        self.assertEqual(json.loads((self.stage / 'package.json').read_text()), self.package)


if __name__ == '__main__':
    unittest.main()
