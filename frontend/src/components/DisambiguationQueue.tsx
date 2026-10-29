import React, { useState, FormEvent } from 'react';

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
  sourceDocumentId: string;
  primaryBearerToken: string;
  secondaryBearerToken: string;
  onResolveSuccess?: (edgeData: unknown) => void;
}

const BOUNDARY = 'UNVERIFIED ALLEGATION / EPISTEMOLOGICAL BOUNDARY UNMET';

export const DisambiguationQueue: React.FC<DisambiguationQueueProps> = ({
  candidates,
  targetEntityName,
  targetEntityId,
  sourceDocumentId,
  primaryBearerToken,
  secondaryBearerToken,
  onResolveSuccess,
}) => {
  const [selectedCandidate, setSelectedCandidate] = useState<DisambiguationItem | null>(null);
  const [justificationLabel, setJustificationLabel] = useState(
    'MANUALLY CONFIRMED SAME PERSON VIA NID & COURT ORDER COMPARISON',
  );
  const [submitting, setSubmitting] = useState(false);
  const [fault, setFault] = useState('');
  const [ok, setOk] = useState('');

  const handleResolveConflict = async (event: FormEvent) => {
    event.preventDefault();
    if (!selectedCandidate) return;
    if (!primaryBearerToken || !secondaryBearerToken) {
      setFault('Two independently authenticated bearer tokens are required.');
      return;
    }

    setSubmitting(true);
    setFault('');
    setOk('');

    try {
      const response = await fetch('/api/entity/resolve_conflict', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${primaryBearerToken}`,
          'X-Dual-Control-Authorization': `Bearer ${secondaryBearerToken}`,
        },
        body: JSON.stringify({
          entity_a_id: targetEntityId,
          entity_b_id: selectedCandidate.candidate_entity_id,
          source_document_id: sourceDocumentId,
          contextual_label: justificationLabel,
          confidence_score: selectedCandidate.composite_score,
        }),
      });
      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || `HTTP ${response.status}`);
      }
      const data = await response.json();
      setOk(`SAME_AS edge recorded. UUIDs preserved: ${targetEntityId} ↔ ${selectedCandidate.candidate_entity_id}`);
      onResolveSuccess?.(data);
    } catch (err: unknown) {
      setFault(err instanceof Error ? err.message : 'Resolution rejected');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section className="forensic-panel" aria-label="Entity disambiguation queue">
      <div className="boundary-watermark boundary-watermark-a" aria-hidden="true">{BOUNDARY}</div>
      <header className="panel-head">
        <div>
          <p className="eyebrow">ZERO AUTO-MERGE</p>
          <h2>ENTITY DISAMBIGUATION QUEUE</h2>
          <p className="scope-note">Target: {targetEntityName}</p>
        </div>
        <span className="stamp">NO UUID MERGE</span>
      </header>

      <p className="panel-alert">
        High similarity creates a review queue only. Approval writes an explicit SAME_AS edge. Distinct entity UUIDs and provenance lineages remain unmerged.
      </p>

      <ul className="candidate-list">
        {candidates.map((cand) => {
          const selected = selectedCandidate?.candidate_entity_id === cand.candidate_entity_id;
          return (
            <li key={cand.candidate_entity_id}>
              <button
                type="button"
                className={selected ? 'candidate-row selected' : 'candidate-row'}
                onClick={() => setSelectedCandidate(cand)}
              >
                <div>
                  <strong>{cand.primary_name_bn}</strong>
                  <span>{cand.primary_name_en}</span>
                  <small>
                    PITA {cand.father_name_bn || 'UNKNOWN'} · THANA {cand.thana_jurisdiction || 'N/A'} · AGE{' '}
                    {cand.age ?? 'N/A'}
                  </small>
                </div>
                <div className="score-block">
                  <span>
                    PH {(cand.name_phonetic_sim * 100).toFixed(0)}% · FA {(cand.father_name_sim * 100).toFixed(0)}%
                  </span>
                  <strong>{(cand.composite_score * 100).toFixed(1)}%</strong>
                </div>
              </button>
            </li>
          );
        })}
      </ul>

      {selectedCandidate && (
        <form className="request-form stacked" onSubmit={handleResolveConflict}>
          <label>
            <span>CONTEXTUAL LEGAL CITATION</span>
            <input
              required
              value={justificationLabel}
              onChange={(e) => setJustificationLabel(e.target.value)}
              spellCheck={false}
            />
          </label>
          <p className="scope-note">
            Actor identities are extracted only from two verified bearer tokens. Operator UUID fields are rejected.
          </p>
          {fault && (
            <div className="offline-block" role="alert">
              <strong>X-01 REJECTED</strong>
              <p>{fault}</p>
            </div>
          )}
          {ok && <p className="panel-ok">{ok}</p>}
          <div className="action-row">
            <button type="button" onClick={() => setSelectedCandidate(null)}>
              CANCEL
            </button>
            <button type="submit" disabled={submitting}>
              {submitting ? 'WRITING EDGE…' : 'ENACT SAME_AS EDGE'}
            </button>
          </div>
        </form>
      )}
    </section>
  );
};
