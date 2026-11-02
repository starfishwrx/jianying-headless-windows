"""Owned output routing and the Windows codec's refuse-overwrite boundary."""
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'engine'))
import jy14_headless as j
import production_library as library


class ProductionLibraryTests(unittest.TestCase):
    def test_binding_can_be_verified_after_target_is_published(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw).resolve(); (root/'case').mkdir()
            target,actual= j.build_target({'name':'case'},library_root=root)
            self.assertEqual((target,actual),(root/'case',root))

    def test_relocation_uses_fresh_codec_outputs_and_preserves_source(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw).resolve();source=root/'source';source.mkdir()
            tid='timeline-id'
            for p in library.mirrors(source,tid):
                p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'old-cipher')
            (source/'draft_meta_info.json').write_bytes(b'old-metadata')
            record={'files':j.files_manifest(source),'target':str(source),'name':'source','timeline_id':tid,'draft_id':'preserved-id'}
            marker={'schema':library.SCHEMA,'plan':{'name':'source'},'record':record}
            j.write(source/library.MARKER,marker)
            original=j.files_manifest(source)
            loaded={'timeline':{'id':tid,'name':'source','materials':{}},
                    'metadata':{'draft_id':'preserved-id','draft_name':'source','draft_fold_path':str(source)},
                    'marker':marker,'reference_root':str(source)}
            writes=[]
            class Codec:
                def _encrypt_metadata_from_memory(self,payload,path):
                    self.assert_new(path)
                    Path(path).write_bytes(b'new-cipher:'+payload)
                    writes.append(Path(path))
                def assert_new(self,path):
                    if Path(path).exists():
                        raise RuntimeError('codec refuses existing output')
            stage,target=root/'stage',root/'destination'/'renamed'
            with patch.object(library,'inspect',return_value=deepcopy(loaded)), \
                 patch.object(library.j.nd,'helper',return_value=Codec()), \
                 patch.object(library.fonts,'rebase_existing'):
                result=library.relocate(source,stage,target)
            self.assertEqual(len(writes),2)
            self.assertTrue(all(not p.exists() for p in writes))
            self.assertEqual(j.files_manifest(source),original)
            self.assertEqual(result['draft_id'],'preserved-id')
            self.assertEqual(len({p.read_bytes() for p in library.mirrors(stage,tid)}),1)


if __name__=='__main__':
    unittest.main()
