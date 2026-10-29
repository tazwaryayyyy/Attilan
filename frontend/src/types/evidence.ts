export type EvidentiaryStatus =
  | 'UNVERIFIED_INTELLIGENCE'
  | 'GD_REGISTERED'
  | 'FIR_COGNIZANCE'
  | 'SEIZURE_MANIFEST'
  | 'CHARGE_SHEET_ALLEGED'
  | 'JUDICIAL_CONVICTION'
  | 'JUDICIAL_ACQUITTAL';

export interface DocumentRecord {
  source_id: string;
  source_type: 'COURT_ORDER' | 'POLICE_FIR' | 'GAZETTE' | 'INVESTIGATIVE_REPORT';
  document_reference: string;
  issuing_authority: string;
  publication_date: string;
  ingestion_timestamp: string;
  storage_uri: string;
  sha256_hash: string;
  blake3_hash: string;
  uploaded_by_user_id: string;
  evidentiary_status: EvidentiaryStatus;
  excerpt: string;
  is_superseded?: boolean;
  legal_justification?: string;
}

export interface GraphNode {
  id: string;
  label: string;
  label_bn?: string;
  type: 'INDIVIDUAL' | 'ORGANIZATION' | 'INCIDENT' | 'LOCATION';
  evidentiary_status: EvidentiaryStatus;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  relationship_type: string;
  contextual_label: string;
  evidentiary_status: EvidentiaryStatus;
  confidence_score: number;
}
