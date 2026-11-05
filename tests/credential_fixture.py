"""Explicit fixture-only protector for non-Windows protocol tests.

Windows runs use native DPAPI. The portable codec is deliberately not encryption
and must never be imported by production. Its marker matches the JS test fixture.
"""
import base64
import os
from translation_config import UserStore as RealUserStore
from credential_protection import CredentialError


class FixtureProtector:
    def protect(self, value):
        return base64.b64encode(('fixture:' + value).encode('utf-8')).decode('ascii')

    def unprotect(self, value):
        decoded = base64.b64decode(value, validate=True).decode('utf-8')
        if not decoded.startswith('fixture:'):
            raise CredentialError('fixture mismatch')
        return decoded[8:]


class UserStore(RealUserStore):
    def __init__(self, *args, **kwargs):
        if os.name != 'nt':
            kwargs.setdefault('protector', FixtureProtector())
        super().__init__(*args, **kwargs)
