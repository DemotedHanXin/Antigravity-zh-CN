"""Locate source modules when testing the checkout without installing a package."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
LOCALIZATION = ROOT / 'src' / 'localization'
PROXY = ROOT / 'src' / 'proxy'

# Production entry scripts import their sibling modules in this directory.
sys.path.insert(0, str(LOCALIZATION))
