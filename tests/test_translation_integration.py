"""Bridge integration tests use fake app bytes only, never a real installation."""
import copy
import contextlib
import io
import hashlib
import importlib.util
import json
import shutil
import subprocess
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from source_paths import LOCALIZATION, ROOT
import translation_integration as bridge
import antigravity_common as common
from test_localization import make_archive

SPEC = importlib.util.spec_from_file_location('bridge_patcher', LOCALIZATION / 'Antigravity-Patcher.py')
PATCHER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PATCHER)


class ShippedProfileTests(unittest.TestCase):
    def setUp(self):
        self.registry = json.loads((ROOT / 'localization_runtime/compatibility.json').read_text(encoding='utf-8'))
        self.candidate = json.loads((ROOT / 'tests/manual/antigravity-2.28.2.candidate.json').read_text(encoding='utf-8'))

    def test_shipped_profile_is_valid_and_explicitly_scoped(self):
        self.assertEqual(self.registry['schemaVersion'], 1)
        self.assertEqual(len(self.registry['profiles']), 1)
        profile = self.registry['profiles'][0]
        bridge._validate_profile(profile)
        self.assertEqual(profile['id'], 'antigravity-2.28.2-win32-x64-navigation')
        self.assertEqual((profile['name'], profile['version']), ('antigravity', '2.28.2'))
        self.assertEqual(profile['windowBinding'], {'kind': bridge.DYNAMIC_BINDING, 'paths': ['/']})
        self.assertEqual(profile['policy']['paths'], ['/'])
        rules = profile['policy']['rules']
        self.assertEqual(len(rules), 4)
        self.assertEqual({tuple(rule['sourceTexts']) for rule in rules},
                         {('New Conversation',), ('Automations',), ('Customizations',), ('Settings',)})
        for rule in rules:
            self.assertEqual(rule['contextKind'], 'navigation')
            self.assertIs(rule['text'], True)
            self.assertNotIn('attributes', rule)
            self.assertTrue(rule['selector'].startswith('#root > '))
        self.assertNotIn('runtimeIntegrity', profile)
        self.assertEqual(profile['review']['providerValidation'], 'controlled-local-response-only')
        self.assertEqual(profile['review']['stageApproval'], 'approved')
        self.assertEqual((profile['review']['platform'], profile['review']['architecture']), ('win32', 'x64'))
        self.assertTrue((ROOT / profile['review']['evidenceDocument']).is_file())

    def test_production_policy_and_fingerprints_equal_the_exercised_lab_candidate(self):
        # Prevent production promotion from silently broadening the independently
        # exercised lab policy or changing its original-application fingerprints.
        profile = copy.deepcopy(self.registry['profiles'][0])
        profile.pop('id')
        profile.pop('review')
        candidate = copy.deepcopy(self.candidate['profile'])
        candidate.pop('id')
        self.assertEqual(profile, candidate)
        self.assertEqual(self.candidate['scope'], 'isolated-lab-only')
        self.assertEqual(self.candidate['acceptanceStatus'], 'pending-runtime-verification')

    def test_shipped_preload_has_scoped_policy_without_controlled_provider_or_miss(self):
        profile = self.registry['profiles'][0]
        generated = PATCHER.build_dom_injection(profile)
        self.assertIn('policy: ' + json.dumps(profile['policy'], ensure_ascii=True), generated)
        self.assertNotIn('processNode(document.body)', generated)
        self.assertNotIn('const observer = new MutationObserver', generated)
        self.assertNotIn("if (text.trim() === 'Automations') return {value: text, matched: false};", generated)
        self.assertNotIn('fixture-not-a-real-key', generated)
        self.assertNotIn('m1-controlled-fixture', generated)
        self.assertNotIn('自动化（测试译文）', generated)


class BridgePackagingTests(unittest.TestCase):
    def setUp(self):
        # Like the existing localization suite, capture human-readable CLI output.
        # These fixture tests check file state, not the host console code page.
        output = contextlib.redirect_stdout(io.StringIO())
        output.__enter__()
        self.addCleanup(output.__exit__, None, None, None)
        self.temp = tempfile.TemporaryDirectory(prefix='dragongirl-fixture-')
        self.addCleanup(self.temp.cleanup)
        self.stage = Path(self.temp.name)
        (self.stage / 'dist').mkdir()
        self.package = {'name': 'fixture-only', 'version': '0.0.0', 'main': 'dist/main.js'}
        (self.stage / 'package.json').write_text(json.dumps(self.package), encoding='utf-8')
        for name in ('main.js', 'preload.js', 'menu.js', 'tray.js', 'ui.js'):
            (self.stage / 'dist' / name).write_text('// isolated ' + name, encoding='utf-8')
        report = bridge.fingerprints(self.stage, ['dist/ui.js'])
        self.profile = dict(report, id='fixture-only', schemaVersion=1, verified=True,
                            preload='dist/preload.js', uiFiles=['dist/ui.js'],
                            trustedUrls=['https://fixture.invalid/ui'],
                            policy={'verified': True, 'rules': [{'selector': '#fixed-settings', 'contextKind': 'settings', 'text': True, 'attributes': ['title']}]})
        self.profile.pop('note')
        self.profile.pop('bridgeVerified')

    def test_shipped_registry_rejects_unrelated_fixture(self):
        self.assertIsNone(bridge.select_profile(self.stage))

    def test_shipped_registry_rejects_same_version_with_different_application_bytes(self):
        # Matching version metadata is insufficient: these are fixture bytes,
        # not the reviewed application or its separately packaged UI service.
        package = dict(self.package, name='antigravity', version='2.28.2')
        (self.stage / 'package.json').write_text(json.dumps(package), encoding='utf-8')
        resources = self.stage / 'resources'
        (resources / 'bin').mkdir(parents=True)
        (resources / 'bin/language_server.exe').write_bytes(b'not the reviewed service')
        before = (self.stage / 'package.json').read_bytes()
        self.assertIsNone(bridge.select_profile(self.stage, resources_root=resources))
        PATCHER._inject(self.stage, resources_root=resources)
        self.assertEqual((self.stage / 'package.json').read_bytes(), before)
        self.assertFalse((self.stage / '.dragongirl').exists())
        self.assertNotIn('dragongirl:v1', (self.stage / 'dist/preload.js').read_text(encoding='utf-8'))

    def test_fingerprint_does_not_mutate_or_authorize(self):
        before = {str(p): p.read_bytes() for p in self.stage.rglob('*') if p.is_file()}
        self.assertFalse(bridge.fingerprints(self.stage)['bridgeVerified'])
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.stage.rglob('*') if p.is_file()})

    def test_exact_profile_and_ui_digest_required(self):
        self.assertEqual(bridge.select_profile(self.stage, [self.profile])['id'], 'fixture-only')
        (self.stage / 'dist/ui.js').write_text('// different version', encoding='utf-8')
        self.assertIsNone(bridge.select_profile(self.stage, [self.profile]))

    def test_traversal_rejected(self):
        with self.assertRaises(ValueError):
            bridge.fingerprints(self.stage, ['../outside'])

    def test_symlink_rejected(self):
        try:
            (self.stage / 'linked').symlink_to(self.stage / 'dist/ui.js')
        except OSError as error:
            if getattr(error, 'winerror', None) == 1314:
                self.skipTest('Windows symlink privilege unavailable')
            raise
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
        self.assertEqual(json.loads((self.stage / 'package.json').read_text(encoding='utf-8'))['main'], 'dist/main.js')
        self.assertFalse((self.stage / '.dragongirl').exists())
        self.assertNotIn('dragongirl:v1', (self.stage / 'dist/preload.js').read_text(encoding='utf-8'))

    def test_reviewed_fixture_packages_runtime_and_private_preload(self):
        with mock.patch.object(PATCHER, 'select_profile', return_value=self.profile):
            PATCHER._inject(self.stage)
        self.assertEqual(json.loads((self.stage / 'package.json').read_text(encoding='utf-8'))['main'], '.dragongirl/bootstrap.cjs')
        self.assertEqual((self.stage / 'dist/main.js').read_text(encoding='utf-8'), '// isolated main.js')
        for name in bridge.RUNTIME_FILES:
            self.assertTrue((self.stage / '.dragongirl' / name).is_file())
        preload = (self.stage / 'dist/preload.js').read_text(encoding='utf-8')
        self.assertIn('dragongirl:v1:translate', preload)
        self.assertNotIn('exposeInMainWorld', preload)
        self.assertIn('value !== text', preload)
        self.assertNotIn('processNode(document.body)', preload)
        self.assertNotIn('const observer = new MutationObserver', preload)

    def dynamic_profile(self):
        self.resources = self.stage / 'fixture-resources'
        (self.resources / 'bin').mkdir(parents=True)
        (self.resources / 'bin/language_server.exe').write_bytes(b'fixture UI service, never executed')
        for name in bridge.BINDING_FILES:
            (self.stage / name).write_text('// fixture binding module', encoding='utf-8')
        (self.stage / 'dist/utils.js').write_text(
            "function createWindow() {\n    const options = {preload: path_1.default.join(__dirname, 'preload.js')};\n    hubWindows.add(win);\n}\n", encoding='utf-8')
        report = bridge.fingerprints(self.stage, sorted(bridge.BINDING_FILES),
                                    resources_root=self.resources,
                                    resource_files=['bin/language_server.exe'])
        profile = copy.deepcopy(self.profile)
        profile.pop('trustedUrls')
        profile.pop('uiFiles')
        profile['files'].update(report['files'])
        profile['resourcesFiles'] = report['resourcesFiles']
        profile['uiResources'] = ['bin/language_server.exe']
        profile['windowBinding'] = {'kind': bridge.DYNAMIC_BINDING, 'paths': ['/onboarding']}
        profile['policy']['paths'] = ['/onboarding']
        profile['policy']['rules'][0]['sourceTexts'] = ['Unknown action', 'Save']
        return profile

    def test_dynamic_profile_requires_explicit_matching_resource_root(self):
        profile = self.dynamic_profile()
        self.assertIsNone(bridge.select_profile(self.stage, [profile]))
        self.assertIsNone(bridge.select_profile(self.stage, [profile], resources_root=self.stage))
        self.assertEqual(bridge.select_profile(self.stage, [profile], resources_root=self.resources), profile)
        (self.resources / 'bin/language_server.exe').write_bytes(b'updated fixture UI')
        self.assertIsNone(bridge.select_profile(self.stage, [profile], resources_root=self.resources))
        (self.resources / 'bin/language_server.exe').unlink()
        self.assertIsNone(bridge.select_profile(self.stage, [profile], resources_root=self.resources))

    def test_dynamic_binding_modules_must_match(self):
        profile = self.dynamic_profile()
        for name in bridge.BINDING_FILES:
            with self.subTest(name=name):
                path = self.stage / name
                original = path.read_bytes()
                path.write_bytes(original + b' changed')
                self.assertIsNone(bridge.select_profile(self.stage, [profile], resources_root=self.resources))
                path.write_bytes(original)

    def test_dynamic_binding_contract_rejects_missing_and_ambiguous_fields(self):
        profile = self.dynamic_profile()
        invalid = []
        for field, value in [('windowBinding', {'kind': 'anything-loopback'}),
                             ('resourcesFiles', {}), ('uiResources', []),
                             ('trustedUrls', ['https://127.0.0.1/'])]:
            invalid.append(dict(profile, **{field: value}))
        missing_module = copy.deepcopy(profile)
        missing_module['files'].pop('dist/utils.js')
        invalid.append(missing_module)
        missing_ui = copy.deepcopy(profile)
        missing_ui['resourcesFiles'] = {'bin/other.exe': '0' * 64}
        invalid.append(missing_ui)
        for candidate in invalid:
            with self.subTest(candidate=candidate):
                with self.assertRaises(ValueError):
                    bridge.select_profile(self.stage, [candidate], resources_root=self.resources)

    def test_dynamic_binding_paths_are_unique_exact_routes(self):
        profile = self.dynamic_profile()
        for paths in [[], '/', ['/onboarding', '/onboarding'], ['https://127.0.0.1/onboarding'],
                      ['/onboarding?x=1'], ['/onboarding#step'], ['/../onboarding'],
                      ['/./onboarding'], ['//onboarding'], ['/a//b'], ['/a/'],
                      ['/%2e%2e/onboarding'], ['/onboarding\\extra'], ['/onboarding:extra'], [None],
                      ['/route' + str(i) for i in range(33)]]:
            with self.subTest(paths=paths):
                candidate = copy.deepcopy(profile)
                candidate['windowBinding']['paths'] = paths
                with self.assertRaises(ValueError):
                    bridge.select_profile(self.stage, [candidate], resources_root=self.resources)
        for paths in [['/'], ['/onboarding'], ['/onboarding', '/settings/account']]:
            with self.subTest(paths=paths):
                candidate = copy.deepcopy(profile)
                candidate['windowBinding']['paths'] = paths
                candidate['policy']['paths'] = paths
                self.assertEqual(bridge.select_profile(self.stage, [candidate], resources_root=self.resources), candidate)
        for binding in [{'kind': bridge.DYNAMIC_BINDING},
                        {'kind': bridge.DYNAMIC_BINDING, 'paths': ['/'], 'wildcard': True}]:
            candidate = dict(profile, windowBinding=binding)
            with self.assertRaises(ValueError):
                bridge.select_profile(self.stage, [candidate], resources_root=self.resources)

    def test_dynamic_policy_paths_match_binding_semantically(self):
        profile = self.dynamic_profile()
        for paths in [None, [], ['/'], ['/onboarding', '/settings'], ['/onboarding?x=1'],
                      ['/onboarding', '/onboarding'], ['/route' + str(i) for i in range(33)]]:
            with self.subTest(paths=paths):
                candidate = copy.deepcopy(profile)
                candidate['policy']['paths'] = paths
                with self.assertRaises(ValueError):
                    bridge.select_profile(self.stage, [candidate], resources_root=self.resources)
        candidate = copy.deepcopy(profile)
        candidate['policy'].pop('paths')
        with self.assertRaises(ValueError):
            bridge.select_profile(self.stage, [candidate], resources_root=self.resources)
        profile['windowBinding']['paths'] = ['/onboarding', '/settings']
        profile['policy']['paths'] = ['/settings', '/onboarding']
        self.assertEqual(bridge.select_profile(self.stage, [profile], resources_root=self.resources), profile)

    def test_dynamic_rules_require_exact_fixed_source_texts(self):
        profile = self.dynamic_profile()
        invalid_sources = [None, [], 'Save', [''], [' Save'], ['Save '], ['Save', 'Save'],
                           ['Hello\nworld'], ['Hello\tworld'], ['你好'], ['123'], ['A' * 161],
                           [None], [{'regex': '.*'}]]
        for sources in invalid_sources:
            with self.subTest(sources=sources):
                candidate = copy.deepcopy(profile)
                candidate['policy']['rules'][0]['sourceTexts'] = sources
                with self.assertRaises(ValueError):
                    bridge.select_profile(self.stage, [candidate], resources_root=self.resources)
        missing = copy.deepcopy(profile)
        missing['policy']['rules'][0].pop('sourceTexts')
        with self.assertRaises(ValueError):
            bridge.select_profile(self.stage, [missing], resources_root=self.resources)
        # These are exact strings; no case folding, interpolation or regex matching.
        profile['policy']['rules'][0]['sourceTexts'] = ['Save', 'save', 'New conversation...']
        self.assertEqual(bridge.select_profile(self.stage, [profile], resources_root=self.resources), profile)

    def test_policy_rule_shape_rejects_ineffective_or_ambiguous_targets(self):
        invalid_rules = [None, {}, {'selector': '#fixed-settings', 'contextKind': []},
                         dict(self.profile['policy']['rules'][0], selector=''),
                         dict(self.profile['policy']['rules'][0], contextKind='user-input'),
                         dict(self.profile['policy']['rules'][0], text=1),
                         dict(self.profile['policy']['rules'][0], text=False, attributes=[]),
                         dict(self.profile['policy']['rules'][0], attributes=['value']),
                         dict(self.profile['policy']['rules'][0], attributes=['title', 'title']),
                         dict(self.profile['policy']['rules'][0], attributes=None)]
        for rule in invalid_rules:
            with self.subTest(rule=rule):
                candidate = copy.deepcopy(self.profile)
                candidate['policy']['rules'] = [rule]
                with self.assertRaises(ValueError):
                    bridge.select_profile(self.stage, [candidate])

    def test_static_policy_keeps_legacy_support_but_validates_optional_limits(self):
        self.assertEqual(bridge.select_profile(self.stage, [self.profile]), self.profile)
        for field, value in [('paths', None), ('paths', ['/ui?x=1']), ('excludeSelectors', None),
                             ('excludeSelectors', [''])]:
            with self.subTest(field=field, value=value):
                candidate = copy.deepcopy(self.profile)
                candidate['policy'][field] = value
                with self.assertRaises(ValueError):
                    bridge.select_profile(self.stage, [candidate])
        candidate = copy.deepcopy(self.profile)
        candidate['policy']['rules'][0]['sourceTexts'] = None
        with self.assertRaises(ValueError):
            bridge.select_profile(self.stage, [candidate])
        candidate['policy']['rules'][0]['sourceTexts'] = ['Save']
        candidate['policy']['paths'] = ['/ui']
        self.assertEqual(bridge.select_profile(self.stage, [candidate]), candidate)

    def test_resources_cannot_escape_or_alias_their_root(self):
        profile = self.dynamic_profile()
        for path in ['../bin/language_server.exe', '/bin/language_server.exe',
                     'C:/outside.exe', 'bin\\language_server.exe',
                     'bin//language_server.exe', 'bin/./language_server.exe', 'bin/file.']:
            with self.subTest(path=path):
                candidate = copy.deepcopy(profile)
                candidate['resourcesFiles'][path] = '0' * 64
                with self.assertRaises(ValueError):
                    bridge.select_profile(self.stage, [candidate], resources_root=self.resources)
                with self.assertRaises(ValueError):
                    bridge.fingerprints(self.stage, resources_root=self.resources, resource_files=[path])

    def test_resource_fingerprint_is_read_only_and_never_authorizes(self):
        profile = self.dynamic_profile()
        before = {str(p): p.read_bytes() for p in self.stage.rglob('*') if p.is_file()}
        report = bridge.fingerprints(self.stage, resources_root=self.resources,
                                    resource_files=['bin/language_server.exe'])
        self.assertFalse(report['bridgeVerified'])
        self.assertEqual(report['resourcesFiles'], profile['resourcesFiles'])
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.stage.rglob('*') if p.is_file()})
        with self.assertRaises(ValueError):
            bridge.fingerprints(self.stage, resource_files=['bin/language_server.exe'])

    def test_resource_links_and_linked_resource_roots_rejected(self):
        self.dynamic_profile()
        try:
            (self.resources / 'bin/linked.exe').symlink_to(self.resources / 'bin/language_server.exe')
            (self.stage / 'linked-resources').symlink_to(self.resources, target_is_directory=True)
        except OSError as error:
            if getattr(error, 'winerror', None) == 1314:
                self.skipTest('Windows symlink privilege unavailable')
            raise
        with self.assertRaises(ValueError):
            bridge.fingerprints(self.stage, resources_root=self.resources, resource_files=['bin/linked.exe'])
        with self.assertRaises(ValueError):
            bridge.fingerprints(self.stage, resources_root=self.stage / 'linked-resources',
                                resource_files=['bin/language_server.exe'])

    def test_inspector_accepts_explicit_resources_and_never_marks_bridge_verified(self):
        profile = self.dynamic_profile()
        spec = importlib.util.spec_from_file_location('bridge_inspector', LOCALIZATION / 'Inspect-Translation-Compatibility.py')
        inspector = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(inspector)
        output = io.StringIO()
        before = {str(p): p.read_bytes() for p in self.stage.rglob('*') if p.is_file()}
        with contextlib.redirect_stdout(output):
            result = inspector.main([str(self.stage), '--resources-dir', str(self.resources),
                                     '--resource-file', 'bin/language_server.exe'])
        report = json.loads(output.getvalue())
        self.assertEqual(result, 0)
        self.assertFalse(report['bridgeVerified'])
        self.assertIsNone(report['matchedProfile'])
        self.assertEqual(report['resourcesFiles'], profile['resourcesFiles'])
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.stage.rglob('*') if p.is_file()})

    def test_dynamic_preparation_hooks_only_hub_and_seals_final_bytes(self):
        profile = self.dynamic_profile()
        with mock.patch.object(PATCHER, 'select_profile', return_value=profile):
            PATCHER._inject(self.stage, resources_root=self.resources)
        installed = json.loads((self.stage / '.dragongirl/profile.json').read_text(encoding='utf-8'))
        self.assertNotIn('runtimeIntegrity', profile)
        self.assertEqual((self.stage / 'dist/utils.js').read_text(encoding='utf-8').count(bridge.HUB_HOOK), 1)
        self.assertIn("registerHubWindow(win, url, path_1.default.join(__dirname, 'preload.js'))",
                      (self.stage / 'dist/utils.js').read_text(encoding='utf-8'))
        expected = set(profile['files']) | {'.dragongirl/' + name for name in bridge.RUNTIME_FILES}
        self.assertEqual(set(installed['runtimeIntegrity']), expected)
        self.assertNotIn('.dragongirl/profile.json', installed['runtimeIntegrity'])
        for relative, digest in installed['runtimeIntegrity'].items():
            self.assertEqual(hashlib.sha256((self.stage / relative).read_bytes()).hexdigest(), digest)
        self.assertNotEqual(installed['runtimeIntegrity']['package.json'], profile['files']['package.json'])
        self.assertNotEqual(installed['runtimeIntegrity']['dist/preload.js'], profile['files']['dist/preload.js'])
        self.assertNotEqual(installed['runtimeIntegrity']['dist/utils.js'], profile['files']['dist/utils.js'])

    def test_dynamic_hook_requires_unique_known_anchor_before_entry_changes(self):
        profile = self.dynamic_profile()
        for content in ['// no anchor', bridge.HUB_PRELOAD + '\n' + bridge.HUB_ANCHOR + '\n' + bridge.HUB_ANCHOR,
                        bridge.HUB_ANCHOR, bridge.HUB_PRELOAD.replace('path_1', 'other_path') + '\n' + bridge.HUB_ANCHOR,
                        bridge.HUB_PRELOAD + '\n' + bridge.HUB_PRELOAD + '\n' + bridge.HUB_ANCHOR]:
            with self.subTest(content=content):
                (self.stage / 'dist/utils.js').write_text(content, encoding='utf-8')
                with self.assertRaises(ValueError):
                    bridge.prepare_bridge(self.stage, profile)
                self.assertEqual(json.loads((self.stage / 'package.json').read_text(encoding='utf-8')), self.package)
                common.remove_tree(self.stage / '.dragongirl', self.stage)

    def test_legacy_dom_generation_unchanged_and_verified_dom_uses_only_safe_observer(self):
        self.assertEqual(PATCHER.build_dom_injection(), PATCHER.DOM_TRANSLATOR_INJECTION)
        reviewed = PATCHER.build_dom_injection(self.profile)
        self.assertNotIn('processNode(document.body)', reviewed)
        self.assertNotIn('const observer = new MutationObserver', reviewed)
        self.assertIn('function translateText', reviewed)
        self.assertIn('__dgTranslator.start()', reviewed)

    @unittest.skipUnless(shutil.which('node'), 'Node required for isolated bootstrap execution')
    def test_packaged_bootstrap_keeps_original_entry_when_electron_unavailable(self):
        (self.stage / 'dist/main.js').write_text('process.stdout.write("ORIGINAL_FIXTURE_LOADED");', encoding='utf-8')
        bridge.prepare_bridge(self.stage, self.profile)
        result = subprocess.run([shutil.which('node'), str(self.stage / '.dragongirl/bootstrap.cjs')],
                                capture_output=True, text=True, check=True, timeout=10)
        self.assertEqual(result.stdout, 'ORIGINAL_FIXTURE_LOADED')
        self.assertEqual(result.stderr, '')

    def test_existing_runtime_path_never_overwritten(self):
        (self.stage / '.dragongirl').mkdir()
        sentinel = self.stage / '.dragongirl/sentinel'
        sentinel.write_text('keep', encoding='utf-8')
        with self.assertRaises(ValueError):
            bridge.prepare_bridge(self.stage, self.profile)
        self.assertEqual(sentinel.read_text(encoding='utf-8'), 'keep')

    def test_full_fixture_patch_repeat_restore_preserves_user_data(self):
        restore_spec = importlib.util.spec_from_file_location('bridge_restore', LOCALIZATION / 'Restore.py')
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
        (user_data / 'config.json').write_text('{"enabled":false}', encoding='utf-8')
        (user_data / 'personal-dictionary.json').write_text('{"sentinel":"保留"}', encoding='utf-8')
        before = {p.name: p.read_bytes() for p in user_data.iterdir()}
        with mock.patch.object(common.sys, 'platform', 'win32'), \
                mock.patch.object(PATCHER, 'stop_application'), \
                mock.patch.object(restore, 'stop_application'), \
                mock.patch.object(PATCHER, 'select_profile', side_effect=lambda stage, **kwargs: bridge.select_profile(stage, [self.profile], **kwargs)):
            PATCHER.apply_patch(installation, no_launch=True)
            PATCHER.apply_patch(installation, no_launch=True)
            self.assertEqual(json.loads((resources / 'app/package.json').read_text(encoding='utf-8'))['main'], '.dragongirl/bootstrap.cjs')
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
        self.assertEqual(json.loads((self.stage / 'package.json').read_text(encoding='utf-8')), self.package)


if __name__ == '__main__':
    unittest.main()
