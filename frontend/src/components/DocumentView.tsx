import React, { useState } from 'react';
import { DocumentRecord } from '../types/evidence';
import { EvidentiaryBadge } from './EvidentiaryBadge';

const BOUNDARY = 'UNVERIFIED ALLEGATION / EPISTEMOLOGICAL BOUNDARY UNMET';

interface DocumentViewProps {
  document: DocumentRecord;
  onExportCertificate?: (sourceId: string) => void;
  onInitiateTombstone?: (document: DocumentRecord) => void;
}

export const DocumentView: React.FC<DocumentViewProps> = ({
  document,
  onExportCertificate,
  onInitiateTombstone,
}) => {
  const [copiedSha, setCopiedSha] = useState(false);
  const [copiedBlake, setCopiedBlake] = useState(false);

  const copyDigest = async (text: string, kind: 'sha' | 'blake') => {
    await navigator.clipboard.writeText(text);
    if (kind === 'sha') {
      setCopiedSha(true);
      window.setTimeout(() => setCopiedSha(false), 1200);
    } else {
      setCopiedBlake(true);
      window.setTimeout(() => setCopiedBlake(false), 1200);
    }
  };

  const isPreTrial = [
    'UNVERIFIED_INTELLIGENCE',
    'GD_REGISTERED',
    'FIR_COGNIZANCE',
    'SEIZURE_MANIFEST',
    'CHARGE_SHEET_ALLEGED',
  ].includes(document.evidentiary_status);
  const isUnverified = document.evidentiary_status === 'UNVERIFIED_INTELLIGENCE';

  return (
    <article className={`forensic-panel document-panel${document.is_superseded ? ' superseded' : ''}`}>
      {isUnverified && (
        <div className="boundary-watermark boundary-watermark-a" aria-hidden="true">
          {BOUNDARY}
        </div>
      )}

      {document.is_superseded && (
        <p className="panel-alert">
          SUPERSEDED HISTORICAL RECORD. {document.legal_justification || 'Superseded by certified judicial decree.'}
        </p>
      )}

      <header className="panel-head">
        <div>
          <p className="eyebrow">
            {document.source_type} / REF {document.document_reference}
          </p>
          <h2>{document.issuing_authority}</h2>
        </div>
        <EvidentiaryBadge status={document.evidentiary_status} />
      </header>

      {isPreTrial && (
        <p className="panel-alert catastrophic">
          PRE-TRIAL ASSERTION. Does not constitute judicial establishment of guilt. {BOUNDARY}
        </p>
      )}

      <dl className="meta-grid">
        <div>
          <dt>PUBLICATION</dt>
          <dd>{document.publication_date}</dd>
        </div>
        <div>
          <dt>INTAKE UTC</dt>
          <dd>{new Date(document.ingestion_timestamp).toISOString()}</dd>
        </div>
        <div>
          <dt>SOURCE ID</dt>
          <dd title={document.source_id}>{document.source_id}</dd>
        </div>
        <div>
          <dt>CUSTODIAN</dt>
          <dd title={document.uploaded_by_user_id}>{document.uploaded_by_user_id}</dd>
        </div>
      </dl>

      <section className="excerpt-block">
        <p className="eyebrow">EVIDENTIARY EXCERPT</p>
        <p>{document.excerpt}</p>
      </section>

      <section className="digest-block">
        <p className="eyebrow">WORM OBJECT LOCK / BYTE INTEGRITY ONLY</p>
        <div className="digest-row">
          <span>SHA256</span>
          <code>{document.sha256_hash}</code>
          <button type="button" onClick={() => copyDigest(document.sha256_hash, 'sha')}>
            {copiedSha ? 'COPIED' : 'COPY'}
          </button>
        </div>
        <div className="digest-row">
          <span>BLAKE3</span>
          <code>{document.blake3_hash}</code>
          <button type="button" onClick={() => copyDigest(document.blake3_hash, 'blake')}>
            {copiedBlake ? 'COPIED' : 'COPY'}
          </button>
        </div>
        <p className="scope-note">URI: {document.storage_uri}</p>
      </section>

      <footer className="action-row">
        <button type="button" onClick={() => onExportCertificate?.(document.source_id)}>
          REQUEST RAW DIGEST MANIFEST
        </button>
        {!document.is_superseded && (
          <button type="button" onClick={() => onInitiateTombstone?.(document)}>
            RECORD JUDICIAL TOMBSTONE
          </button>
        )}
      </footer>
    </article>
  );
};
