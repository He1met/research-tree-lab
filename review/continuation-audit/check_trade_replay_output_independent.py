"""Independent helper-output attacks against synthetic temporary files only."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--code-root', required=True, type=Path)
    args=parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='independent-trade-output-') as temp:
        root=Path(temp).resolve()
        from datetime import datetime, timezone
        at=int(datetime(2026,9,20,16,tzinfo=timezone.utc).timestamp()*1000)
        csv=('instrument_name,trade_id,side,price,size,created_time,source\nBTC-USDT-SWAP,1,buy,1,1,%d,0\n'%at).encode()
        buffer=io.BytesIO()
        with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('BTC-USDT-SWAP-trades-2026-09-21.csv',csv)
        source=root/'source.zip';source.write_bytes(buffer.getvalue())
        dataset=root/'dataset.json'
        dataset.write_text(json.dumps({'dataset_id':'d-btc-trades-20260921','version':1,
            'synthetic':False,'instrument_ref':'BTC-USDT-SWAP','data_role':'TARGET_TRADE_HISTORY',
            'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'bytes':source.stat().st_size,
            'source_url':'https://www.okx.com/historical-data','acquired_at':'2026-09-21T00:00:00Z'}))
        sentinel=root/'existing.json';sentinel.write_bytes(b'immutable-sentinel')
        alias=root/'source-alias.json';alias.symlink_to(source)
        dangling=root/'dangling.json';missing=root/'must-not-create.json';dangling.symlink_to(missing)
        original={path:path.read_bytes() for path in (source,dataset,sentinel)}
        cases=[]
        for label,output in [('source',source),('dataset',dataset),('existing',sentinel),
                             ('source_symlink',alias),('dangling_symlink',dangling)]:
            result=subprocess.run([sys.executable,str(args.code_root/'tests/replay_okx_trade_sample.py'),
                '--source',str(source),'--dataset',str(dataset),'--receipt',str(output)],
                text=True,capture_output=True,timeout=10)
            assert result.returncode != 0, label
            assert all(path.read_bytes()==blob for path,blob in original.items()),label
            assert not missing.exists(), label
            cases.append(label+'_rejected_originals_unchanged')
        output=root/'new.json'
        result=subprocess.run([sys.executable,str(args.code_root/'tests/replay_okx_trade_sample.py'),
            '--source',str(source),'--dataset',str(dataset),'--receipt',str(output)],
            text=True,capture_output=True,timeout=10)
        assert result.returncode != 0
        assert output.exists()
        assert json.loads(output.read_text())['status'] == 'COMPARISON_FAILED'
        assert all(path.read_bytes()==blob for path,blob in original.items())
        cases.append('nonmatching_fixture_cannot_emit_pass_or_mutate_input')
        print(json.dumps({'state':'PASS_SYNTHETIC_HELPER_OUTPUT_ATTACKS','checks':cases,
            'helper_sha256':hashlib.sha256((args.code_root/'tests/replay_okx_trade_sample.py').read_bytes()).hexdigest(),
            'production_mutated':False,'finding':'P2_RECEIPT_INPUT_OVERWRITE_RETEST'},sort_keys=True))


if __name__=='__main__':
    main()
