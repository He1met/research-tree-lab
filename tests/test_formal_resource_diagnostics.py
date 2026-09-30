"""Read-only telemetry preserves resource gates and restores instrumented functions."""
import sys
from pathlib import Path
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from diagnose_formal_resources import observe_replay, resource_counters
from researchlib import formal_review as fr

class ResourceDiagnosticsTests(unittest.TestCase):
    def test_exact_byte_and_node_boundaries_are_unchanged(self):
        for byte_delta in (-1,0,1):
            for node_delta in (-1,0,1):
                ctx=fr._context();ctx['encoded_bytes']=fr.legacy.MAX_CONTEXT_BYTES+byte_delta
                ctx['nodes']=set(range(fr.MAX_HISTORY_NODES+node_delta))
                row=resource_counters(ctx)
                self.assertEqual(row['bytes_exceeded'],byte_delta>0)
                self.assertEqual(row['nodes_exceeded'],node_delta>0)
                if byte_delta>0 or node_delta>0:
                    with self.assertRaisesRegex(fr.Rejected,'COMBINED_HISTORY_RESOURCE_LIMIT_EXCEEDED'):fr._check_time(ctx)
                else:fr._check_time(ctx)

    def test_old_and_public_counts_and_node_union_are_not_waived(self):
        ctx=fr._context();ctx['encoded_bytes']=1;ctx['old_context']=fr._context()
        ctx['old_context']['encoded_bytes']=2;ctx['public_replay_bytes']=fr.legacy.MAX_CONTEXT_BYTES-2
        ctx['nodes']={1,2};ctx['old_context']['nodes']={2,3}
        self.assertEqual(resource_counters(ctx)['combined_nodes'],3)
        self.assertEqual(resource_counters(ctx)['combined_bytes'],fr.legacy.MAX_CONTEXT_BYTES+1)
        with self.assertRaisesRegex(fr.Rejected,'COMBINED_HISTORY_RESOURCE_LIMIT_EXCEEDED'):fr._check_time(ctx)

    def test_multiple_history_subtrees_are_accounted_once_without_deduction(self):
        def prepare(store,batch,inputs,cutoff,ctx):
            ctx['encoded_bytes']=10
            for child_name in {'root':['a','b'],'a':['c']}.get(batch,[]):
                child=fr._context();fr._prepare_bundle(store,child_name,inputs,cutoff,child)
                ctx['public_replay_bytes']=ctx.get('public_replay_bytes',0)+resource_counters(child)['combined_bytes']
            return {'records':[]}
        with patch.object(fr,'_prepare_bundle',prepare):
            result=observe_replay(None,'root',{},None)
            self.assertIs(fr._prepare_bundle,prepare)
        self.assertTrue(result['all_child_accounting_equal'])
        self.assertEqual(result['final_counters']['combined_bytes'],40)
        self.assertEqual(len(result['history_contexts']),4)

    def test_final_batch_failure_remains_fatal_and_has_accurate_diagnostics(self):
        def prepare(store,batch,inputs,cutoff,ctx):
            ctx['encoded_bytes']=fr.legacy.MAX_CONTEXT_BYTES+1
            for _ in range(2):
                try:fr._check_time(ctx)
                except fr.Rejected:pass
            fr._check_time(ctx)
            self.fail('No partial batch may escape a final resource gate')
        check=fr._check_time;reserve=fr._reserve;old_reserve=fr.legacy._reserve
        with patch.object(fr,'_prepare_bundle',prepare):
            result=observe_replay(None,'root',{},None)
            self.assertIs(fr._prepare_bundle,prepare)
        self.assertEqual(result['outcome'],'COMBINED_HISTORY_RESOURCE_LIMIT_EXCEEDED')
        self.assertEqual(len(result['checks_rejected']),3)
        self.assertTrue(all(r['bytes_exceeded'] and not r['nodes_exceeded'] for r in result['checks_rejected']))
        self.assertIs(fr._check_time,check);self.assertIs(fr._reserve,reserve);self.assertIs(fr.legacy._reserve,old_reserve)
        self.assertFalse(result['store_committed']);self.assertFalse(result['outbox_written'])

    def test_unexpected_exception_is_not_relabelled_or_swallowed(self):
        check=fr._check_time
        def prepare(*args):raise ValueError('test')
        with patch.object(fr,'_prepare_bundle',prepare):
            with self.assertRaisesRegex(ValueError,'test'):observe_replay(None,'root',{},None)
            self.assertIs(fr._prepare_bundle,prepare)
        self.assertIs(fr._check_time,check)
