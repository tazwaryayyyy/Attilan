import React, { useState } from 'react';
import { DocumentRecord } from '../types/evidence';
import { History, X, AlertTriangle, ShieldCheck } from 'lucide-react';

interface SoftTombstoneModalProps {
  document: DocumentRecord;
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (updatedRecord: any) => void;
}

export const SoftTombstoneModal: React.FC<SoftTombstoneModalProps> = ({
  document,
  isOpen,
  onClose,
  onSuccess,
}) => {
  const [legalJustification, setLegalJustification] = useState(
    'Certified Judicial Decree: Sessions Case No. 45/2026, Khulna Sessions Judge Court. Accused fully acquitted under Section 265H CrPC.'
  );
  const [newSummary, setNewSummary] = useState(
    'Sessions Court examined prosecution witnesses and ruled allegations unsubstantiated. Accused honorably acquitted.'
  );
  const [courtOrderSourceId, setCourtOrderSourceId] = useState(
    '33333333-4444-5555-6666-777777777777'
  );
  const [newWeight, setNewWeight] = useState('JUDICIAL_ACQUITTAL');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);

    try {
      const response = await fetch(`/api/events/${document.source_id}/tombstone_and_supersede`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          legal_justification: legalJustification,
          court_order_source_id: courtOrderSourceId,
          new_event_type: 'JUDICIAL_VERDICT',
          new_procedural_weight: newWeight,
          new_event_summary: newSummary,
          new_event_date: new Date().toISOString().split('T')[0],
        }),
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Failed to soft-tombstone event.');
      }

      const resData = await response.json();
      onSuccess(resData);
      onClose();
    } catch (err: any) {
      setError(err.message || 'Submission failed');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
      <div className="relative w-full max-w-2xl rounded-2xl border border-slate-700 bg-slate-900 p-6 shadow-2xl space-y-4">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2 text-amber-400">
            <History className="w-5 h-5" />
            <h3 className="text-base font-bold text-white">
              Controlled Correction & Soft-Tombstoning Protocol
            </h3>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Legal notice */}
        <div className="rounded-lg bg-amber-950/40 border border-amber-800/60 p-3 text-xs text-amber-200 flex items-start gap-2.5">
          <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
          <div>
            <strong>IMMUTABLE RECORD RETENTION:</strong> The existing V1 record will be preserved in the append-only Merkle ledger with flag{' '}
            <code className="text-cyan-300 font-mono">is_superseded = TRUE</code>. Active searches and UI will return the new V2 judicial record.
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4 text-xs font-mono">
          <div>
            <label className="block text-slate-300 mb-1 font-sans font-medium">
              Statutory Legal Justification (Court Order Citation)
            </label>
            <textarea
              rows={2}
              value={legalJustification}
              onChange={(e) => setLegalJustification(e.target.value)}
              required
              className="w-full rounded bg-slate-950 border border-slate-700 p-2 text-white focus:outline-none focus:border-cyan-500 font-sans text-xs"
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-slate-300 mb-1 font-sans font-medium">
                New Evidentiary Weight
              </label>
              <select
                value={newWeight}
                onChange={(e) => setNewWeight(e.target.value)}
                className="w-full rounded bg-slate-950 border border-slate-700 p-2 text-white focus:outline-none focus:border-cyan-500 font-sans text-xs"
              >
                <option value="JUDICIAL_ACQUITTAL">JUDICIAL_ACQUITTAL (Presumption Restored)</option>
                <option value="JUDICIAL_CONVICTION">JUDICIAL_CONVICTION (Established Fact)</option>
              </select>
            </div>

            <div>
              <label className="block text-slate-300 mb-1 font-sans font-medium">
                Certified Court Order Source UUID
              </label>
              <input
                type="text"
                value={courtOrderSourceId}
                onChange={(e) => setCourtOrderSourceId(e.target.value)}
                required
                className="w-full rounded bg-slate-950 border border-slate-700 p-2 text-white focus:outline-none focus:border-cyan-500 font-mono text-xs"
              />
            </div>
          </div>

          <div>
            <label className="block text-slate-300 mb-1 font-sans font-medium">
              Active V2 Record Summary
            </label>
            <textarea
              rows={3}
              value={newSummary}
              onChange={(e) => setNewSummary(e.target.value)}
              required
              className="w-full rounded bg-slate-950 border border-slate-700 p-2 text-white focus:outline-none focus:border-cyan-500 font-sans text-xs"
            />
          </div>

          {error && (
            <div className="p-2.5 rounded bg-red-950 text-red-300 border border-red-800 text-xs">
              {error}
            </div>
          )}

          <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-800">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded text-slate-400 hover:text-white"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="px-5 py-2 rounded-lg bg-amber-500 hover:bg-amber-400 font-bold text-slate-950 flex items-center gap-2 disabled:opacity-50 transition-colors"
            >
              <ShieldCheck className="w-4 h-4" />
              <span>{submitting ? 'Committing...' : 'Commit Tombstone & Generate V2'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
