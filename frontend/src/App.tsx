import { FormEvent, useState } from 'react';

type VerificationState = 'idle' | 'loading' | 'verified' | 'offline';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api';
const BOUNDARY_WATERMARK = 'UNVERIFIED ALLEGATION / EPISTEMOLOGICAL BOUNDARY UNMET';

export default function App() {
  const [sourceId, setSourceId] = useState('');
  const [bearerToken, setBearerToken] = useState('');
  const [state, setState] = useState<VerificationState>('idle');
  const [manifest, setManifest] = useState('');
  const [fault, setFault] = useState('');

  const retrieveManifest = async (event: FormEvent) => {
    event.preventDefault();
    setState('loading');
    setManifest('');
    setFault('');

    try {
      const response = await fetch(
        `${API_BASE}/export/certificate/${encodeURIComponent(sourceId)}?format=markdown`,
        {
          headers: { Authorization: `Bearer ${bearerToken}` },
          cache: 'no-store',
        },
      );
      if (!response.ok) {
        throw new Error(`Gateway rejected verification request: HTTP ${response.status}`);
      }
      setManifest(await response.text());
      setState('verified');
    } catch (error) {
      setFault(error instanceof Error ? error.message : 'Verification transport failure');
      setState('offline');
    }
  };

  const downloadManifest = () => {
    const artifact = new Blob([manifest], { type: 'text/markdown;charset=utf-8' });
    const location = URL.createObjectURL(artifact);
    const anchor = document.createElement('a');
    anchor.href = location;
    anchor.download = `attilan_raw_digest_${sourceId || 'unknown'}.md`;
    anchor.click();
    URL.revokeObjectURL(location);
  };

  return (
    <main className="forensic-shell">
      <div className="boundary-watermark boundary-watermark-a" aria-hidden="true">{BOUNDARY_WATERMARK}</div>
      <div className="boundary-watermark boundary-watermark-b" aria-hidden="true">{BOUNDARY_WATERMARK}</div>

      <header className="masthead">
        <p>ATTILAN / KHULNA / CONTROLLED INTELLIGENCE LEDGER</p>
        <p>TERMINAL 01 · RAW DIGEST VERIFICATION ONLY</p>
      </header>

      <section className="forensic-grid" aria-labelledby="page-title">
        <div className="evidence-marker">A-65B</div>
        <div>
          <p className="eyebrow">EPISTEMIC BOUNDARY</p>
          <h1 id="page-title">UNSIGNED DIGEST<br />INSPECTION</h1>
        </div>
        <p className="scope-note">
          No certificate is constructed in this client. A gateway response can expose only raw SHA-256 and BLAKE3
          values. Hardware-HSM certification remains external to this interface.
        </p>
      </section>

      <section className="terminal-panel" aria-label="Raw digest retrieval">
        <form onSubmit={retrieveManifest} className="request-form">
          <label>
            <span>SOURCE UUID</span>
            <input
              required
              value={sourceId}
              onChange={(event) => setSourceId(event.target.value)}
              placeholder="00000000-0000-0000-0000-000000000000"
              spellCheck="false"
            />
          </label>
          <label>
            <span>VERIFIED BEARER TOKEN</span>
            <input
              required
              type="password"
              value={bearerToken}
              onChange={(event) => setBearerToken(event.target.value)}
              placeholder="JWT only; identity headers are rejected"
              spellCheck="false"
            />
          </label>
          <button type="submit" disabled={state === 'loading'}>
            {state === 'loading' ? 'QUERYING GATEWAY…' : 'REQUEST RAW DIGESTS'}
          </button>
        </form>

        <div className="terminal-status" aria-live="polite">
          <span>STATUS</span>
          <strong>
            {state === 'verified' ? 'GATEWAY RESPONSE RECEIVED / UNCERTIFIED' : 'NO CLAIM OF CERTIFICATION'}
          </strong>
        </div>

        {state === 'offline' && (
          <section className="offline-block" role="alert">
            <strong>X-01 OFFLINE / UNCERTIFIED</strong>
            <p>NO LOCAL CERTIFICATE, DIGEST, OR HARDWARE-SIGNATURE FALLBACK EXISTS.</p>
            <small>{fault}</small>
          </section>
        )}

        {state === 'verified' && (
          <section className="manifest-output" aria-label="Gateway raw digest manifest">
            <div>
              <span>UNSIGNED GATEWAY ARTIFACT</span>
              <button type="button" onClick={downloadManifest}>DOWNLOAD RESPONSE</button>
            </div>
            <pre>{manifest}</pre>
          </section>
        )}
      </section>

      <footer>
        <span>HASHING ESTABLISHES INTEGRITY OF BYTES, NOT TRUTH OF ALLEGATIONS.</span>
        <span>NO OFFLINE ASSERTION PATH.</span>
      </footer>
    </main>
  );
}
