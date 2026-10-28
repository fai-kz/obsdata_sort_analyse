"""Controlled test of verbatim deployed RD code; database and clock are doubles.

Run on development host: python3 test_release.py /var/gavo/inputs/ccd_observations/q.rd
No archive, database, system-clock, or service changes are made.
"""
import datetime
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import textwrap
import types
import xml.etree.ElementTree as ET

import numpy as np
from astropy.io import fits

rd = Path(sys.argv[1])
root = ET.fromstring(rd.read_bytes())
proc = root.find("./service[@id='zeroed']/pythonCore/coreProc")
setup = textwrap.dedent(proc.find('setup/code').text)
body = textwrap.dedent(proc.find('code').text)
release = datetime.date(2026, 10, 29)

class Clock(datetime.date):
    value = release - datetime.timedelta(days=1)

    @classmethod
    def today(cls):
        return cls.value

results = []
with tempfile.TemporaryDirectory(prefix='kazvo-embargo-test-') as folder:
    path = Path(folder) / 'synthetic.fits'
    primary = fits.PrimaryHDU(np.arange(1, 65, dtype=np.int16).reshape(8, 8))
    primary.header['OBJECT'] = 'SYNTHETIC EMBARGO TEST'
    primary.header['RELEASE'] = release.isoformat()
    primary.header['CRVAL1'] = 123.45
    primary.header['CRVAL2'] = 45.67
    extension = fits.ImageHDU(np.arange(1, 17, dtype=np.float32).reshape(4, 4))
    fits.HDUList([primary, extension]).writeto(path)
    original = path.read_bytes()
    digest = hashlib.sha256(b'synthetic-test-only').hexdigest()

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def query(self, sql, params):
            assert params['accref'] == 'ccd_observations/products/' + digest + '.fits'
            return [('synthetic.fits', release)]

    base = types.SimpleNamespace(
        getTableConn=Connection,
        getConfig=lambda key: folder if key == 'inputsDir' else None)
    namespace = dict(datetime=types.SimpleNamespace(date=Clock),
                     io=io, os=os, re=re, base=base)
    exec(compile(setup, str(rd) + ':zeroed/setup', 'exec'), namespace)
    exec(compile('def run(inputTable):\n' + textwrap.indent(body, '    '),
                 str(rd) + ':zeroed/core', 'exec'), namespace)
    inputs = types.SimpleNamespace(getParam=lambda key: digest + '/synthetic.fits')
    with fits.open(path) as hdus:
        infos = [h.fileinfo() for h in hdus]

    for offset in [-1, 0, 1, -1]:
        Clock.value = release + datetime.timedelta(days=offset)
        mime, payload = namespace['run'](inputs)
        assert mime == 'application/fits'
        assert len(payload) == len(original)
        headers_equal = all(
            payload[x['hdrLoc']:x['datLoc']] == original[x['hdrLoc']:x['datLoc']]
            for x in infos)
        assert headers_equal
        with fits.open(io.BytesIO(payload)) as delivered:
            all_zero = all(np.all(h.data == 0) for h in delivered if h.data is not None)
        if offset < 0:
            assert all_zero
            assert payload != original
        else:
            assert payload == original
            assert not all_zero
        assert path.read_bytes() == original
        results.append(dict(date=str(Clock.value), release=str(release),
                            outcome='masked' if offset < 0 else 'original',
                            headers_identical=headers_equal,
                            payload_sha256=hashlib.sha256(payload).hexdigest(), passed=True))

print(json.dumps(dict(
    test_scope='Deployed handler with controlled clock and database test double; no HTTP transition test',
    rd_path=str(rd), rd_sha256=hashlib.sha256(rd.read_bytes()).hexdigest(),
    executed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    cases=results, source_unchanged=True), indent=2))
