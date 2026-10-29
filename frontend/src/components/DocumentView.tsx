import React, { useState } from 'react';
import { DocumentRecord } from '../types/evidence';
import { EvidentiaryBadge } from './EvidentiaryBadge';
import {
  FileCheck2,
  Lock,
  Copy,
  Check,
  ShieldCheck,
  AlertTriangle,
  History,
} from 'lucide-react';

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

  const copyToClipboard = (text: string, type: 'sha' | 'blake') => {
    navigator.clipboard.writeText(text);
    if (type === 'sha') {
      setCopiedSha(true);
      setTimeout(() => setCopiedSha(false), 1500);
    } else {
      setCopiedBlake(true);
      setTimeout(() => setCopiedBlake(false), 1500);
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
    <div
      className={`relative w-full border bg-zinc-950 p-4 text-zinc-100 rounded-none transition-none ${
        document.is_superseded
          ? 'border-amber-600/80 bg-zinc-950'
          : 'border-zinc-800'
      }`}
    >
      {/* SVG Repeating Diagonal Watermark Overlay for Unverified Intelligence */}
      {isUnverified && (
        <div
          className="pointer-events-none absolute inset-0 z-20 overflow-hidden opacity-25 select-none"
          style={{
            backgroundImage: `url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='380' height='160' viewBox='0 0 380 160'><text x='50%' y='50%' fill='%23ef4444' font-size='10.5' font-family='monospace' font-weight='900' letter-spacing='2px' transform='rotate(-25 190 80)' text-anchor='middle'>PRE-TRIAL ALLEGATION - NOT JUDICIALLY PROVEN</text></svg>")`,
            backgroundRepeat: 'repeat',
          }}
          aria-hidden="true"
        />
      )}

      {/* Superseded Record Banner (Soft-Tombstone Audit Notice) */}
      {document.is_superseded && (
        <div className="mb-3 border border-amber-600 bg-amber-950/90 p-2 text-xs text-amber-200 rounded-none flex items-center justify-between">
          <div className="flex items-center gap-2">
            <History className="h-4 w-4 text-amber-400 shrink-0" />
            <span className="font-sans font-medium">
              <strong className="font-mono text-amber-300">SUPERSEDED HISTORICAL RECORD (SOFT-TOMBSTONED):</strong>{' '}
              {document.legal_justification || 'Superseded by subsequent certified judicial decree.'}
            </span>
          </div>
          <span className="font-mono text-[10px] bg-amber-900 px-1.5 py-0.5 border border-amber-500 text-amber-200 shrink-0">
            AUDIT TRAIL IMMUTABLE
          </span>
        </div>
      )}

      {/* Header Bar */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-zinc-800 pb-3 mb-3">
        <div className="flex flex-col gap-0.5">
          <div className="flex items-center gap-2">
            <span className="font-mono text-[11px] font-bold text-zinc-400 tracking-wider uppercase">
              {document.source_type}
            </span>
            <span className="text-zinc-600 font-mono">/</span>
            <span className="font-mono text-[11px] text-zinc-300">
              REF: {document.document_reference}
            </span>
          </div>
          <h2 className="text-sm font-semibold tracking-tight text-zinc-100 uppercase">
            {document.issuing_authority}
          </h2>
        </div>

        <div className="flex items-center gap-2">
          <EvidentiaryBadge
            status={document.evidentiary_status}
            size="md"
            showLegalBoundary={false}
          />
        </div>
      </div>

      {/* Mandatory Statutory Notice for Pre-Trial Allegations */}
      {isPreTrial && (
        <div className="mb-3 border-l-2 border-red-600 bg-zinc-900/90 p-2 flex items-center gap-2 text-[11px] text-red-300 rounded-none">
          <AlertTriangle className="h-3.5 w-3.5 text-red-400 shrink-0" />
          <p className="font-mono">
            SECTION 65B STATUTORY CAVEAT: Pre-trial assertion. Does not constitute judicial establishment of guilt.
          </p>
        </div>
      )}

      {/* Technical Metadata Ledger Bar */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2 border border-zinc-800 bg-zinc-900/70 p-2 text-[11px] font-mono text-zinc-400 mb-3">
        <div>
          <span className="text-zinc-500 block text-[9px] uppercase">Publication Date</span>
          <span className="text-zinc-200">{document.publication_date}</span>
        </div>
        <div>
          <span className="text-zinc-500 block text-[9px] uppercase">Intake Timestamp (UTC)</span>
          <span className="text-zinc-200">{new Date(document.ingestion_timestamp).toISOString()}</span>
        </div>
        <div>
          <span className="text-zinc-500 block text-[9px] uppercase">Source ID</span>
          <span className="text-zinc-200 truncate block" title={document.source_id}>
            {document.source_id.slice(0, 13)}...
          </span>
        </div>
        <div>
          <span className="text-zinc-500 block text-[9px] uppercase">Ingestion Custodian</span>
          <span className="text-zinc-200 truncate block" title={document.uploaded_by_user_id}>
            {document.uploaded_by_user_id.slice(0, 13)}...
          </span>
        </div>
      </div>

      {/* Document Excerpt / Evidentiary Text Body */}
      <div className="relative border border-zinc-800 bg-zinc-900/40 p-3 mb-3">
        <div className="text-[10px] font-mono uppercase tracking-wider text-zinc-500 border-b border-zinc-800/80 pb-1 mb-2">
          Evidentiary Intake Excerpt
        </div>
        <div className="font-sans text-xs leading-relaxed text-zinc-200 selection:bg-zinc-800">
          {document.excerpt}
        </div>
      </div>

      {/* Cryptographic WORM Provenance Block */}
      <div className="border border-zinc-800 bg-zinc-900/80 p-3 space-y-2 mb-3">
        <div className="flex items-center justify-between border-b border-zinc-800 pb-1.5 text-[11px] font-mono">
          <div className="flex items-center gap-1.5 text-zinc-300 font-bold">
            <Lock className="h-3.5 w-3.5 text-zinc-400" />
            <span>WORM OBJECT LOCK PROVENANCE (S3 COMPLIANCE MODE)</span>
          </div>
          <span className="text-[10px] text-emerald-400 border border-emerald-600/40 bg-emerald-950/40 px-1.5 py-0.5 flex items-center gap-1">
            <ShieldCheck className="h-3 w-3" /> RETENTION 3650D ACTIVE
          </span>
        </div>

        {/* SHA-256 Hash Row */}
        <div className="flex items-center justify-between gap-2 text-[11px] font-mono bg-zinc-950 px-2 py-1.5 border border-zinc-800">
          <div className="flex items-center gap-2 truncate">
            <span className="text-zinc-500 shrink-0 font-bold">SHA256:</span>
            <span className="text-zinc-200 truncate">{document.sha256_hash}</span>
          </div>
          <button
            onClick={() => copyToClipboard(document.sha256_hash, 'sha')}
            className="text-zinc-400 hover:text-zinc-100 p-1 shrink-0"
            title="Copy SHA-256 Digest"
          >
            {copiedSha ? <Check className="h-3 w-3 text-emerald-400" /> : <Copy className="h-3 w-3" />}
          </button>
        </div>

        {/* BLAKE3 Hash Row */}
        <div className="flex items-center justify-between gap-2 text-[11px] font-mono bg-zinc-950 px-2 py-1.5 border border-zinc-800">
          <div className="flex items-center gap-2 truncate">
            <span className="text-zinc-500 shrink-0 font-bold">BLAKE3:</span>
            <span className="text-zinc-200 truncate">{document.blake3_hash}</span>
          </div>
          <button
            onClick={() => copyToClipboard(document.blake3_hash, 'blake')}
            className="text-zinc-400 hover:text-zinc-100 p-1 shrink-0"
            title="Copy BLAKE3 Digest"
          >
            {copiedBlake ? <Check className="h-3 w-3 text-emerald-400" /> : <Copy className="h-3 w-3" />}
          </button>
        </div>

        <div className="text-[10px] font-mono text-zinc-500 pt-0.5 truncate">
          URI: <span className="text-zinc-400">{document.storage_uri}</span>
        </div>
      </div>

      {/* Action Footer */}
      <div className="flex items-center justify-between pt-2 border-t border-zinc-800">
        <button
          onClick={() => onExportCertificate?.(document.source_id)}
          className="inline-flex items-center gap-1.5 bg-zinc-100 hover:bg-white text-zinc-950 font-bold px-3 py-1.5 text-xs transition-none rounded-none"
        >
          <FileCheck2 className="h-3.5 w-3.5" />
          <span>EXPORT SECTION 65B(4) CERTIFICATE</span>
        </button>

        {!document.is_superseded && (
          <button
            onClick={() => onInitiateTombstone?.(document)}
            className="inline-flex items-center gap-1.5 border border-zinc-700 bg-zinc-900 hover:bg-zinc-800 text-zinc-300 hover:text-amber-300 px-3 py-1.5 text-xs transition-none rounded-none"
          >
            <History className="h-3.5 w-3.5" />
            <span>RECORD JUDICIAL TOMBSTONE</span>
          </button>
        )}
      </div>
    </div>
  );
};
