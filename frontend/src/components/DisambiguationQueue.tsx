import React, { useState } from 'react';
import { Users, Key, AlertTriangle, CheckCircle2, ArrowRight } from 'lucide-react';

export interface DisambiguationItem {
  candidate_entity_id: string;
  primary_name_bn: string;
  primary_name_en: string;
  father_name_bn?: string;
  thana_jurisdiction?: string;
  age?: number;
  name_phonetic_sim: number;
  father_name_sim: number;
  thana_match_score: number;
  age_proximity_score: number;
  composite_score: number;
  adjudication_status: string;
}

interface DisambiguationQueueProps {
  candidates: DisambiguationItem[];
  targetEntityName: string;
  targetEntityId: string;
  onResolveSuccess?: (edgeData: any) => void;
}

export const DisambiguationQueue: React.FC<DisambiguationQueueProps> = ({
  candidates,
  targetEntityName,
  targetEntityId,
  onResolveSuccess,
}) => {
  const [selectedCandidate, setSelectedCandidate] = useState<DisambiguationItem | null>(null);
  const [operatorKey1, setOperatorKey1] = useState('');
  const [operatorKey2, setOperatorKey2] = useState('');
  const [justificationLabel, setJustificationLabel] = useState(
    'MANUALLY CONFIRMED SAME PERSON VIA NID & COURT ORDER COMPARISON'
  );
  const [submitting, setSubmitting] = useState(false);
  const [feedback, setFeedback] = useState<{ type: 'error' | 'success'; message: string } | null>(null);

  const handleResolveConflict = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedCandidate) return;

    if (operatorKey1.trim() === operatorKey2.trim()) {
      setFeedback({
        type: 'error',
        message: 'Security Violation: Two distinct operator keys required (Four-Eyes Principle).',
      });
      return;
    }

    setSubmitting(true);
    setFeedback(null);

    try {
      const response = await fetch('/api/entity/resolve_conflict', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          entity_a_id: targetEntityId,
          entity_b_id: selectedCandidate.candidate_entity_id,
          source_document_id: '11111111-2222-3333-4444-555555555555', // Valid reference stub
          contextual_label: justificationLabel,
          confidence_score: selectedCandidate.composite_score,
          operator_key_1: operatorKey1.trim(),
          operator_key_2: operatorKey2.trim(),
        }),
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || 'Resolution edge creation rejected.');
      }

      const data = await response.json();
      setFeedback({
        type: 'success',
        message: `Edge pointer created! Both entity UUIDs (${targetEntityId.slice(0, 8)}... and ${selectedCandidate.candidate_entity_id.slice(0, 8)}...) remain preserved independently.`,
      });
      onResolveSuccess?.(data);
    } catch (err: any) {
      setFeedback({
        type: 'error',
        message: err.message || 'Failed to submit resolution.',
      });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/95 p-6 shadow-2xl">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-4 mb-5">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-cyan-950 border border-cyan-800 text-cyan-400">
            <Users className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-base font-bold text-white">
              Bengali Entity Disambiguation Queue
            </h3>
            <p className="text-xs text-slate-400">
              Evaluating target: <strong className="text-cyan-300 font-bangla">{targetEntityName}</strong>
            </p>
          </div>
        </div>

        <span className="font-mono text-xs bg-red-950/80 text-red-300 border border-red-700/80 px-2.5 py-1 rounded">
          ZERO AUTO-MERGE POLICY
        </span>
      </div>

      {/* Strict Policy Alert */}
      <div className="rounded-lg bg-amber-950/30 border border-amber-800/60 p-3.5 mb-5 text-xs text-amber-200 flex items-start gap-2.5">
        <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
        <p>
          <strong>VITAL LEGAL SAFEGUARD:</strong> Automatic UUID record merging is mathematically forbidden.
          High similarity candidates are queued for human adjudication. Approving a match creates an explicit{' '}
          <code className="text-cyan-300 bg-slate-950 px-1 py-0.5 rounded border border-slate-800">SAME_AS</code>{' '}
          pointer while permanently retaining distinct database entities and provenance lineages.
        </p>
      </div>

      {/* Candidate List */}
      <div className="space-y-3 mb-6">
        {candidates.map((cand) => {
          const isSelected = selectedCandidate?.candidate_entity_id === cand.candidate_entity_id;
          const isHigh = cand.composite_score >= 0.85;

          return (
            <div
              key={cand.candidate_entity_id}
              onClick={() => setSelectedCandidate(cand)}
              className={`cursor-pointer rounded-lg border p-4 transition-all flex flex-col md:flex-row md:items-center justify-between gap-4 ${
                isSelected
                  ? 'border-cyan-500 bg-slate-800/80 shadow-md'
                  : 'border-slate-800 bg-slate-950 hover:border-slate-700'
              }`}
            >
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="font-bold text-white font-bangla text-base">
                    {cand.primary_name_bn}
                  </span>
                  <span className="text-xs text-slate-400 font-mono">
                    ({cand.primary_name_en})
                  </span>
                </div>

                <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-400">
                  <span>Pita: <strong className="text-slate-200 font-bangla">{cand.father_name_bn || 'Unknown'}</strong></span>
                  <span>Thana: <strong className="text-slate-200">{cand.thana_jurisdiction || 'N/A'}</strong></span>
                  <span>Age: <strong className="text-slate-200">{cand.age || 'N/A'}</strong></span>
                </div>
              </div>

              {/* Score breakdown metrics */}
              <div className="flex items-center gap-4 shrink-0">
                <div className="text-right">
                  <div className="text-xs font-mono text-slate-400">
                    Phonetic: {(cand.name_phonetic_sim * 100).toFixed(0)}% • Father: {(cand.father_name_sim * 100).toFixed(0)}%
                  </div>
                  <div className="flex items-center justify-end gap-2 mt-1">
                    <span className="text-xs font-mono text-slate-500">Composite:</span>
                    <span
                      className={`font-mono text-sm font-bold px-2 py-0.5 rounded ${
                        isHigh
                          ? 'bg-red-950 text-red-300 border border-red-800'
                          : 'bg-slate-800 text-slate-300'
                      }`}
                    >
                      {(cand.composite_score * 100).toFixed(1)}%
                    </span>
                  </div>
                </div>

                <button
                  type="button"
                  className={`px-3 py-1.5 rounded text-xs font-semibold flex items-center gap-1 transition-colors ${
                    isSelected
                      ? 'bg-cyan-500 text-slate-950 font-bold'
                      : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
                  }`}
                >
                  <span>Select</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* Dual-Key Sign-off Modal / Drawer */}
      {selectedCandidate && (
        <form
          onSubmit={handleResolveConflict}
          className="rounded-lg border border-cyan-800/80 bg-slate-950 p-5 space-y-4 animate-in fade-in"
        >
          <div className="flex items-center justify-between border-b border-slate-800 pb-2">
            <span className="text-xs font-bold text-cyan-400 uppercase tracking-wider flex items-center gap-1.5">
              <Key className="w-4 h-4" /> Two-Operator Cryptographic Resolution Authorization
            </span>
            <span className="text-xs font-mono text-slate-400">
              Target ID: {targetEntityId.slice(0, 8)} ↔ Candidate ID: {selectedCandidate.candidate_entity_id.slice(0, 8)}
            </span>
          </div>

          <div>
            <label className="block text-xs font-mono text-slate-400 mb-1">
              Contextual Edge Description (Mandatory Legal Citation)
            </label>
            <input
              type="text"
              value={justificationLabel}
              onChange={(e) => setJustificationLabel(e.target.value)}
              required
              className="w-full rounded bg-slate-900 border border-slate-700 px-3 py-2 text-xs text-white focus:outline-none focus:border-cyan-500 font-mono"
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-mono text-slate-400 mb-1">
                Primary Operator Key / UUID (Analyst 1)
              </label>
              <input
                type="text"
                placeholder="e.g. 11111111-1111-1111-1111-111111111111"
                value={operatorKey1}
                onChange={(e) => setOperatorKey1(e.target.value)}
                required
                className="w-full rounded bg-slate-900 border border-slate-700 px-3 py-2 text-xs text-white font-mono focus:outline-none focus:border-cyan-500"
              />
            </div>
            <div>
              <label className="block text-xs font-mono text-slate-400 mb-1">
                Secondary Reviewer Key / UUID (Supervisor 2)
              </label>
              <input
                type="text"
                placeholder="e.g. 22222222-2222-2222-2222-222222222222"
                value={operatorKey2}
                onChange={(e) => setOperatorKey2(e.target.value)}
                required
                className="w-full rounded bg-slate-900 border border-slate-700 px-3 py-2 text-xs text-white font-mono focus:outline-none focus:border-cyan-500"
              />
            </div>
          </div>

          {feedback && (
            <div
              className={`p-3 rounded text-xs flex items-center gap-2 ${
                feedback.type === 'error'
                  ? 'bg-red-950/80 text-red-200 border border-red-800'
                  : 'bg-emerald-950/80 text-emerald-200 border border-emerald-800'
              }`}
            >
              {feedback.type === 'error' ? <AlertTriangle className="w-4 h-4 shrink-0" /> : <CheckCircle2 className="w-4 h-4 shrink-0" />}
              <span>{feedback.message}</span>
            </div>
          )}

          <div className="flex items-center justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={() => setSelectedCandidate(null)}
              className="px-3 py-1.5 rounded text-xs text-slate-400 hover:text-white"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="px-4 py-2 rounded-lg bg-cyan-600 hover:bg-cyan-500 font-bold text-slate-950 text-xs transition-colors flex items-center gap-1.5 disabled:opacity-50"
            >
              {submitting ? 'Signing Ledger...' : 'Enact SAME_AS Edge Pointer Link'}
            </button>
          </div>
        </form>
      )}
    </div>
  );
};
