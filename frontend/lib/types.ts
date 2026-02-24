export type DiagnosticRequest = {
  business_name: string;
  city: string;
  website?: string;
};

export type InterventionPlanItem = {
  step: number;
  category: string;
  action: string;
};

export type DiagnosticResponse = {
  lead_id: number;
  business_name: string;
  city: string;
  opportunity_profile: string;
  constraint: string;
  primary_leverage: string;
  market_density: string;
  review_position: string;
  paid_status: string;
  intervention_plan: InterventionPlanItem[];
};
