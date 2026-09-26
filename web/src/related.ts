import type { JsonRecord } from './data';

// These are explicit references, not evidence of derivation or execution.
export function relatedFields(record: JsonRecord, roundId: string): string[] {
  return ['round_id', 'source_round_ref', 'input_record_refs'].filter(field => {
    const value = record[field];
    return field === 'input_record_refs' ? Array.isArray(value) && value.includes(roundId) : value === roundId;
  });
}
export function relatedTab(record: JsonRecord): 'plan' | 'feedback' | undefined {
  if (typeof record.decision_id === 'string') return 'feedback';
  if (typeof record.run_id === 'string' || typeof record.evidence_id === 'string') return 'plan';
  return undefined;
}
