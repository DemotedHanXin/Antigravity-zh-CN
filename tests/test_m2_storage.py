"""Schema2 migration and cross-language transaction tests use isolated fixtures only."""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import unittest
from unittest import mock

from source_paths import ROOT
import translation_config as config

NOW = 1700000000000


class M2StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='m2-storage-')
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name) / 'user'
        self.store = config.UserStore(self.directory, lock_timeout=0.1, clock=lambda: NOW)

    def seed(self, legacy=False):
        self.directory.mkdir()
        current = config.default_config()
        current.update(enabled=True, revision=4)
        current['providers']['openai'].update(model='fixture', apiKey='fixture-key')
        dictionary = config.default_dictionary()
        if legacy:
            current.update(schemaVersion=1, autoSave=True, cacheEpoch=8)
            dictionary.update(schemaVersion=1, revision=5)
            dictionary['entries'] = {
                'Manual': dict(translation='人工', source='manual', updatedAt='old', context='ui'),
                'AI': dict(translation='历史', source='ai', updatedAt='old-ai', context='ui')}
            dictionary['tombstones'] = {'Deleted': 3}
        for name, value in [('config.json', current), ('personal-dictionary.json', dictionary)]:
            (self.directory / name).write_text(json.dumps(value), encoding='utf-8')
        return current, dictionary

    def candidate(self, source='Label', translation='候选', created_at=NOW):
        data = config.default_candidates()
        data['revision'] = 1
        data['entries'][source] = dict(translation=translation, createdAt=created_at,
            expiresAt=created_at + config.CANDIDATE_TTL_MS, context='ui')
        (self.directory / 'pending-translations').mkdir(exist_ok=True)
        (self.directory / config.CANDIDATES_FILE).write_text(json.dumps(data), encoding='utf-8')
        return data

    def node(self, body, payload=None):
        if not shutil.which('node'):
            self.skipTest('Node required for cross-language storage validation')
        module = json.dumps(str(ROOT / 'localization_runtime/storage.cjs'))
        script = 'const S=require(' + module + ');const input=JSON.parse(process.argv[2]);' + \
            'const store=new S.Store(process.argv[1],{clock:()=>input.now});' + \
            '(async()=>{' + body + '})().catch(error=>{process.stderr.write(error.code||error.message);process.exitCode=1;});'
        result = subprocess.run(['node', '-e', script, str(self.directory), json.dumps(payload or {'now': NOW})],
                                capture_output=True, text=True, encoding='utf-8', check=True, timeout=15)
        return json.loads(result.stdout) if result.stdout else None

    def save_node(self, source='Label', translation='候选', guard=None, now=NOW):
        return self.node("const s=await store.read(input.now);const g=input.guard||{configRevision:s.config.revision,dictionaryRevision:s.dictionary.revision,epochs:{[input.source]:s.candidates.epochs[input.source]||0}};process.stdout.write(JSON.stringify(await store.saveCandidates([{source:input.source,translation:input.translation}],g,input.now)));",
                         dict(now=now, source=source, translation=translation, guard=guard))

    def test_defaults_do_not_create_user_data_and_v2_disallows_direct_ai_autosave(self):
        state = self.store.read_state()
        self.assertEqual([state[key]['schemaVersion'] for key in ('config', 'dictionary', 'candidates')], [2, 2, 2])
        self.assertFalse(self.directory.exists())
        with self.assertRaises(config.DataError):
            config.validate_config(dict(state['config'], autoSave=True))
        with self.assertRaises(config.DataError):
            self.store.set_entry('Label', 'AI', 0, 'ai')

    def test_python_migration_preserves_legacy_values_and_node_reads_same_state(self):
        original_config, original_dictionary = self.seed(legacy=True)
        state = self.store.read_state()
        self.assertEqual(state['config']['revision'], 5)
        self.assertEqual(state['config']['cacheEpoch'], 9)
        self.assertFalse(state['config']['autoSave'])
        self.assertEqual(state['config']['providers'], original_config['providers'])
        self.assertEqual(state['dictionary']['entries']['Manual'], original_dictionary['entries']['Manual'])
        self.assertEqual(state['dictionary']['entries']['AI'], dict(original_dictionary['entries']['AI'], source='legacy-ai'))
        self.assertEqual(state['dictionary']['tombstones'], {'Deleted': 3})
        self.assertEqual(state['candidates']['entries'], {})
        self.assertEqual(self.node('process.stdout.write(JSON.stringify(await store.read(input.now)));'), state)
        with self.assertRaises(config.DataError):
            config.validate_config(state['config'], version=1)
        with self.assertRaises(config.DataError):
            config.validate_dictionary(state['dictionary'], version=1)

    def test_node_migration_and_candidates_are_visible_to_python_with_exact_expiry(self):
        self.seed(legacy=True)
        saved = self.save_node()['saved'][0]
        self.assertEqual(saved['createdAt'], NOW)
        self.assertEqual(saved['expiresAt'], NOW + config.CANDIDATE_TTL_MS)
        before = self.store.read_state(NOW + config.CANDIDATE_TTL_MS - 1)
        self.assertEqual(before['dictionary']['entries']['AI']['source'], 'legacy-ai')
        self.assertIn('Label', before['candidates']['entries'])
        expired = self.store.read_state(NOW + config.CANDIDATE_TTL_MS)
        self.assertNotIn('Label', expired['candidates']['entries'])
        self.assertEqual(expired['candidates']['epochs']['Label'], 1)
        self.assertIn('AI', expired['dictionary']['entries'])

    def test_reject_unblock_and_manual_edit_invalidate_old_node_results(self):
        self.seed()
        old_guard = dict(configRevision=4, dictionaryRevision=0, epochs={'Label': 0})
        rejected = self.store.reject_candidate('Label', 0)
        self.assertEqual(rejected['candidates']['rejected']['Label']['rejectedAt'], NOW)
        self.assertEqual(self.save_node(guard=old_guard)['status'], 'stale')
        unblocked = self.store.unblock('Label', 1)
        self.assertEqual(unblocked['candidates']['epochs']['Label'], 2)
        self.assertEqual(self.save_node(guard=old_guard)['status'], 'stale')
        self.assertEqual(self.save_node()['status'], 'ok')
        self.store.set_entry('Label', '人工覆盖', 0)
        state = self.store.read_state()
        self.assertEqual(state['dictionary']['entries']['Label']['source'], 'manual')
        self.assertNotIn('Label', state['candidates']['entries'])
        self.assertEqual(state['candidates']['epochs']['Label'], 3)
        self.assertEqual(self.save_node(guard=old_guard)['status'], 'stale')

    def test_accept_is_atomic_and_edited_translation_becomes_reviewed_dictionary_entry(self):
        self.seed()
        self.candidate()
        state = self.store.accept_candidate('Label', 1, '编辑后采纳')
        self.assertEqual(state['dictionary']['entries']['Label']['translation'], '编辑后采纳')
        self.assertEqual(state['dictionary']['entries']['Label']['source'], 'accepted')
        self.assertEqual(state['dictionary']['revision'], 1)
        self.assertNotIn('Label', state['candidates']['entries'])
        self.assertEqual(state['candidates']['epochs']['Label'], 1)
        self.assertFalse((self.directory / config.JOURNAL_FILE).exists())

    def test_accept_at_exact_expiry_fails_and_rejection_does_not_expire(self):
        self.seed()
        self.candidate()
        with self.assertRaises(config.ConflictError):
            self.store.accept_candidate('Label', 1, now_ms=NOW + config.CANDIDATE_TTL_MS)
        state = self.store.read_state(NOW + config.CANDIDATE_TTL_MS)
        self.assertEqual(state['dictionary']['entries'], {})
        self.assertEqual(state['candidates']['entries'], {})
        self.store.reject_candidate('Label', state['candidates']['revision'])
        self.assertIn('Label', self.store.read_state(NOW + 100 * config.CANDIDATE_TTL_MS)['candidates']['rejected'])

    def test_accept_rechecks_live_clock_after_waiting_for_shared_lock(self):
        self.seed()
        self.candidate()
        lock = self.directory / '.translation.lock'
        lock.mkdir()
        expiry = NOW + config.CANDIDATE_TTL_MS
        current = [expiry - 1]
        clock_read = threading.Event()
        def clock():
            clock_read.set()
            return current[0]
        waiting = config.UserStore(self.directory, lock_timeout=3, clock=clock)
        outcomes = []
        def accept():
            try:
                outcomes.append(waiting.accept_candidate('Label', 1))
            except Exception as error:
                outcomes.append(error)
        worker = threading.Thread(target=accept)
        worker.start()
        self.assertTrue(clock_read.wait(2))
        current[0] = expiry
        lock.rmdir()
        worker.join(4)
        self.assertFalse(worker.is_alive())
        self.assertIsInstance(outcomes[0], config.ConflictError)
        self.assertEqual(waiting.read_state()['dictionary']['entries'], {})

    def test_extreme_timestamps_fail_before_datetime_conversion_or_storage_write(self):
        self.seed()
        self.candidate()
        for now in (True, -1, 2**53 - 1, config.MAX_TIMESTAMP_MS):
            with self.assertRaises(config.DataError):
                self.store.accept_candidate('Label', 1, now_ms=now)
        item = config.default_candidates()
        item['entries']['Label'] = dict(translation='候选', createdAt=2**53 - 1 - config.CANDIDATE_TTL_MS,
                                      expiresAt=2**53 - 1, context='ui')
        with self.assertRaises(config.DataError):
            config.validate_candidates(item)
        self.assertEqual(self.store.read_candidates()['revision'], 1)

    def test_accept_rechecks_live_clock_after_state_read_crosses_deadline(self):
        self.seed()
        self.candidate()
        expiry = NOW + config.CANDIDATE_TTL_MS
        current = [expiry - 1]
        store = config.UserStore(self.directory, clock=lambda: current[0])
        original = store._read_state_locked
        def delayed_read(now):
            state = original(now)
            current[0] = expiry
            return state
        with mock.patch.object(store, '_read_state_locked', side_effect=delayed_read):
            with self.assertRaises(config.ConflictError):
                store.accept_candidate('Label', 1)
        self.assertEqual(store.read_state()['dictionary']['entries'], {})

    def test_capacity_tracks_union_so_expiry_cannot_overflow_source_epochs(self):
        self.seed()
        candidates = config.default_candidates()
        candidates['epochs'] = {f'Old {index}': 1 for index in range(9999)}
        candidates['entries']['Label'] = dict(translation='候选', createdAt=NOW,
            expiresAt=NOW + config.CANDIDATE_TTL_MS, context='ui')
        path = self.directory / config.CANDIDATES_FILE
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(candidates), encoding='utf-8')
        before = path.read_bytes()
        with self.assertRaises(config.DataError):
            self.store.set_entry('Beyond capacity', '不能提交')
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(self.store.read_dictionary()['entries'], {})
        state = self.store.cleanup(NOW + config.CANDIDATE_TTL_MS)
        self.assertEqual(len(state['candidates']['epochs']), 10000)
        self.assertEqual(state['candidates']['entries'], {})
        invalid = copy.deepcopy(state['candidates'])
        invalid['rejected']['One more'] = {'rejectedAt': NOW}
        with self.assertRaises(config.DataError):
            config.validate_candidates(invalid)

    def test_deleting_override_restores_normal_flow_but_invalidates_inflight_candidate(self):
        self.seed()
        self.store.set_entry('Label', '个人')
        before = self.store.read_state()
        deleted = self.store.delete_entry('Label', before['dictionary']['revision'])
        self.assertEqual(deleted['tombstones'], {'Label': 2})
        self.assertEqual(self.store.read_candidates()['rejected'], {})
        self.assertEqual(self.save_node()['status'], 'ok')

    def test_node_rolls_forward_interrupted_python_accept_without_double_revision(self):
        self.seed()
        self.candidate()
        original = self.store._write
        def fail(name, *args):
            if name == config.CANDIDATES_FILE:
                raise OSError('fixture interruption after dictionary write')
            return original(name, *args)
        with mock.patch.object(self.store, '_write', side_effect=fail):
            with self.assertRaises(OSError):
                self.store.accept_candidate('Label', 1)
        self.assertTrue((self.directory / config.JOURNAL_FILE).exists())
        state = self.node('process.stdout.write(JSON.stringify(await store.read(input.now)));')
        self.assertEqual(state['dictionary']['revision'], 1)
        self.assertEqual(state['dictionary']['entries']['Label']['source'], 'accepted')
        self.assertEqual(state['candidates']['entries'], {})
        self.assertEqual(self.store.read_state(), state)
        self.assertFalse((self.directory / config.JOURNAL_FILE).exists())

    def test_python_rolls_forward_interrupted_node_candidate_write(self):
        self.seed()
        result = self.node("const s=await store.read(input.now),original=store.writeFile;store.writeFile=async function(name,...args){if(name===S.CANDIDATES_FILE)throw Error('fixture interruption');return original.call(this,name,...args);};try{await store.saveCandidates([{source:'Label',translation:'恢复候选'}],{configRevision:s.config.revision,dictionaryRevision:s.dictionary.revision,epochs:{Label:0}},input.now);}catch(e){process.stdout.write(JSON.stringify({failed:true}));}")
        self.assertTrue(result['failed'])
        self.assertTrue((self.directory / config.JOURNAL_FILE).exists())
        state = self.store.read_state()
        self.assertEqual(state['candidates']['entries']['Label']['translation'], '恢复候选')
        self.assertEqual(state['candidates']['revision'], 1)
        self.assertFalse((self.directory / config.JOURNAL_FILE).exists())

    def test_interrupted_migration_rolls_forward_from_mixed_versions(self):
        self.seed(legacy=True)
        original = self.store._write
        def fail(name, *args):
            if name == 'personal-dictionary.json':
                raise OSError('fixture migration interruption')
            return original(name, *args)
        with mock.patch.object(self.store, '_write', side_effect=fail):
            with self.assertRaises(OSError):
                self.store.read_state()
        self.assertEqual(json.loads((self.directory / 'config.json').read_text())['schemaVersion'], 2)
        self.assertEqual(json.loads((self.directory / 'personal-dictionary.json').read_text())['schemaVersion'], 1)
        state = self.node('process.stdout.write(JSON.stringify(await store.read(input.now)));')
        self.assertEqual(state['config']['revision'], 5)
        self.assertEqual(state['dictionary']['revision'], 6)
        self.assertEqual(state['dictionary']['entries']['AI']['source'], 'legacy-ai')

    def test_unknown_schema_or_invalid_journal_never_overwrites_files(self):
        self.seed()
        before = (self.directory / 'config.json').read_bytes()
        for value in [None, {'schemaVersion': 1, 'kind': 'dragongirl-state-transaction', 'id': 'a' * 32,
                             'files': {'../outside.json': config.default_candidates()}}]:
            raw = json.dumps(value)
            (self.directory / config.JOURNAL_FILE).write_text(raw)
            with self.assertRaises(config.DataError):
                self.store.read_state()
            self.assertEqual((self.directory / config.JOURNAL_FILE).read_text(), raw)
            self.assertEqual((self.directory / 'config.json').read_bytes(), before)
        (self.directory / config.JOURNAL_FILE).unlink()
        unsupported = dict(config.default_dictionary(), schemaVersion=3)
        raw = json.dumps(unsupported)
        (self.directory / 'personal-dictionary.json').write_text(raw)
        with self.assertRaises(config.DataError):
            self.store.set_entry('New', '不得写入')
        self.assertEqual((self.directory / 'personal-dictionary.json').read_text(), raw)

    def test_nonfinite_json_values_are_preserved_and_not_migrated(self):
        current, _ = self.seed(legacy=True)
        path = self.directory / 'config.json'
        for number in ('NaN', 'Infinity', '-Infinity', '1e400'):
            raw = json.dumps(current)[:-1] + ', "extension": ' + number + '}'
            path.write_text(raw, encoding='utf-8')
            with self.assertRaises(config.DataError):
                self.store.read_state()
            self.assertEqual(path.read_text(encoding='utf-8'), raw)
        with self.assertRaises(config.DataError):
            self.store._encoded({'extension': float('nan')})

    def test_stale_candidate_revision_and_linked_pending_directory_are_rejected(self):
        self.seed()
        self.candidate()
        with self.assertRaises(config.ConflictError):
            self.store.reject_candidate('Label', 0)
        pending = self.directory / 'pending-translations'
        other = Path(self.temp.name) / 'outside'
        other.mkdir()
        shutil.rmtree(pending)
        try:
            pending.symlink_to(other, target_is_directory=True)
        except OSError as error:
            if os.name == 'nt' and getattr(error, 'winerror', None) == 1314:
                self.skipTest('Windows symlink privilege unavailable')
            raise
        with self.assertRaises(config.DataError):
            self.store.read_state()


if __name__ == '__main__':
    unittest.main()
