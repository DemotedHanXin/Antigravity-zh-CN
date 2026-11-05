"""M3 credential persistence; isolated keys, no network or application launch."""
import base64
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

from source_paths import ROOT
from credential_protection import CredentialError, WindowsProtector
from translation_config import UserStore, DataError, default_config, JOURNAL_FILE


class FixtureProtector:
    """Explicit in-memory test dependency, never selected by production options."""
    def protect(self, value):
        return base64.b64encode(('fixture:' + value).encode()).decode()

    def unprotect(self, value):
        result = base64.b64decode(value).decode()
        if not result.startswith('fixture:'):
            raise CredentialError('fixture account mismatch')
        return result[8:]


class CredentialTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='m3-credentials-')
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.store = UserStore(self.directory, protector=FixtureProtector())

    def configuration(self):
        value = default_config()
        value['providers']['openai'].update(model='fixture', apiKey='isolated-credential-123')
        value['enabled'] = True
        return value

    def test_legacy_migration_encrypts_and_invalidates_once(self):
        value = self.configuration()
        path = self.directory / 'config.json'
        path.write_text(json.dumps(value), encoding='utf-8')
        current = self.store.read_config()
        self.assertEqual(current['revision'], 1)
        self.assertEqual(current['cacheEpoch'], 1)
        self.assertEqual(current['providers'], value['providers'])
        raw = path.read_text(encoding='utf-8')
        self.assertNotIn('isolated-credential-123', raw)
        self.assertEqual(json.loads(raw)['schemaVersion'], 3)
        self.assertEqual(self.store.read_config(), current)
        self.assertEqual(path.read_text(encoding='utf-8'), raw)

    def test_failure_after_journal_never_records_plaintext_and_recovers(self):
        original = self.store._write
        def fail(name, *args):
            if name == 'config.json':
                raise OSError('fixture failure')
            return original(name, *args)
        with mock.patch.object(self.store, '_write', side_effect=fail):
            with self.assertRaises(OSError):
                self.store.save_config(self.configuration(), 0)
        journal = (self.directory / JOURNAL_FILE).read_text(encoding='utf-8')
        self.assertNotIn('isolated-credential-123', journal)
        self.assertEqual(json.loads(journal)['files']['config.json']['schemaVersion'], 3)
        self.assertEqual(self.store.read_config()['revision'], 1)
        self.assertFalse((self.directory / JOURNAL_FILE).exists())

    def test_unavailable_protection_preserves_original_and_no_journal(self):
        self.store.save_config(default_config())
        before = (self.directory / 'config.json').read_bytes()
        with mock.patch.object(self.store.protector, 'protect', side_effect=CredentialError('private detail')):
            with self.assertRaises(DataError) as raised:
                self.store.save_config(self.configuration(), 1)
        self.assertNotIn('private detail', str(raised.exception))
        self.assertEqual((self.directory / 'config.json').read_bytes(), before)
        self.assertFalse((self.directory / JOURNAL_FILE).exists())

    def test_wrong_account_failure_preserves_encrypted_state(self):
        self.store.save_config(self.configuration())
        before = (self.directory / 'config.json').read_bytes()
        with mock.patch.object(self.store.protector, 'unprotect', side_effect=CredentialError('private detail')):
            with self.assertRaises(DataError):
                self.store.read_config()
        self.assertEqual((self.directory / 'config.json').read_bytes(), before)

    def test_protected_schema_rejects_float_and_noncanonical_base64(self):
        self.store.save_config(self.configuration())
        saved = json.loads((self.directory / 'config.json').read_text())
        for modify in [lambda c: c.update(schemaVersion=3.0),
                       lambda c: c['providers']['openai'].update(apiKeyProtected='ab=c'),
                       lambda c: c['providers']['openai'].update(apiKeyProtected='Zh=='),
                       lambda c: c['providers']['openai'].update(apiKey='plain')]:
            broken = copy.deepcopy(saved)
            modify(broken)
            with self.assertRaises(DataError):
                self.store._open_config(broken, decrypt=False)

    def test_legacy_recovery_journal_is_protected_before_application(self):
        journal = dict(schemaVersion=1, kind='dragongirl-state-transaction', id='a' * 32,
                       files={'config.json': self.configuration()})
        (self.directory / JOURNAL_FILE).write_text(json.dumps(journal), encoding='utf-8')
        original = self.store._write
        def fail(name, *args):
            if name == 'config.json':
                raise OSError('fixture recovery interruption')
            return original(name, *args)
        with mock.patch.object(self.store, '_write', side_effect=fail):
            with self.assertRaises(OSError):
                self.store.read_config()
        self.assertNotIn('isolated-credential-123', (self.directory / JOURNAL_FILE).read_text())
        self.assertEqual(self.store.read_config()['providers']['openai']['apiKey'], 'isolated-credential-123')

    @unittest.skipUnless(os.name == 'nt' and shutil.which('node'), 'Windows DPAPI and Node required')
    def test_native_dpapi_python_node_roundtrip_and_runtime_snapshot_redaction(self):
        self.store = UserStore(self.directory)
        value = self.configuration()
        value['providers']['openai']['apiKey'] = 'isolated-密钥-123'
        saved = self.store.save_config(value)
        script = """const {Store}=require('./src/localization_runtime/storage.cjs');
        const {createService}=require('./src/localization_runtime/main.cjs');
        (async()=>{const store=new Store(process.argv[1]),state=await store.read();
        if(state.config.providers.openai.apiKey!=='isolated-密钥-123')throw Error('roundtrip');
        const service=createService({store});const snapshot=await service.snapshot();service.close();
        if(JSON.stringify(snapshot).includes('isolated-'))throw Error('leak');
        await store.withLock(async()=>{state.config.revision++;await store.commit({'config.json':state.config});});
        process.stdout.write('ok');})().catch(()=>process.exitCode=1);"""
        result = subprocess.run(['node', '-e', script, str(self.directory)], cwd=ROOT,
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, 'ok')
        final = self.store.read_config()
        self.assertEqual(final['revision'], saved['revision'] + 1)
        self.assertEqual(final['providers'], saved['providers'])
        self.assertNotIn('isolated-', (self.directory / 'config.json').read_text())

    @unittest.skipUnless(os.name == 'nt', 'Windows DPAPI required')
    def test_native_dpapi_tamper_is_rejected(self):
        protector = WindowsProtector()
        value = bytearray(base64.b64decode(protector.protect('fixture')))
        value[-1] ^= 1
        with self.assertRaises(CredentialError):
            protector.unprotect(base64.b64encode(value).decode())


if __name__ == '__main__':
    unittest.main()
