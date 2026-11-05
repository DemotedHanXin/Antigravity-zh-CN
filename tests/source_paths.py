"""Locate source modules when testing the checkout without installing a package."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'src'
LOCALIZATION = SOURCE / 'localization'
PROXY = SOURCE / 'proxy'
RUNTIME = SOURCE / 'localization_runtime'

# The root launcher exposes source packages; legacy tools also import siblings.
sys.path.insert(0, str(SOURCE))
sys.path.insert(0, str(LOCALIZATION))
