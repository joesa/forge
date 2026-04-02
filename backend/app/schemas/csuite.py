"""
Pydantic v2 schemas for C-Suite executive agent outputs.

Each schema validates the structured output from one of the 8 executive
analyst agents. Used by Gate G2 to ensure every agent returns well-formed
data before the pipeline continues.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


# ── CEO ──────────────────────────────────────────────────────────────


class MarketOpportunity(BaseModel):
    """TAM / SAM / SOM breakdown."""

    tam: str = Field(description="Total Addressable Market")
    sam: str = Field(description="Serviceable Addressable Market")
    som: str = Field(description="Serviceable Obtainable Market")


class CEOAnalysis(BaseModel):
    """CEO agent output — business strategy analysis."""

    market_opportunity: MarketOpportunity
    business_model: str = Field(
        description="SaaS / marketplace / usage-based / hybrid"
    )
    revenue_strategy: str
    competitive_moat: str
    go_to_market_summary: str


# ── CTO ──────────────────────────────────────────────────────────────


class TechStackRecommendation(BaseModel):
    """Technology stack with reasoning."""

    frontend: str
    backend: str
    database: str
    hosting: str
    reasoning: str


class CTOAnalysis(BaseModel):
    """CTO agent output — technical architecture analysis."""

    tech_stack_recommendation: TechStackRecommendation
    api_design_principles: list[str] = Field(min_length=1)
    scalability_approach: str
    infrastructure_choices: str
    technical_risks: list[str] = Field(default_factory=list)
    build_vs_buy_decisions: list[str] = Field(default_factory=list)


# ── CDO (Chief Design Officer) ───────────────────────────────────────


class CDOAnalysis(BaseModel):
    """CDO agent output — design & UX analysis."""

    ux_principles: list[str] = Field(min_length=1)
    design_system_recommendation: str
    brand_identity: str
    color_palette_suggestion: list[str] = Field(min_length=1)
    typography_choices: list[str] = Field(min_length=1)
    user_journey_map: list[str] = Field(min_length=1)


# ── CMO (Chief Marketing Officer) ───────────────────────────────────


class CMOAnalysis(BaseModel):
    """CMO agent output — go-to-market analysis."""

    gtm_strategy: str
    target_customer_profile: str
    growth_channels: list[str] = Field(min_length=1)
    positioning_statement: str
    messaging_framework: str
    acquisition_loop: str


# ── CPO (Chief Product Officer) ──────────────────────────────────────


class UserStory(BaseModel):
    """A single user story."""

    title: str
    description: str
    priority: str = Field(description="must / should / could / wont")


class CPOAnalysis(BaseModel):
    """CPO agent output — product strategy analysis."""

    feature_prioritization: dict[str, list[str]] = Field(
        description="MoSCoW: {must: [], should: [], could: [], wont: []}"
    )
    mvp_scope: str
    user_stories: list[UserStory] = Field(min_length=1, max_length=15)
    epic_breakdown: list[str] = Field(min_length=1)
    sprint_1_plan: str
    success_metrics: list[str] = Field(min_length=1)


# ── CSO (Chief Security Officer) ────────────────────────────────────


class CSOAnalysis(BaseModel):
    """CSO agent output — security analysis."""

    auth_architecture: str
    encryption_requirements: list[str] = Field(min_length=1)
    compliance_needs: list[str] = Field(
        default_factory=list,
        description="GDPR / HIPAA / SOC2 based on domain",
    )
    threat_model: list[str] = Field(min_length=1)
    security_controls: list[str] = Field(min_length=1)


# ── CCO (Chief Compliance Officer) ──────────────────────────────────


class CCOAnalysis(BaseModel):
    """CCO agent output — compliance & legal analysis."""

    regulatory_requirements: list[str] = Field(default_factory=list)
    legal_obligations: list[str] = Field(default_factory=list)
    privacy_policy_requirements: str
    terms_of_service_requirements: str
    data_retention_policy: str
    gdpr_obligations: list[str] = Field(default_factory=list)


# ── CFO (Chief Financial Officer) ───────────────────────────────────


class CFOAnalysis(BaseModel):
    """CFO agent output — financial analysis."""

    pricing_strategy: str
    unit_economics: str
    cac_estimate: str
    ltv_estimate: str
    runway_calculation: str
    cost_structure: str
    breakeven_analysis: str


# ── Comprehensive Plan (Synthesizer output) ─────────────────────────


class ComprehensivePlan(BaseModel):
    """Synthesized plan from all 8 C-Suite analyses — Stage 3 output."""

    executive_summary: str
    tech_stack: dict[str, str] = Field(
        description="Final tech stack: {frontend, backend, database, hosting}"
    )
    design_system: str
    gtm_strategy: str
    feature_list: list[str] = Field(
        min_length=1,
        max_length=25,
        description="Top 20 prioritized features",
    )
    security_requirements: list[str] = Field(min_length=1)
    compliance_requirements: list[str] = Field(default_factory=list)
    financial_model: str
    timeline_estimate: str
    coherence_score: float = Field(ge=0.0, le=1.0)
    coherence_dimensions: dict[str, float] = Field(
        default_factory=dict,
        description="5 coherence dimension scores",
    )


# ── G3 Resolution ───────────────────────────────────────────────────


class ConflictResolution(BaseModel):
    """A single resolved conflict."""

    conflict_type: str = Field(
        description="tech_vs_budget | timeline_vs_scope | compliance_vs_features"
    )
    description: str
    winner: str = Field(description="Which perspective won")
    adaptation: str = Field(description="How the losing side adapted")


class G3Resolution(BaseModel):
    """G3 auto-resolver output — inter-agent conflict resolution."""

    conflicts_found: int = Field(ge=0)
    conflicts_resolved: int = Field(ge=0)
    resolutions: list[ConflictResolution] = Field(default_factory=list)


# ── Schema registry (for validation lookup) ─────────────────────────

CSUITE_SCHEMA_MAP: dict[str, type[BaseModel]] = {
    "ceo": CEOAnalysis,
    "cto": CTOAnalysis,
    "cdo": CDOAnalysis,
    "cmo": CMOAnalysis,
    "cpo": CPOAnalysis,
    "cso": CSOAnalysis,
    "cco": CCOAnalysis,
    "cfo": CFOAnalysis,
}
