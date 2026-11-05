"""Windows current-user DPAPI; never falls back to plaintext storage.

The fixed entropy matches credentials.cjs. It is application separation, not a
secret. DPAPI protects against other users, not programs running as this user.
"""
import base64
import ctypes
import os

ENTROPY = b'Antigravity-zh-CN credentials v1'


class CredentialError(ValueError):
    pass


class WindowsProtector:
    def _crypt(self, value, decrypt=False):
        if os.name != 'nt':
            raise CredentialError('密钥保护仅支持 Windows 当前用户。')
        from ctypes import wintypes

        class Blob(ctypes.Structure):
            _fields_ = [('size', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_ubyte))]

        def blob(data):
            buffer = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
            return Blob(len(data), buffer), buffer

        incoming, keep_input = blob(value)
        entropy, keep_entropy = blob(ENTROPY)
        output = Blob()
        crypt32 = ctypes.WinDLL('crypt32', use_last_error=True)
        kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        kernel32.LocalFree.restype = ctypes.c_void_p
        function = crypt32.CryptUnprotectData if decrypt else crypt32.CryptProtectData
        function.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.POINTER(Blob),
                             ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
        function.restype = wintypes.BOOL
        try:
            # UI_FORBIDDEN only; never CRYPTPROTECT_LOCAL_MACHINE.
            if not function(ctypes.byref(incoming), None, ctypes.byref(entropy), None, None,
                            1, ctypes.byref(output)):
                raise CredentialError('无法使用当前 Windows 用户保护或解锁密钥；原数据已保留。')
            return ctypes.string_at(output.data, output.size)
        finally:
            ctypes.memset(keep_input, 0, len(keep_input))
            if output.data:
                ctypes.memset(output.data, 0, output.size)
                kernel32.LocalFree(output.data)

    def protect(self, value):
        return base64.b64encode(self._crypt(value.encode('utf-8'))).decode('ascii')

    def unprotect(self, value):
        try:
            return self._crypt(base64.b64decode(value, validate=True), True).decode('utf-8')
        except (ValueError, UnicodeError):
            raise CredentialError('无法使用当前 Windows 用户解锁密钥；原数据已保留。') from None
