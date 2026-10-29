import React from 'react';
import { EvidentiaryStatus } from '../types/evidence';
import { ShieldAlert, ShieldCheck, Scale, FileText, AlertCircle } from 'lucide-react';

interface EvidentiaryBadgeProps {
  status: EvidentiaryStatus;
  size?: 'sm' | 'md' | 'lg';
  showLegalBoundary?: boolean;
}

export const EvidentiaryBadge: React.FC<EvidentiaryBadgeProps> = ({
  status,
  size = 'md',
  showLegalBoundary = false,
}) => {
  const getBadgeConfig = (status: EvidentiaryStatus) => {
    switch (status) {
      case 'UNVERIFIED_INTELLIGENCE':
        return {
          level: 'LEVEL 0',
          title: 'UNVERIFIED ALLEGATION',
          subtext: 'Zero judicial weight. Excluded from suspect graphs.',
          bg: 'bg-slate-800/90 text-slate-300 border-slate-600',
          dot: 'bg-slate-400',
          icon: ShieldAlert,
        };
      case 'GD_REGISTERED':
      case 'FIR_COGNIZANCE':
      case 'SEIZURE_MANIFEST':
        return {
          level: 'LEVEL 1',
          title: 'STATUTORY POLICE RECORD',
          subtext: 'Pre-trial allegation: Not judicially examined or proven.',
          bg: 'bg-amber-950/80 text-amber-300 border-amber-600/80',
          dot: 'bg-amber-400 animate-pulse',
          icon: AlertCircle,
        };
      case 'CHARGE_SHEET_ALLEGED':
        return {
          level: 'LEVEL 2',
          title: 'FORMAL PROBABLE CAUSE REPORT',
          subtext: 'CrPC s.173 police charge: Prima facie finding, not conviction.',
          bg: 'bg-blue-950/80 text-blue-300 border-blue-600/80',
          dot: 'bg-blue-400',
          icon: FileText,
        };
      case 'JUDICIAL_CONVICTION':
        return {
          level: 'LEVEL 3',
          title: 'JUDICIAL CONVICTION',
          subtext: 'Established judicial fact pursuant to final court judgment.',
          bg: 'bg-emerald-950/80 text-emerald-300 border-emerald-500/80',
          dot: 'bg-emerald-400',
          icon: ShieldCheck,
        };
      case 'JUDICIAL_ACQUITTAL':
        return {
          level: 'LEVEL 3',
          title: 'JUDICIAL ACQUITTAL',
          subtext: 'Presumption of innocence fully restored by Court Order.',
          bg: 'bg-zinc-900 text-teal-300 border-teal-400/80',
          dot: 'bg-teal-300',
          icon: Scale,
        };
    }
  };

  const config = getBadgeConfig(status);
  const Icon = config.icon;

  const sizeClasses = {
    sm: 'text-xs px-2 py-0.5 gap-1.5',
    md: 'text-xs px-3 py-1.5 gap-2 font-semibold',
    lg: 'text-sm px-4 py-2 gap-2.5 font-bold',
  };

  return (
    <div className="inline-flex flex-col gap-1">
      <div
        className={`inline-flex items-center rounded-md border tracking-wide uppercase transition-all shadow-sm ${config.bg} ${sizeClasses[size]}`}
      >
        <span className={`w-2 h-2 rounded-full ${config.dot}`} />
        <Icon className="w-3.5 h-3.5 shrink-0" />
        <span className="font-mono text-[10px] opacity-75 mr-1">[{config.level}]</span>
        <span>{config.title}</span>
      </div>

      {showLegalBoundary && (
        <span className="text-[11px] font-mono text-slate-400 pl-1">
          {config.subtext}
        </span>
      )}
    </div>
  );
};
