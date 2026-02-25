export type DiagnosticRequest = {
  business_name: string;
  city: string;
  state: string;
  website?: string;
};

export type InterventionPlanItem = {
  step: number;
  category: string;
  action: string;
};

export interface ServiceIntelligence {
  detected_services: string[];
  missing_services: string[];
  schema_detected?: boolean;
}

export interface RevenueBreakdown {
  service: string;
  consults_per_month: string;
  revenue_per_case: string;
  annual_revenue_range: string;
}

export interface ConversionInfrastructure {
  online_booking?: boolean;
  contact_form?: boolean;
  phone_prominent?: boolean;
  mobile_optimized?: boolean;
  page_load_ms?: number;
}

export interface EvidenceItem {
  label: string;
  value: string;
}

export interface BriefExecutiveDiagnosis {
  constraint?: string;
  primary_leverage?: string;
  opportunity_profile?: { label?: string; why?: string } | string;
  modeled_revenue_upside?: string;
}

export interface BriefMarketPosition {
  revenue_band?: string;
  reviews?: string;
  local_avg?: string;
  market_density?: string;
}

export interface BriefCompetitiveContext {
  line1?: string;
  line2?: string;
  line3?: string;
}

export interface BriefDemandSignals {
  google_ads_line?: string;
  meta_ads_line?: string;
  paid_spend_estimate?: string;
  organic_visibility_tier?: string;
  organic_visibility_reason?: string;
  last_review_days_ago?: number;
  last_review_estimated?: boolean;
  review_velocity_30d?: number;
  review_velocity_estimated?: boolean;
}

export interface BriefCompetitiveServiceGap {
  type?: string;
  service?: string;
  competitor_name?: string;
  competitor_reviews?: number;
  lead_reviews?: number;
  distance_miles?: number;
  schema_missing?: boolean;
}

export interface BriefStrategicGap {
  service?: string;
  competitor_name?: string;
  competitor_reviews?: number;
  distance_miles?: number;
  market_density?: string;
}

export interface BriefHighTicketGaps {
  high_ticket_services_detected?: string[];
  missing_landing_pages?: string[];
  schema?: string;
  service_level_upside?: Array<{ service?: string; upside?: string }>;
}

export interface BriefRevenueUpsideCaptureGap {
  primary_service?: string;
  consult_low?: number;
  consult_high?: number;
  case_low?: number;
  case_high?: number;
  annual_low?: number;
  annual_high?: number;
}

export interface BriefConversionInfrastructure {
  online_booking?: boolean;
  contact_form?: boolean;
  phone_prominent?: boolean;
  mobile_optimized?: boolean;
  page_load_ms?: number;
}

/** Brief view model — full structure from build_revenue_brief_view_model */
export type Brief = {
  executive_diagnosis?: BriefExecutiveDiagnosis;
  executive_footnote?: string;
  market_position?: BriefMarketPosition;
  competitive_context?: BriefCompetitiveContext;
  competitive_service_gap?: BriefCompetitiveServiceGap | null;
  strategic_gap?: BriefStrategicGap | null;
  demand_signals?: BriefDemandSignals;
  high_ticket_gaps?: BriefHighTicketGaps;
  revenue_upside_capture_gap?: BriefRevenueUpsideCaptureGap | null;
  conversion_infrastructure?: BriefConversionInfrastructure;
  risk_flags?: string[];
  intervention_plan?: string[];
  intervention_fallback?: { strategic_frame?: string; tactical_levers?: string };
  evidence_bullets?: string[];
  [key: string]: unknown;
};

export type DiagnosticResponse = {
  lead_id: number;
  business_name: string;
  city: string;
  state?: string | null;
  opportunity_profile: string;
  constraint: string;
  primary_leverage: string;
  market_density: string;
  review_position: string;
  paid_status: string;
  intervention_plan: InterventionPlanItem[];
  brief?: Brief | null;
  service_intelligence?: ServiceIntelligence;
  revenue_breakdowns?: RevenueBreakdown[];
  conversion_infrastructure?: ConversionInfrastructure;
  risk_flags?: string[];
  evidence?: EvidenceItem[];
};

// ---------------------------------------------------------------------------
// Jobs
// ---------------------------------------------------------------------------

export type JobSubmitResponse = {
  job_id: string;
  status: string;
};

export type JobStatusResponse = {
  job_id: string;
  status: string;
  created_at: string;
  completed_at?: string | null;
  error?: string | null;
  diagnostic_id?: number | null;
};

// ---------------------------------------------------------------------------
// Diagnostics (SaaS layer)
// ---------------------------------------------------------------------------

export type DiagnosticListItem = {
  id: number;
  business_name: string;
  city: string;
  state?: string | null;
  place_id?: string | null;
  created_at: string;
  opportunity_profile?: string | null;
  constraint?: string | null;
  modeled_revenue_upside?: string | null;
};

export type DiagnosticListResponse = {
  items: DiagnosticListItem[];
  total: number;
  limit: number;
  offset: number;
};
