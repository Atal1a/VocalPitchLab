import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from vocalpitchlab.analysis import analysis_cache as cache


class AnalysisCacheTests(unittest.TestCase):
    def test_short_work_paths_publish_and_reuse_verified_results(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)/'profile'/('u'*20)/'AppData/Local/VocalPitchLab'
            def producer(work):
                self.assertLessEqual(len(work.name),12)
                path=work/'vocals.wav';path.write_bytes(b'audio')
                return {'audio':path}
            with patch.object(cache,'DATA_ROOT',root):
                paths,first=cache.stage('lead',{'model':'test'},producer)
                again,second=cache.stage('lead',{'model':'test'},lambda _:self.fail('cache was not reused'))
            self.assertEqual(paths,again)
            self.assertFalse(first['hit']);self.assertTrue(second['hit'])

    def test_legacy_work_directory_remains_readable(self):
        signature={'version':'old'}
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            key=hashlib.sha256(json.dumps(signature,sort_keys=True,separators=(',',':')).encode()).hexdigest()
            folder=root/'results/stages/lead'/key
            audio=folder/('work-'+'a'*32)/'vocals.wav'
            audio.parent.mkdir(parents=True);audio.write_bytes(b'original')
            (folder/'complete.json').write_text(json.dumps(dict(signature=signature,files=dict(audio=dict(
                path=audio.relative_to(folder).as_posix(),size=8,sha256=cache.digest_file(audio))))))
            with patch.object(cache,'DATA_ROOT',root):
                paths,meta=cache.stage('lead',signature,lambda _:self.fail('legacy cache was discarded'))
            self.assertEqual(paths['audio'],audio);self.assertTrue(meta['hit'])

    def test_failed_stage_does_not_publish_partial_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            def interrupted(work):
                (work/'vocals.wav').write_bytes(b'partial')
                raise RuntimeError('interrupted')
            with patch.object(cache,'DATA_ROOT',root),self.assertRaises(RuntimeError):
                cache.stage('lead',{'version':'test'},interrupted)
            self.assertFalse(list(root.rglob('complete.json')))
