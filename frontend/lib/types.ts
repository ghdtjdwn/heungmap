export type PlannerType =
  | "local_government" | "public_agency" | "company" | "event_agency"
  | "performance_agency" | "venue_operator" | "club_or_group"
  | "independent_planner" | "artist" | "other";

export type PlanningStage =
  | "idea" | "research" | "budget_application" | "venue_search"
  | "booking" | "marketing_preparation" | "ticket_sales" | "final_preparation";

export type ScheduleMode = "fixed" | "candidates" | "recommend" | "unknown";
export type RegionMode = "fixed" | "candidates" | "recommend" | "unknown";

export type RegionRef = {
  area_code: string;
  sigungu_code?: string;
  display_name: string;
};

export type DateRange = { start_date: string; end_date: string };

export type Venue = {
  venue_id?: string;
  name: string;
  address?: string;
  coordinates?: { latitude: number; longitude: number };
  capacity?: number;
  indoor_outdoor?: "indoor" | "outdoor" | "mixed" | "unknown";
  accessibility_summary?: string;
};

export type EventDraft = {
  event_id: string;
  working_title?: string;
  planner_type: PlannerType | "";
  planning_stage: PlanningStage | "";
  event_type: "festival" | "local_event" | "concert" | "club_performance" | "exhibition" | "conference" | "experience" | "market" | "other" | "";
  event_type_other?: string;
  purpose: "profit" | "regional_revitalization" | "tourism" | "brand" | "fandom" | "community" | "culture" | "education" | "social_contribution" | "other" | "";
  purpose_other?: string;
  theme_keywords: string[];
  schedule_selection_mode: ScheduleMode;
  start_date?: string;
  end_date?: string;
  date_candidates?: DateRange[];
  region_selection_mode: RegionMode;
  region?: RegionRef;
  region_candidates?: RegionRef[];
  venue?: Venue;
  indoor_outdoor: "indoor" | "outdoor" | "mixed" | "undecided";
  target_audience: string[];
  target_audience_other?: string;
  target_attendance?: number;
  ticket_type: "free" | "paid" | "mixed" | "undecided";
  budget_min_krw?: number;
  budget_max_krw?: number;
  fixed_constraints: string[];
  other_notes?: string;
};

export type PlanningDetails = {
  team_size?: number;
  decision_makers?: number;
  experience_level: "unknown" | "none" | "one_or_two" | "three_to_five" | "six_plus";
  decision_deadline: string;
  recommendation_goals: string[];
  detail_level: "quick" | "standard" | "detailed";
  main_concern: string;
  event_summary: string;
  event_frequency: "unknown" | "new" | "repeat" | "annual";
  event_format: "unknown" | "offline" | "online" | "hybrid";
  access_type: "unknown" | "public" | "invite" | "members";
  success_metric: string;
  minimum_success_attendance?: number;
  maximum_concurrent_attendance?: number;
  audience_interests: string;
  visit_motivation: string;
  dropout_reason: string;
  expected_stay_hours?: number;
  required_languages: string[];
  audience_accessibility_needs: string;
  daily_hours: string;
  setup_rehearsal_teardown: string;
  rain_or_weather_fallback: string;
  preferred_daytime: "unknown" | "day" | "evening" | "late_night" | "flexible";
  competing_event_tolerance: "unknown" | "avoid" | "some" | "acceptable";
  venue_type: string;
  venue_search_source?: SourceRef;
  address_search_source?: SourceRef;
  seating_mode: "unknown" | "seated" | "standing" | "mixed";
  venue_area_sqm?: number;
  parking_spaces?: number;
  transit_plan: string;
  facility_plan: string;
  program_outline: string;
  performer_partner_plan: string;
  program_priority: string;
  ticket_price_min_krw?: number;
  ticket_price_max_krw?: number;
  ticket_sales_target?: number;
  ticket_sales_channels: string;
  refund_policy: string;
  secured_budget_krw?: number;
  budget_breakdown: string;
  expected_revenue_krw?: number;
  break_even_attendance?: number;
  marketing_channels: string[];
  marketing_start_date: string;
  marketing_budget_krw?: number;
  marketing_kpi: string;
  operation_plan: string;
  staff_count?: number;
  queue_plan: string;
  technical_fallback: string;
  transport_accommodation_plan: string;
  local_partnership_plan: string;
  safety_plan: string;
  permits_and_insurance: string;
  cancellation_rule: string;
  accessibility_plan: string;
  sustainability_plan: string;
  past_event_summary: string;
  flexible_options: string;
  priority_criteria: string[];
  risk_tolerance: "unknown" | "low" | "medium" | "high";
  requested_alternatives: number;
  requested_decisions: string;
};

export type DraftVersion = {
  version: number;
  created_at: string;
  summary: string;
  event: EventDraft;
  details: PlanningDetails;
  analysis_id: string;
};

export type PlannerAnalysisRequest = {
  contract_version: "0.1.0";
  client_request_id: string;
  event_draft: EventDraft;
  requested_outputs: ("prediction" | "nearby_places" | "rule_recommendations")[];
};

export type SourceRef = {
  source_id: string;
  source_type: string;
  provider_name: string;
  dataset_name: string;
  source_record_id?: string;
  retrieved_at: string;
  limitation?: string;
};

export type VenueSearchItem = {
  venue: Venue;
  category?: string;
  content_type_id?: string;
  source: SourceRef;
};

export type VenueSearchResponse = {
  items: VenueSearchItem[];
  meta: { contract_version: "0.1.0"; generated_at: string; request_id: string; warnings?: string[] };
};

export type AddressSearchItem = {
  address_name: string;
  road_address_name?: string;
  jibun_address_name?: string;
  building_name?: string;
  coordinates: { latitude: number; longitude: number };
  source: SourceRef;
};

export type AddressSearchResponse = {
  items: AddressSearchItem[];
  meta: { contract_version: "0.1.0"; generated_at: string; request_id: string; warnings?: string[] };
};

export type Evidence = {
  evidence_id: string;
  value_type: "user_input" | "verified_fact" | "derived_value" | "model_prediction" | "assumption";
  label: string;
  display_value: string;
  numeric_value?: number;
  unit?: string;
  as_of?: string;
  confidence?: "low" | "medium" | "high";
  source_refs: string[];
  limitation?: string;
};

export type Prediction = {
  status: "available";
  prediction_id: string;
  event_id: string;
  prediction_type: "relative_demand_score";
  as_of: string;
  target_start_date: string;
  target_end_date: string;
  target_region?: RegionRef;
  primary_metric: { metric_name: "relative_demand_score"; unit: "index_0_100"; value: number };
  indicators?: { demand_score?: number; congestion_level?: string; ticket_demand_level?: string };
  confidence: "low" | "medium" | "high";
  data_sufficiency: "limited" | "sufficient";
  method: "rules" | "machine_learning" | "external_benchmark";
  model_version: string;
  factors: { factor_id: string; label: string; direction: "up" | "down" | "neutral" | "unknown"; importance?: number; explanation: string; evidence_refs: string[] }[];
  evidence: Evidence[];
  sources: SourceRef[];
  limitations: string[];
  out_of_distribution: boolean;
  fallback_used: boolean;
  created_at: string;
  is_mock: boolean;
} | {
  status: "unavailable";
  event_id: string;
  reason_code: string;
  message: string;
  as_of: string;
  sources: SourceRef[];
  limitations: string[];
  retryable: boolean;
  is_mock: boolean;
};

export type NearbyResult = {
  status: "available";
  items: {
    place_id: string;
    place_type: string;
    name: string;
    address?: string;
    distance_m?: number;
    sources: SourceRef[];
  }[];
  radius_m: number;
  is_mock: boolean;
} | {
  status: "unavailable";
  reason_code: string;
  message: string;
  retryable: boolean;
  is_mock: boolean;
};

export type Recommendation = {
  recommendation_id: string;
  category: "demand" | "venue" | "budget" | "marketing" | "operation" | "risk" | "accessibility" | "tourism";
  priority: "low" | "medium" | "high";
  title: string;
  action: string;
  reason: string;
  evidence_refs: string[];
  requires_human_review: boolean;
};

export type PlannerAnalysisResponse = {
  analysis_id: string;
  contract_version: "0.1.0";
  request_snapshot: EventDraft;
  prediction: Prediction;
  nearby_places: NearbyResult;
  evidence: Evidence[];
  rule_recommendations: Recommendation[];
  meta: { contract_version: "0.1.0"; generated_at: string; request_id: string; warnings?: string[] };
};

export type DraftRecord = {
  id: string;
  created_at: string;
  updated_at: string;
  status: "draft" | "analyzed";
  current_step: number;
  version: number;
  event: EventDraft;
  details: PlanningDetails;
  analysis?: PlannerAnalysisResponse;
  recommendation?: StructuredPlanningRecommendation;
  recommendation_meta?: PlannerRecommendationMeta;
  history: DraftVersion[];
};

export type StructuredPlanningRecommendation = {
  schema_version: "1.0";
  prompt_version: "planner-recommendation-1.0";
  generation_mode: "rule_fallback" | "llm";
  generated_at: string;
  executive_summary: string;
  priorities: {
    id: string;
    priority: "low" | "medium" | "high";
    category: "demand" | "venue" | "budget" | "marketing" | "operation" | "risk" | "accessibility" | "tourism";
    title: string;
    action: string;
    reason: string;
    evidence_refs: string[];
    assumptions: string[];
    predicted_impact: string;
    confidence: "low" | "medium" | "high";
    cost_level: "unknown" | "low" | "medium" | "high";
    difficulty: "easy" | "moderate" | "hard" | "needs_review";
    deadline: string | null;
    dependencies: string[];
    risks: string[];
    requires_human_review: true;
  }[];
  alternatives: { id: string; title: string; changes: string[]; verify: string[] }[];
  roadmap: { phase: string; actions: string[] }[];
  missing_information: string[];
  limitations: string[];
};

export type PlannerRecommendationMeta = {
  contract_version: "0.1.0";
  generated_at: string;
  request_id: string;
  provider: string;
  model: string;
  prompt_version: "planner-recommendation-1.0";
  is_fallback: boolean;
  warning?: string;
};

export type PlannerRecommendationRequest = {
  contract_version: "0.1.0";
  client_request_id: string;
  analysis_id: string;
  planning_context: PlanningContext;
  rule_recommendations: Recommendation[];
  requested_alternatives: number;
};

export type PlannerRecommendationResponse = {
  recommendation: StructuredPlanningRecommendation;
  meta: Omit<PlannerRecommendationMeta, "is_fallback" | "warning">;
};

export type ContextValue = {
  value: unknown;
  value_type: "user_input" | "verified_fact" | "derived_value" | "model_prediction" | "assumption";
  source: string;
  unit?: string;
  confidence?: "low" | "medium" | "high";
  limitation?: string;
};

export type PlanningContext = {
  context_version: "1.0";
  generated_at: string;
  planner_profile: Record<string, ContextValue>;
  event_brief: Record<string, ContextValue>;
  target_audience: Record<string, ContextValue>;
  schedule_candidates: Record<string, ContextValue>;
  location_and_venue_candidates: Record<string, ContextValue>;
  program_and_performers: Record<string, ContextValue>;
  ticket_and_budget: Record<string, ContextValue>;
  marketing_and_operations: Record<string, ContextValue>;
  safety_accessibility_sustainability: Record<string, ContextValue>;
  prediction_result: Record<string, ContextValue>;
  tourism_and_local_evidence: Record<string, ContextValue>;
  fixed_constraints: string[];
  flexible_options: string[];
  missing_information: string[];
  requested_decisions: string[];
  generation: {
    mode: "context_only";
    llm_used: false;
    model_mock: true;
    limitation: string;
  };
};

export type Problem = {
  title?: string;
  detail?: string;
  code?: string;
  status?: number;
  retryable?: boolean;
  trace_id?: string;
  field_errors?: { field: string; message: string }[];
};
