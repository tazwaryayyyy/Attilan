import React from 'react';
import { EvidentiaryStatus } from '../types/evidence';

interface EvidentiaryBadgeProps {
  status: EvidentiaryStatus;
  showLegalBoundary?: boolean;
}

const CONFIG: Record<
  EvidentiaryStatus,
  { level: string; title: string; subtext: string; fault?: boolean }
> = {
  UNVERIFIED_INTELLIGENCE: {
    level: 'L0',
    title: 'UNVERIFIED ALLEGATION',
    subtext: 'Zero judicial weight. Excluded from suspect graphs.',
    fault: true,
  },
  GD_REGISTERED: {
    level: 'L1',
    title: 'STATUTORY POLICE RECORD',
    subtext: 'Pre-trial allegation. Not judicially proven.',
  },
  FIR_COGNIZANCE: {
    level: 'L1',
    title: 'STATUTORY POLICE RECORD',
    subtext: 'Pre-trial allegation. Not judicially proven.',
  },
  SEIZURE_MANIFEST: {
    level: 'L1',
    title: 'STATUTORY POLICE RECORD',
    subtext: 'Pre-trial allegation. Not judicially proven.',
  },
  CHARGE_SHEET_ALLEGED: {
    level: 'L2',
    title: 'FORMAL PROBABLE CAUSE',
    subtext: 'CrPC s.173 report. Prima facie only.',
  },
  JUDICIAL_CONVICTION: {
    level: 'L3',
    title: 'JUDICIAL CONVICTION',
    subtext: 'Established by final court judgment.',
  },
  JUDICIAL_ACQUITTAL: {
    level: 'L3',
    title: 'JUDICIAL ACQUITTAL',
    subtext: 'Presumption of innocence restored.',
  },
};

export const EvidentiaryBadge: React.FC<EvidentiaryBadgeProps> = ({
  status,
  showLegalBoundary = false,
}) => {
  const config = CONFIG[status];
  return (
    <div className="badge-stack">
      <span className={config.fault ? 'forensic-badge fault' : 'forensic-badge'}>
        [{config.level}] {config.title}
      </span>
      {showLegalBoundary && <small className="scope-note">{config.subtext}</small>}
    </div>
  );
};
