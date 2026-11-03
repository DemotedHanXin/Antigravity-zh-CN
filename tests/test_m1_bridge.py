import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from source_paths import ROOT
sys.path.insert(0, str(ROOT / 'tests/manual'))
import m1_bridge


class CandidateTests(unittest.TestCase):
    def test_controlled_override_is_unique_and_preserves_original_dictionary(self):
        spec = importlib.util.spec_from_file_location('m1_fixture_patcher', ROOT / 'src/localization/Antigravity-Patcher.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        profile = json.loads(m1_bridge.CANDIDATE.read_text(encoding='utf-8'))['profile']
        original = module.build_dom_injection(profile)
        controlled = m1_bridge.controlled_dom(original)
        self.assertIn('"Automations": "自动化"', controlled)
        self.assertEqual(controlled.count("if (text.trim() === 'Automations') return {value: text, matched: false};"), 1)
        self.assertEqual(module.build_dom_injection(profile), original)
        for invalid in ('no marker', m1_bridge.SYNC_RESULT * 2):
            with self.assertRaises(ValueError):
                m1_bridge.controlled_dom(invalid)

    def test_candidate_has_only_audited_navigation_labels_and_exact_root_route(self):
        candidate = json.loads(m1_bridge.CANDIDATE.read_text(encoding='utf-8'))
        self.assertEqual(candidate['scope'], 'isolated-lab-only')
        self.assertEqual(candidate['acceptanceStatus'], 'pending-runtime-verification')
        p = candidate['profile']
        m1_bridge._validate_profile(p)
        self.assertEqual(p['windowBinding']['paths'], ['/'])
        self.assertEqual(p['policy']['paths'], ['/'])
        self.assertEqual({r['sourceTexts'][0] for r in p['policy']['rules']},
                         {'New Conversation', 'Automations', 'Customizations', 'Settings'})
        for r in p['policy']['rules']:
            self.assertEqual(r['contextKind'], 'navigation')
            self.assertTrue(r['selector'].startswith('#root > '))
            self.assertNotIn('attributes', r)

    def test_install_refuses_running_launcher_before_loading_patcher(self):
        with patch.object(m1_bridge.lab, 'lab_root', return_value=Path('fixture')), \
             patch.object(m1_bridge.lab, 'installation', return_value=Path('fixture/install')), \
             patch.object(Path, 'exists', return_value=True), \
             patch.object(importlib.util, 'spec_from_file_location', side_effect=AssertionError('Do not load patcher')):
            with self.assertRaisesRegex(ValueError, 'Stop the isolated launcher'):
                m1_bridge.install('fixture')

    def test_daily_install_cannot_be_an_install_target(self):
        with self.assertRaises(ValueError):
            m1_bridge.install(ROOT / 'ordinary-install')


if __name__ == '__main__':
    unittest.main()
