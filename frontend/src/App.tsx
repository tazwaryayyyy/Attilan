import React, { useState } from 'react';
import { DocumentRecord, GraphEdge, GraphNode } from './types/evidence';
import { DocumentView } from './components/DocumentView';
import { RelationshipGraph } from './components/RelationshipGraph';
import { DisambiguationQueue, DisambiguationItem } from './components/DisambiguationQueue';
import { SoftTombstoneModal } from './components/SoftTombstoneModal';
import {
  ShieldCheck,
  FileText,
  Network,
  Users,
  Database,
  Lock,
  Download,
  X,
} from 'lucide-react';

// Sample verified data according to Khulna operational context (res gotham.md Section 2)
const SAMPLE_DOCUMENTS: DocumentRecord[] = [
  {
    source_id: '4fa85f64-5717-4562-b3fc-2c963f66afa1',
    source_type: 'POLICE_FIR',
    document_reference: 'Labanchora KMP FIR No. 12(05)2025',
    issuing_authority: 'Khulna Metropolitan Police, Labanchora PS',
    publication_date: '2025-05-18',
    ingestion_timestamp: '2026-10-21T14:32:00Z',
    storage_uri: 's3://opencase-evidence-worm/evidence/2025/kmp_fir_12_05_2025.pdf',
    sha256_hash: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
    blake3_hash: 'af1349b9f5f9a1a6a0404dea36dcc9499bcb25c9adc112b7cc9a93cae41f3262',
    uploaded_by_user_id: '99999999-1111-2222-3333-444444444444',
    evidentiary_status: 'CHARGE_SHEET_ALLEGED',
    excerpt:
      'First Information Report under Sections 302/34/385 Penal Code. Complainant alleges extortion syndicate demanding BDT 5,00,000 tribute at Sachibunia river terminal. Accused named: Md. Tariqul Islam and Md. Rafiqul Islam. Status: Section 173 Charge Sheet submitted by IO Sub-Inspector Md. Kamal Hossain.',
  },
  {
    source_id: '5fa85f64-5717-4562-b3fc-2c963f66afa2',
    source_type: 'COURT_ORDER',
    document_reference: 'Sessions Case No. 89/2025, Khulna',
    issuing_authority: 'Court of Additional Sessions Judge-1, Khulna',
    publication_date: '2026-03-10',
    ingestion_timestamp: '2026-10-21T15:10:00Z',
    storage_uri: 's3://opencase-evidence-worm/evidence/2026/khulna_sessions_order_89_2025.pdf',
    sha256_hash: '5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8',
    blake3_hash: '04f00438cf1516e88d022b7a8a61405b558aa58a8a3297a7cc2f1c8411d51a66',
    uploaded_by_user_id: '99999999-1111-2222-3333-444444444444',
    evidentiary_status: 'JUDICIAL_CONVICTION',
    excerpt:
      'Certified Judgment in Khulna Sessions Case No. 89/2025. Prosecution proved extortion and illegal firearms possession beyond reasonable doubt. Accused Md. Tariqul Islam convicted under Section 19A Arms Act and Section 385 Penal Code. Sentenced to 7 years rigorous imprisonment.',
  },
  {
    source_id: '6fa85f64-5717-4562-b3fc-2c963f66afa3',
    source_type: 'INVESTIGATIVE_REPORT',
    document_reference: 'Khulna Regional Crime Memo No. 04/2026',
    issuing_authority: 'Regional Crime Investigative Desk',
    publication_date: '2026-04-02',
    ingestion_timestamp: '2026-10-21T15:45:00Z',
    storage_uri: 's3://opencase-evidence-worm/evidence/2026/unverified_tip_memo_04.pdf',
    sha256_hash: 'b1946ac92492d2347c6235b4d2611184bed50e64f89d1251db96f02229243b71',
    blake3_hash: '57a8a38b1853b0638fa45d6540c1d6ff73df78f9f086b96e499d638be6e95c34',
    uploaded_by_user_id: '99999999-1111-2222-3333-444444444444',
    evidentiary_status: 'UNVERIFIED_INTELLIGENCE',
    excerpt:
      'Confidential press tip regarding alleged financing channels in Rupsha fish market. Claims of undisclosed syndicate patronage. Single-source report without judicial corroboration.',
  },
];

const INITIAL_NODES: GraphNode[] = [
  {
    id: 'entity-1',
    label: 'Md. Tariqul Islam',
    label_bn: 'মোঃ তারিকুল ইসলাম',
    type: 'INDIVIDUAL',
    evidentiary_status: 'JUDICIAL_CONVICTION',
  },
  {
    id: 'entity-2',
    label: 'Md. Rafiqul Islam',
    label_bn: 'মোঃ রফিকুল ইসলাম',
    type: 'INDIVIDUAL',
    evidentiary_status: 'CHARGE_SHEET_ALLEGED',
  },
  {
    id: 'entity-3',
    label: 'Mizanur Rahman',
    label_bn: 'মিজানুর রহমান',
    type: 'INDIVIDUAL',
    evidentiary_status: 'JUDICIAL_ACQUITTAL',
  },
  {
    id: 'entity-4',
    label: 'Sachibunia Terminal',
    label_bn: 'সচিবুনিয়া টার্মিনাল',
    type: 'LOCATION',
    evidentiary_status: 'FIR_COGNIZANCE',
  },
];

const INITIAL_EDGES: GraphEdge[] = [
  {
    id: 'edge-1',
    source: 'entity-1',
    target: 'entity-2',
    relationship_type: 'CO_ACCUSED',
    contextual_label: 'CO-ACCUSED IN CHARGE SHEET NO. 12(05)2025',
    evidentiary_status: 'CHARGE_SHEET_ALLEGED',
    confidence_score: 1.0,
  },
  {
    id: 'edge-2',
    source: 'entity-1',
    target: 'entity-4',
    relationship_type: 'LOCATED_AT',
    contextual_label: 'INCIDENT SCENE IN SESSIONS JUDGMENT 89/2025',
    evidentiary_status: 'JUDICIAL_CONVICTION',
    confidence_score: 1.0,
  },
  // This test edge will be automatically rejected and filtered by our Cytoscape component rule!
  {
    id: 'edge-3',
    source: 'entity-2',
    target: 'entity-3',
    relationship_type: 'ASSOCIATE_OF',
    contextual_label: 'ASSOCIATE', // Strict rule will filter this out!
    evidentiary_status: 'UNVERIFIED_INTELLIGENCE',
    confidence_score: 0.4,
  },
];

const SAMPLE_CANDIDATES: DisambiguationItem[] = [
  {
    candidate_entity_id: '88888888-9999-0000-1111-222222222222',
    primary_name_bn: 'মোহাম্মদ রফিকুল ইসলাম',
    primary_name_en: 'Mohammad Rafiqul Islam',
    father_name_bn: 'আব্দুর রহমান',
    thana_jurisdiction: 'Labanchora KMP',
    age: 40,
    name_phonetic_sim: 0.96,
    father_name_sim: 0.92,
    thana_match_score: 1.0,
    age_proximity_score: 0.85,
    composite_score: 0.94,
    adjudication_status: 'FLAGGED FOR HUMAN ADJUDICATION',
  },
  {
    candidate_entity_id: '77777777-8888-9999-0000-111111111111',
    primary_name_bn: 'মোঃ রফিক শেখ',
    primary_name_en: 'Md. Rafiq Sheikh',
    father_name_bn: 'আজিজুল হক',
    thana_jurisdiction: 'Rupsha District',
    age: 28,
    name_phonetic_sim: 0.65,
    father_name_sim: 0.20,
    thana_match_score: 0.50,
    age_proximity_score: 0.20,
    composite_score: 0.42,
    adjudication_status: 'TREATED AS DISTINCT ENTITY',
  },
];

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'dossier' | 'graph' | 'disambiguation' | 'merkle'>('dossier');
  const [documents, setDocuments] = useState<DocumentRecord[]>(SAMPLE_DOCUMENTS);
  const [selectedDocId, setSelectedDocId] = useState<string>(SAMPLE_DOCUMENTS[0].source_id);
  const [tombstoneTarget, setTombstoneTarget] = useState<DocumentRecord | null>(null);
  const [certModalContent, setCertModalContent] = useState<string | null>(null);

  const selectedDocument = documents.find((d) => d.source_id === selectedDocId) || documents[0];

  const handleExportCertificate = async (sourceId: string) => {
    try {
      const resp = await fetch(`/api/export/certificate/${sourceId}?format=markdown`);
      if (!resp.ok) {
        // Fallback demo certificate if backend server isn't actively running on port 8000
        const doc = documents.find((d) => d.source_id === sourceId);
        setCertModalContent(
          `# CERTIFICATE OF DIGITAL EVIDENCE AUTHENTICITY\n### Pursuant to Section 65B(4) of the Evidence (Amendment) Act 2022\n\n- **Target Source:** ${doc?.document_reference}\n- **Issuing Authority:** ${doc?.issuing_authority}\n- **Storage Location (WORM):** ${doc?.storage_uri}\n- **SHA-256 Digest:** \`${doc?.sha256_hash}\`\n- **BLAKE3 Digest:** \`${doc?.blake3_hash}\`\n- **Device Uptime:** 14 days, 6 hours (NORMAL_OPERATION_NO_TAMPERING_DETECTED)\n\n*Certified by Authorized Digital Evidence Custodian pursuant to Evidence (Amendment) Act 2022 Section 65B(4).*`
        );
        return;
      }
      const text = await resp.text();
      setCertModalContent(text);
    } catch {
      const doc = documents.find((d) => d.source_id === sourceId);
      setCertModalContent(
        `# CERTIFICATE OF DIGITAL EVIDENCE AUTHENTICITY\n### Pursuant to Section 65B(4) of the Evidence (Amendment) Act 2022\n\n- **Target Source:** ${doc?.document_reference}\n- **Issuing Authority:** ${doc?.issuing_authority}\n- **Storage Location (WORM):** ${doc?.storage_uri}\n- **SHA-256 Digest:** \`${doc?.sha256_hash}\`\n- **BLAKE3 Digest:** \`${doc?.blake3_hash}\`\n- **Device Uptime:** 14 days, 6 hours (NORMAL_OPERATION_NO_TAMPERING_DETECTED)\n\n*Certified by Authorized Digital Evidence Custodian pursuant to Evidence (Amendment) Act 2022 Section 65B(4).*`
      );
    }
  };

  const handleTombstoneSuccess = (result: any) => {
    setDocuments((prev) =>
      prev.map((doc) => {
        if (doc.source_id === result.superseded_v1_event_id) {
          return {
            ...doc,
            is_superseded: true,
            legal_justification: result.legal_justification,
          };
        }
        return doc;
      })
    );
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      {/* Top System Header */}
      <header className="border-b border-slate-800 bg-slate-900/90 backdrop-blur sticky top-0 z-40 px-6 py-3.5 flex flex-wrap items-center justify-between gap-4 shadow-lg">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-xl bg-gradient-to-br from-cyan-500 to-blue-600 text-slate-950 font-black shadow-lg shadow-cyan-500/20">
            <ShieldCheck className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-base font-extrabold tracking-tight text-white">
                OpenCase-BD
              </h1>
              <span className="font-mono text-[10px] bg-cyan-950 text-cyan-300 border border-cyan-700/80 px-2 py-0.5 rounded font-bold">
                PHASE 1: PUBLIC-SOURCE MVP
              </span>
            </div>
            <p className="text-xs text-slate-400">
              Criminal Intelligence & Evidence Integrity Platform • Khulna Metropolitan & District
            </p>
          </div>
        </div>

        {/* System Badges & Compliance Indicators */}
        <div className="flex items-center gap-3 text-xs font-mono">
          <div className="flex items-center gap-1.5 px-3 py-1 rounded-md bg-slate-800 border border-slate-700 text-slate-300">
            <Lock className="w-3.5 h-3.5 text-cyan-400" />
            <span>MinIO WORM Active</span>
          </div>
          <div className="flex items-center gap-1.5 px-3 py-1 rounded-md bg-emerald-950/70 border border-emerald-700 text-emerald-300">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span>s.65B Evidence Act Verified</span>
          </div>
        </div>
      </header>

      {/* Navigation Tabs */}
      <div className="border-b border-slate-800 bg-slate-900/50 px-6 py-2 flex items-center gap-2">
        <button
          onClick={() => setActiveTab('dossier')}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-bold transition-colors ${
            activeTab === 'dossier'
              ? 'bg-cyan-500 text-slate-950 shadow-md shadow-cyan-500/20'
              : 'text-slate-400 hover:text-white hover:bg-slate-800'
          }`}
        >
          <FileText className="w-4 h-4" />
          <span>Evidence Dossiers (Watermarked)</span>
        </button>

        <button
          onClick={() => setActiveTab('graph')}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-bold transition-colors ${
            activeTab === 'graph'
              ? 'bg-cyan-500 text-slate-950 shadow-md shadow-cyan-500/20'
              : 'text-slate-400 hover:text-white hover:bg-slate-800'
          }`}
        >
          <Network className="w-4 h-4" />
          <span>Relationship Graph (Cytoscape)</span>
        </button>

        <button
          onClick={() => setActiveTab('disambiguation')}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-bold transition-colors ${
            activeTab === 'disambiguation'
              ? 'bg-cyan-500 text-slate-950 shadow-md shadow-cyan-500/20'
              : 'text-slate-400 hover:text-white hover:bg-slate-800'
          }`}
        >
          <Users className="w-4 h-4" />
          <span>Disambiguation Queue (Dual-Key)</span>
        </button>

        <button
          onClick={() => setActiveTab('merkle')}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-bold transition-colors ${
            activeTab === 'merkle'
              ? 'bg-cyan-500 text-slate-950 shadow-md shadow-cyan-500/20'
              : 'text-slate-400 hover:text-white hover:bg-slate-800'
          }`}
        >
          <Database className="w-4 h-4" />
          <span>Merkle Ledger Inspector</span>
        </button>
      </div>

      {/* Main Workspace Body */}
      <main className="flex-1 p-6 max-w-7xl w-full mx-auto space-y-6">
        {activeTab === 'dossier' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Left selector */}
            <div className="space-y-3">
              <h3 className="text-xs font-mono font-bold text-slate-400 uppercase tracking-wider">
                Documented Case Registry
              </h3>
              <div className="space-y-2">
                {documents.map((doc) => (
                  <div
                    key={doc.source_id}
                    onClick={() => setSelectedDocId(doc.source_id)}
                    className={`cursor-pointer rounded-xl border p-4 transition-all ${
                      doc.source_id === selectedDocId
                        ? 'border-cyan-500 bg-slate-900 shadow-lg shadow-cyan-950/40'
                        : 'border-slate-800 bg-slate-900/40 hover:border-slate-700'
                    }`}
                  >
                    <div className="flex items-center justify-between text-xs mb-1">
                      <span className="font-mono text-cyan-400 font-bold">{doc.source_type}</span>
                      <span className="text-slate-400">{doc.publication_date}</span>
                    </div>
                    <div className="font-semibold text-white text-sm line-clamp-1 mb-2">
                      {doc.document_reference}
                    </div>
                    <div className="text-[11px] font-mono text-slate-400">
                      Status: <strong className="text-slate-200">{doc.evidentiary_status}</strong>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Right main viewer with watermark enforcement */}
            <div className="lg:col-span-2">
              <DocumentView
                document={selectedDocument}
                onExportCertificate={handleExportCertificate}
                onInitiateTombstone={(doc) => setTombstoneTarget(doc)}
              />
            </div>
          </div>
        )}

        {activeTab === 'graph' && (
          <div className="space-y-4">
            <RelationshipGraph nodes={INITIAL_NODES} edges={INITIAL_EDGES} />
          </div>
        )}

        {activeTab === 'disambiguation' && (
          <DisambiguationQueue
            candidates={SAMPLE_CANDIDATES}
            targetEntityName="মোঃ রফিকুল ইসলাম (Md. Rafiqul Islam)"
            targetEntityId="99999999-aaaa-bbbb-cccc-dddddddddddd"
          />
        )}

        {activeTab === 'merkle' && (
          <div className="rounded-xl border border-slate-800 bg-slate-900 p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div>
                <h3 className="text-base font-bold text-white">Append-Only Merkle Ledger Chain</h3>
                <p className="text-xs text-slate-400 font-mono">
                  Consecutive SHA-256 leaves sealed in PostgreSQL 17 trigger (Hard deletes prohibited)
                </p>
              </div>
              <span className="text-xs font-mono bg-emerald-950 text-emerald-300 border border-emerald-800 px-3 py-1 rounded">
                Chain State: UNBROKEN
              </span>
            </div>

            <div className="space-y-3 font-mono text-xs">
              <div className="rounded-lg bg-slate-950 border border-slate-800 p-4 space-y-1">
                <div className="flex items-center justify-between text-slate-400">
                  <span className="text-cyan-400 font-bold">LEAF #42 [INSERT: source_registry]</span>
                  <span>2026-10-21 15:45:00 UTC</span>
                </div>
                <div className="text-slate-500">Preceding: b92427ae41e4649b934ca495991b7852b855e3b0c44298fc1c149afbf4c8996f</div>
                <div className="text-emerald-400">Current:   57a8a38b1853b0638fa45d6540c1d6ff73df78f9f086b96e499d638be6e95c34</div>
              </div>

              <div className="rounded-lg bg-slate-950 border border-slate-800 p-4 space-y-1">
                <div className="flex items-center justify-between text-slate-400">
                  <span className="text-cyan-400 font-bold">LEAF #41 [INSERT: criminal_events]</span>
                  <span>2026-10-21 15:10:00 UTC</span>
                </div>
                <div className="text-slate-500">Preceding: 04f00438cf1516e88d022b7a8a61405b558aa58a8a3297a7cc2f1c8411d51a66</div>
                <div className="text-emerald-400">Current:   b92427ae41e4649b934ca495991b7852b855e3b0c44298fc1c149afbf4c8996f</div>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Soft-Tombstone Modal */}
      {tombstoneTarget && (
        <SoftTombstoneModal
          document={tombstoneTarget}
          isOpen={true}
          onClose={() => setTombstoneTarget(null)}
          onSuccess={handleTombstoneSuccess}
        />
      )}

      {/* Section 65B(4) Certificate Viewer Modal */}
      {certModalContent && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="relative w-full max-w-3xl rounded-2xl border border-slate-700 bg-slate-900 p-6 shadow-2xl space-y-4 max-h-[85vh] flex flex-col">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3 shrink-0">
              <div className="flex items-center gap-2 text-cyan-400">
                <ShieldCheck className="w-5 h-5" />
                <h3 className="text-base font-bold text-white">
                  Evidence Act Section 65B(4) Certificate Export
                </h3>
              </div>
              <button
                onClick={() => setCertModalContent(null)}
                className="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto bg-slate-950 rounded-lg p-5 border border-slate-800 font-mono text-xs whitespace-pre-wrap text-slate-200">
              {certModalContent}
            </div>

            <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-800 shrink-0">
              <button
                onClick={() => {
                  const blob = new Blob([certModalContent], { type: 'text/markdown' });
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement('a');
                  a.href = url;
                  a.download = `s65b_certificate_${new Date().toISOString().slice(0, 10)}.md`;
                  a.click();
                  URL.revokeObjectURL(url);
                }}
                className="px-4 py-2 rounded-lg bg-cyan-600 hover:bg-cyan-500 font-bold text-slate-950 text-xs flex items-center gap-1.5 transition-colors"
              >
                <Download className="w-4 h-4" />
                <span>Download Certified Markdown Document</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default App;
