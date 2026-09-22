"""Independent synthetic CLI output-path attacks; no production data or writes."""
import argparse
from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--code-root', type=Path, required=True)
    args = parser.parse_args(); sys.path.insert(0, str(args.code_root))
    spec = importlib.util.spec_from_file_location('independent_public_helper', args.code_root/'tests/verify_public_fields_v2.py')
    helper = importlib.util.module_from_spec(spec); spec.loader.exec_module(helper)
    checks = []
    outcomes = []
    for attack in ('normal', 'receipts-root-symlink', 'nested-parent-symlink', 'leaf-symlink',
                   'existing-file', 'hardlink', 'traversal', 'parent-replaced-during-verification',
                   'leaf-replaced-during-verification', 'verification-failure'):
        with tempfile.TemporaryDirectory(prefix='independent-output-probe-') as scratch:
            base = Path(scratch).resolve(); candidate=base/'candidate'; outside=base/'outside'
            receipts=candidate/'tests/receipts'; receipts.mkdir(parents=True); outside.mkdir()
            original=outside/'original.json'; original.write_bytes(b'IMMUTABLE_SYNTHETIC_SOURCE_BYTES')
            output=receipts/'new.json'; called=[]
            if attack=='receipts-root-symlink':
                receipts.rmdir(); receipts.symlink_to(outside,target_is_directory=True)
            elif attack=='nested-parent-symlink':
                (receipts/'linked').symlink_to(outside,target_is_directory=True);output=receipts/'linked/new.json'
            elif attack=='leaf-symlink': output.symlink_to(original)
            elif attack=='existing-file': output.write_bytes(b'EXISTING_RECEIPT')
            elif attack=='hardlink': os.link(original,output)
            elif attack=='traversal': output=receipts/'../../../outside/new.json'
            def verify(_):
                called.append(True)
                if attack=='parent-replaced-during-verification':
                    receipts.rename(candidate/'tests/original-receipts')
                    receipts.symlink_to(outside,target_is_directory=True)
                elif attack=='leaf-replaced-during-verification':
                    if output.exists(): output.unlink()
                    output.symlink_to(original)
                elif attack=='verification-failure': raise RuntimeError('SYNTHETIC_VERIFY_FAILURE')
                return {'state':'SYNTHETIC_PASS','old_public_records_unchanged':0,
                        'new_public_records_exact':0,'former_failures_now_exact':0,'cases':[]}
            caught = None
            with patch.object(helper,'ROOT',candidate),patch.object(helper,'verify',side_effect=verify), \
                 patch.object(sys,'argv',['verify','--code-root',str(base),'--receipt',str(output)]), \
                 redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()):
                try: helper.main()
                except (OSError,ValueError,RuntimeError,SystemExit) as error: caught=type(error).__name__
            assert original.read_bytes()==b'IMMUTABLE_SYNTHETIC_SOURCE_BYTES',attack
            assert not (outside/'new.json').exists(),attack
            if attack=='normal':
                assert caught is None and json.loads(output.read_text())['state']=='SYNTHETIC_PASS'
            elif attack in {'receipts-root-symlink','nested-parent-symlink','leaf-symlink','existing-file','hardlink','traversal'}:
                assert caught is not None and not called,(attack,caught,called)
            elif attack=='verification-failure':
                assert caught is not None and output.read_bytes()==b'',attack
            if attack=='existing-file': assert output.read_bytes()==b'EXISTING_RECEIPT'
            checks.append(attack)
            outcomes.append({'attack':attack,'verification_called':bool(called),'caught':caught})
    from researchlib.common import digest
    print(json.dumps({'state':'PASS_INDEPENDENT_PUBLIC_HELPER_OUTPUT_ATTACKS','cases':len(checks),
        'checks':checks,'outcomes':outcomes,'helper_sha256':digest((args.code_root/'tests/verify_public_fields_v2.py').read_bytes()),
        'production_modified':False,'synthetic_only':True}))


if __name__=='__main__': main()
