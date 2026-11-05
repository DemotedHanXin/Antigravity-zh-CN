"""Check relocated entry points and resources without an app or network access."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from source_paths import LOCALIZATION, PROXY, ROOT, RUNTIME, SOURCE
import translation_integration as bridge

SPEC = importlib.util.spec_from_file_location('layout_settings', LOCALIZATION / 'Translation-Settings.py')
GUI = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GUI)


class SourceLayoutTests(unittest.TestCase):
    def test_root_launcher_from_unrelated_working_directory(self):
        environment = dict(os.environ, PYTHONIOENCODING='utf-8')
        environment.pop('PYTHONPATH', None)
        with tempfile.TemporaryDirectory(prefix='manager-layout-') as directory:
            for arguments in (['--help'], ['--cli', '--help']):
                with self.subTest(arguments=arguments):
                    result = subprocess.run(
                        [sys.executable, '-B', str(ROOT / 'main.py'), *arguments],
                        cwd=directory, env=environment, capture_output=True, text=True,
                        encoding='utf-8', timeout=15,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn('usage:', result.stdout)
            result = subprocess.run(
                [sys.executable, '-B', str(ROOT / 'main.py'), '--cli',
                 '--data-dir', str(Path(directory) / 'user'), 'config'],
                cwd=directory, env=environment, capture_output=True, text=True,
                encoding='utf-8', timeout=15,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(json.loads(result.stdout)['ok'])

    def test_importing_root_launcher_does_not_start_or_load_manager(self):
        script = """
from pathlib import Path
import runpy
import sys
before = list(sys.path)
namespace = runpy.run_path(sys.argv[1], run_name='launcher_import_test')
assert callable(namespace['main'])
assert sys.path == before
assert not any(name == 'PySide6' or name.startswith('PySide6.') for name in sys.modules)
assert not any(name == 'antigravity_manager' or name.startswith('antigravity_manager.') for name in sys.modules)
"""
        with tempfile.TemporaryDirectory(prefix='manager-import-') as directory:
            result = subprocess.run(
                [sys.executable, '-B', '-c', script, str(ROOT / 'main.py')],
                cwd=directory, capture_output=True, text=True, timeout=15,
            )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_manager_reexports_the_storage_error_class(self):
        from antigravity_manager.service import DataError
        from translation_config import DataError as StorageDataError
        self.assertIs(DataError, StorageDataError)

    def test_checkout_uses_one_root_launcher_and_centralized_documentation(self):
        self.assertEqual({path.name for path in ROOT.glob('*.py')}, {'main.py'})
        self.assertEqual({path.name for path in ROOT.glob('*.md')}, {'README.md'})
        self.assertTrue((SOURCE / 'antigravity_manager' / '__main__.py').is_file())
        self.assertTrue((RUNTIME / 'compatibility.json').is_file())
        for old_directory in ('antigravity_manager', 'localization_runtime'):
            self.assertFalse((ROOT / old_directory).exists(), old_directory)
        for tree in (SOURCE, ROOT / 'tests'):
            self.assertEqual(list(tree.rglob('*.md')), [], str(tree))
        for document in ('CONTRIBUTING.md', 'PROJECT_STATUS.md', 'README_EN.md',
                         'testing/manual.md', 'testing/fixtures.md'):
            self.assertTrue((ROOT / 'docs' / document).is_file(), document)

    def test_cli_help_from_unrelated_working_directory(self):
        scripts = [LOCALIZATION / name for name in (
            'Antigravity-Patcher.py', 'Restore.py', 'Inspect-Translation-Compatibility.py',
        )] + [PROXY / name for name in (
            'Setup-Proxy-Shortcuts.py', 'Cleanup-Proxy-Shortcuts.py',
        )]
        environment = dict(os.environ, PYTHONIOENCODING='utf-8')
        environment.pop('PYTHONPATH', None)
        with tempfile.TemporaryDirectory(prefix='source-layout-') as directory:
            for script in scripts:
                with self.subTest(script=script.name):
                    result = subprocess.run(
                        [sys.executable, '-B', str(script), '--help'], cwd=directory,
                        env=environment, capture_output=True, text=True,
                        encoding='utf-8', timeout=15,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn('usage:', result.stdout)

    def test_source_resources_and_cleanup_from_unrelated_working_directory(self):
        # Importing the GUI and loading Setup must not open a window or run Setup.
        script = """
import json
from pathlib import Path
import runpy
import sys
from unittest import mock
sys.path.insert(0, sys.argv[1])
from translation_integration import resource_root, RUNTIME_FILES
gui = runpy.run_path(str(Path(sys.argv[1]) / 'Translation-Settings.py'))
resources = resource_root()
for name in RUNTIME_FILES + ('dom.js', 'probe.cjs', 'compatibility.json'):
    assert (resources / name).is_file(), name
with mock.patch.object(gui['shutil'], 'which', return_value=sys.executable):
    command = gui['probe_command']()
cleanup = runpy.run_path(str(Path(sys.argv[2]) / 'Cleanup-Proxy-Shortcuts.py'))
assert callable(cleanup['load_setup']().install)
print(json.dumps([str(resources), command[1]]))
"""
        with tempfile.TemporaryDirectory(prefix='source-layout-') as directory:
            result = subprocess.run(
                [sys.executable, '-B', '-c', script, str(LOCALIZATION), str(PROXY)],
                cwd=directory, capture_output=True, text=True, timeout=15,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        resource, probe = json.loads(result.stdout)
        self.assertEqual(Path(resource), RUNTIME)
        self.assertEqual(Path(probe), RUNTIME / 'probe.cjs')

    def test_frozen_resources_and_missing_probe_use_only_bundle(self):
        with tempfile.TemporaryDirectory(prefix='frozen-layout-') as directory:
            bundle = Path(directory)
            resources = bundle / 'localization_runtime'
            resources.mkdir()
            probe = resources / 'probe.cjs'
            probe.write_text('// isolated fixture; never executed', encoding='utf-8')
            with mock.patch.object(bridge.sys, '_MEIPASS', str(bundle), create=True), \
                    mock.patch.object(bridge, '__file__', str(Path(bundle.anchor) / 'translation_integration.py')), \
                    mock.patch.object(GUI.shutil, 'which', return_value='fixture-node'):
                self.assertEqual(bridge.resource_root(), resources)
                self.assertEqual(GUI.probe_command(), ['fixture-node', str(probe), '--confirm-network'])
                probe.unlink()
                with self.assertRaises(GUI.DataError):
                    GUI.probe_command()


if __name__ == '__main__':
    unittest.main()
