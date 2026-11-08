"""Verify voice labels without replacing button nodes or preset values."""
import unittest

from test_icon_repair import BROWSER, run_dom_check


FIXTURES = r"""
<button id="whole" data-voice="Fola">Use Fola</button>
<button id="split" data-voice="Arlo"><span id="verb">Use </span><span id="preset">Arlo</span></button>
<div id="nested" role="button" data-voice="Cleo"><span><span id="nested-verb">Use </span></span><span>Cleo</span></div>
<button id="unknown">Use Custom</button>
<div id="outside"><span>Use </span><span>Fola</span></div>
<pre><code id="code">Use Fola</code></pre>
<div contenteditable="true" id="editable">Use Fola</div>
<div id="models">Models within this group: Claude Opus, Claude Sonnet, GPT-OSS</div>
<div id="split-models"><span id="model-prefix">Models within this group: </span><span id="model-names">Gemini Flash, Gemini Pro</span></div>
<pre id="icon-repair-result"></pre>
"""

CHECKS = r"""
const ids = ['whole', 'split', 'verb', 'preset', 'nested', 'nested-verb', 'models',
             'split-models', 'model-prefix', 'model-names'];
const elements = Object.fromEntries(ids.map(id => [id, document.getElementById(id)]));
const textNodes = Object.fromEntries(['whole', 'verb', 'preset', 'nested-verb', 'models',
                                    'model-prefix', 'model-names'].map(id => [id, elements[id].firstChild]));
let clicks = 0;
elements.split.addEventListener('click', () => { clicks++; });
const tick = () => new Promise(resolve => setTimeout(resolve, 0));
const ensure = (condition, message) => { if (!condition) throw new Error(message); };
document.addEventListener('DOMContentLoaded', async () => {
  const result = document.getElementById('icon-repair-result');
  try {
    await tick();
    ensure(elements.whole.textContent === '使用 Fola', 'whole button not translated');
    ensure(elements.split.textContent === '使用 Arlo', 'split button not translated');
    ensure(elements.nested.textContent === '使用 Cleo', 'nested button not translated');
    ensure(elements.models.textContent === '本组包含的模型：Claude Opus, Claude Sonnet, GPT-OSS', 'model list changed');
    ensure(elements['split-models'].textContent === '本组包含的模型： Gemini Flash, Gemini Pro', 'split model list changed');
    for (const [id, expected] of [['unknown', 'Use Custom'], ['outside', 'Use Fola'],
                                  ['code', 'Use Fola'], ['editable', 'Use Fola']]) {
      ensure(document.getElementById(id).textContent === expected, id + ': unrelated text modified');
    }
    textNodes.whole.textContent = 'Use Tari';
    textNodes.preset.textContent = 'Neno';
    textNodes['nested-verb'].textContent = 'Use ';
    textNodes.models.textContent = 'Models within this group: Gemini Flash, Gemini Pro';
    textNodes['model-names'].textContent = 'Claude Opus, Claude Sonnet, GPT-OSS';
    await tick();
    ensure(elements.whole.textContent === '使用 Tari', 'whole button update missed');
    ensure(elements.split.textContent === '使用 Neno', 'voice name update missed');
    ensure(elements.nested.textContent === '使用 Cleo', 'prefix rerender missed');
    ensure(elements.models.textContent === '本组包含的模型：Gemini Flash, Gemini Pro', 'model update missed');
    ensure(elements['split-models'].textContent === '本组包含的模型： Claude Opus, Claude Sonnet, GPT-OSS', 'split model update missed');
    textNodes.verb.textContent = 'Use ';
    await tick();
    ensure(elements.split.textContent === '使用 Neno', 'split prefix rerender missed');
    for (const id of ids) ensure(document.getElementById(id) === elements[id], id + ': element replaced');
    for (const [id, node] of Object.entries(textNodes)) ensure(elements[id].firstChild === node, id + ': text node replaced');
    ensure(elements.whole.dataset.voice === 'Fola' && elements.split.dataset.voice === 'Arlo' &&
           elements.nested.dataset.voice === 'Cleo', 'voice action values modified');
    elements.split.click();
    ensure(clicks === 1, 'button handler changed');
    result.textContent = JSON.stringify({ok: true, checks: 'voice and model labels, updates, nodes, actions, protected text'});
  } catch (error) {
    result.textContent = JSON.stringify({ok: false, error: error.message});
  }
});
"""


@unittest.skipUnless(BROWSER, 'Chrome or Edge is required for the isolated DOM test')
class VoiceSelectionTests(unittest.TestCase):
    def test_voice_and_model_labels_preserve_nodes_actions_and_updates(self):
        run_dom_check(self, FIXTURES, CHECKS)


if __name__ == '__main__':
    unittest.main()
