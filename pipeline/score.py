"""
V1 Lead Scoring System

Rules-based scoring with confidence and explainability.

Design Principles:
- Conservative > clever
- Explainable > complex
- Unknown ≠ bad (null signals don't penalize, just reduce confidence)
- Output must make sense to agencies

Signal Semantics:
- true  = confidently observed (can contribute positive points)
- false = confidently absent (can contribute negative points or zero)
- null  = unknown (does NOT penalize, but reduces confidence)
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

# Base score everyone starts with
BASE_SCORE = 40

# Signal weights for confidence calculation
# Higher weight = more important for confidence
SIGNAL_WEIGHTS = {
    "has_website": 1.0,
    "website_accessible": 1.0,
    "has_phone": 1.0,
    "has_contact_form": 1.5,
    "has_email": 1.0,
    "has_automated_scheduling": 1.5,
    "review_count": 1.0,
    "last_review_days_ago": 1.0,
}

# Review freshness thresholds (in days)
REVIEW_FRESH_DAYS = 30
REVIEW_WARM_DAYS = 90
REVIEW_STALE_DAYS = 180

# Review volume threshold
LOW_REVIEW_COUNT = 30


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class ScoringResult:
    """Result of lead scoring."""
    lead_score: int           # 0-100
    priority: str             # "High", "Medium", "Low"
    confidence: float         # 0.0-1.0
    reasons: List[str]        # Human-readable explanations
    review_summary: Dict      # Review context for agencies
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "lead_score": self.lead_score,
            "priority": self.priority,
            "confidence": self.confidence,
            "reasons": self.reasons,
            "review_summary": self.review_summary,
        }


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _is_known(value) -> bool:
    """Check if a signal value is known (not null/None)."""
    return value is not None


def _is_true(value) -> bool:
    """Check if a signal value is confidently true."""
    return value is True


def _is_false(value) -> bool:
    """Check if a signal value is confidently false."""
    return value is False


def _get_priority_bucket(score: int) -> str:
    """Determine priority bucket from score."""
    if score >= 80:
        return "High"
    elif score >= 50:
        return "Medium"
    else:
        return "Low"


def _clamp(value: int, min_val: int, max_val: int) -> int:
    """Clamp a value to a range."""
    return max(min_val, min(max_val, value))


# =============================================================================
# SCORING RULES
# =============================================================================

def _score_reachability(signals: Dict) -> Tuple[int, List[str]]:
    """
    Score PRIMARY signals: Reachability & Intake.
    
    These signals indicate the business can be contacted.
    Only positive contributions - null doesn't penalize.
    """
    points = 0
    reasons = []
    
    # Website presence (+10)
    if _is_true(signals.get("has_website")):
        points += 10
        reasons.append("Has business website")
    
    # Website accessible (+10)
    if _is_true(signals.get("website_accessible")):
        points += 10
        reasons.append("Website is accessible and functional")
    
    # Phone number (+10) - PRIMARY for HVAC
    if _is_true(signals.get("has_phone")):
        points += 10
        reasons.append("Phone contact available")
    
    # Contact form (+15) - Strong inbound signal
    if _is_true(signals.get("has_contact_form")):
        points += 15
        reasons.append("Accepts online requests via website")
    
    # Email (+10)
    if _is_true(signals.get("has_email")):
        points += 10
        reasons.append("Email contact available")
    
    return points, reasons


def _score_operations_maturity(signals: Dict) -> Tuple[int, List[str]]:
    """
    Score OPERATIONS MATURITY (opportunity signal).
    
    Businesses WITHOUT automated scheduling are HIGHER opportunity
    because they have room for optimization services.
    
    - false = Manual ops = +20 (high opportunity)
    - null  = Unknown = +10 (moderate opportunity)
    - true  = Automated = +0 (already optimized)
    """
    points = 0
    reasons = []
    
    scheduling = signals.get("has_automated_scheduling")
    
    if _is_false(scheduling):
        # Confirmed manual operations = high opportunity
        points += 20
        reasons.append("Manual scheduling detected (optimization opportunity)")
    elif scheduling is None:
        # Unknown = moderate opportunity (don't penalize)
        points += 10
        reasons.append("Scheduling automation status unknown")
    else:
        # Automated = no bonus (already optimized)
        pass
    
    return points, reasons


def _score_reputation_opportunity(signals: Dict) -> Tuple[int, List[str]]:
    """
    Score REPUTATION opportunity.
    
    Low review count and stale reviews indicate opportunity
    for reputation management services.
    """
    points = 0
    reasons = []
    
    review_count = signals.get("review_count")
    last_review_days = signals.get("last_review_days_ago")
    
    # Low review volume (+10)
    if review_count is not None and review_count < LOW_REVIEW_COUNT:
        points += 10
        reasons.append(f"Low review volume ({review_count} reviews)")
    
    # Stale reviews (+10 or +15)
    if last_review_days is not None:
        if last_review_days > REVIEW_STALE_DAYS:
            points += 15
            months = last_review_days // 30
            reasons.append(f"No recent reviews in {months}+ months")
        elif last_review_days > REVIEW_WARM_DAYS:
            points += 10
            reasons.append("Reviews becoming stale (3+ months)")
    
    return points, reasons


def _score_disqualifiers(signals: Dict) -> Tuple[int, List[str]]:
    """
    Apply DISQUALIFIERS (rare, severe issues).
    
    Only applies when signals are CONFIDENTLY false.
    Null values do NOT trigger disqualifiers.
    """
    points = 0
    reasons = []
    
    # No contact paths at all (-40)
    # Only if ALL are confidently false (not null)
    has_phone = signals.get("has_phone")
    has_form = signals.get("has_contact_form")
    has_email = signals.get("has_email")
    
    if (_is_false(has_phone) and 
        _is_false(has_form) and 
        _is_false(has_email)):
        points -= 40
        reasons.append("No contact methods available")
    
    # Website inaccessible (-20)
    # Only if website exists but is inaccessible
    if (_is_true(signals.get("has_website")) and 
        _is_false(signals.get("website_accessible"))):
        points -= 20
        reasons.append("Website exists but is not accessible")
    
    return points, reasons


# =============================================================================
# CONFIDENCE CALCULATION
# =============================================================================

def calculate_confidence(signals: Dict) -> float:
    """
    Calculate confidence score based on data coverage.
    
    Confidence = (weight of known signals) / (weight of all signals)
    
    Known = value is true or false
    Unknown = value is null
    
    Confidence ≠ correctness
    Confidence = how much evidence we have
    """
    observed_weight = 0.0
    total_weight = 0.0
    
    for signal_name, weight in SIGNAL_WEIGHTS.items():
        total_weight += weight
        
        # Get the signal value
        # Handle both direct signals and signal_ prefixed versions
        value = signals.get(signal_name)
        if value is None:
            value = signals.get(f"signal_{signal_name}")
        
        # Check if this signal is known (not null)
        if _is_known(value):
            observed_weight += weight
    
    if total_weight == 0:
        return 0.0
    
    confidence = observed_weight / total_weight
    return round(confidence, 2)


# =============================================================================
# REVIEW SUMMARY
# =============================================================================

def _build_review_summary(signals: Dict) -> Dict:
    """
    Build human-readable review summary for agency context.
    
    This provides at-a-glance review data alongside scoring reasons.
    """
    review_count = signals.get("review_count")
    rating = signals.get("rating")
    last_review_days = signals.get("last_review_days_ago")
    
    # Calculate freshness label
    if last_review_days is None:
        freshness = "Unknown"
        last_review_text = "Unknown"
    elif last_review_days <= REVIEW_FRESH_DAYS:
        freshness = "Fresh"
        last_review_text = f"{last_review_days} days ago"
    elif last_review_days <= REVIEW_WARM_DAYS:
        freshness = "Warm"
        last_review_text = f"{last_review_days} days ago"
    elif last_review_days <= REVIEW_STALE_DAYS:
        freshness = "Stale"
        months = last_review_days // 30
        last_review_text = f"~{months} months ago"
    else:
        freshness = "Very Stale"
        months = last_review_days // 30
        last_review_text = f"~{months} months ago"
    
    # Volume label
    if review_count is None:
        volume = "Unknown"
    elif review_count < 10:
        volume = "Very Low"
    elif review_count < LOW_REVIEW_COUNT:
        volume = "Low"
    elif review_count < 100:
        volume = "Moderate"
    else:
        volume = "High"
    
    return {
        "review_count": review_count,
        "rating": rating,
        "last_review_days_ago": last_review_days,
        "last_review_text": last_review_text,
        "freshness": freshness,
        "volume": volume,
    }


# =============================================================================
# MAIN SCORING FUNCTION
# =============================================================================

def score_lead(lead: Dict) -> ScoringResult:
    """
    Score a single lead and generate explanations.
    
    Args:
        lead: Lead dictionary with signals (can have signal_ prefix or not)
    
    Returns:
        ScoringResult with score, priority, confidence, and reasons
    """
    # Normalize signals - handle both prefixed and non-prefixed
    signals = {}
    for key, value in lead.items():
        if key.startswith("signal_"):
            clean_key = key[7:]  # Remove "signal_" prefix
            signals[clean_key] = value
        else:
            signals[key] = value
    
    # Start with base score
    score = BASE_SCORE
    all_reasons = []
    
    # Apply scoring rules
    reachability_points, reachability_reasons = _score_reachability(signals)
    score += reachability_points
    all_reasons.extend(reachability_reasons)
    
    ops_points, ops_reasons = _score_operations_maturity(signals)
    score += ops_points
    all_reasons.extend(ops_reasons)
    
    reputation_points, reputation_reasons = _score_reputation_opportunity(signals)
    score += reputation_points
    all_reasons.extend(reputation_reasons)
    
    disqualifier_points, disqualifier_reasons = _score_disqualifiers(signals)
    score += disqualifier_points
    all_reasons.extend(disqualifier_reasons)
    
    # Calculate confidence first (needed for adjustments)
    confidence = calculate_confidence(signals)
    
    # Build review summary (needed for adjustments)
    review_summary = _build_review_summary(signals)
    
    # =========================================================================
    # SCORE REFINEMENT (make 100 rare and meaningful)
    # =========================================================================
    
    raw_score = score  # Store for reference
    
    # --- 1. Penalties for "already optimized" businesses ---
    if _is_true(signals.get("has_automated_scheduling")):
        score -= 5
        all_reasons.append("Already uses scheduling automation (-5)")
    
    if _is_true(signals.get("has_trust_badges")):
        score -= 3
        all_reasons.append("Has trust badges (established presence, -3)")
    
    review_count = signals.get("review_count")
    freshness = review_summary.get("freshness")
    
    if freshness == "Fresh" and review_count is not None and review_count > 100:
        score -= 3
        all_reasons.append("High volume with fresh reviews (saturated, -3)")
    
    # --- 2. Confidence-weighted final score ---
    # Dampens inflated scores when data is incomplete
    # Formula: final = raw * (0.7 + 0.3 * confidence)
    confidence_multiplier = 0.7 + 0.3 * confidence
    score = int(score * confidence_multiplier)
    
    if confidence < 0.8:
        all_reasons.append(f"Score adjusted for data coverage ({confidence:.0%} confidence)")
    
    # --- 3. Review-count score ceiling ---
    # Large brands are less ideal outreach targets
    if review_count is not None:
        if review_count > 200:
            max_score = 92
            if score > max_score:
                score = max_score
                all_reasons.append("Capped at 92 (large brand, 200+ reviews)")
        elif review_count > 100:
            max_score = 95
            if score > max_score:
                score = max_score
                all_reasons.append("Capped at 95 (established brand, 100+ reviews)")
    
    # --- 4. Hard gate for 100-score leads ---
    # 100 = elite, must-contact-first leads
    # All conditions must be true for a perfect score
    can_be_elite = (
        _is_true(signals.get("has_website")) and
        _is_true(signals.get("has_contact_form")) and
        _is_true(signals.get("has_phone")) and
        _is_false(signals.get("has_automated_scheduling")) and
        review_count is not None and 5 <= review_count <= 80 and
        freshness != "Fresh" and
        confidence >= 0.9
    )
    
    if score >= 100 and not can_be_elite:
        score = 95
        all_reasons.append("Capped at 95 (does not meet elite criteria)")
    
    # Final clamp to valid range
    score = _clamp(score, 0, 100)
    
    # Add confidence context to reasons if low
    if confidence < 0.5:
        all_reasons.append("Limited data available (low confidence)")
    
    # Determine priority (after all adjustments)
    priority = _get_priority_bucket(score)
    
    return ScoringResult(
        lead_score=score,
        priority=priority,
        confidence=confidence,
        reasons=all_reasons,
        review_summary=review_summary
    )


def score_leads_batch(leads: List[Dict]) -> List[Dict]:
    """
    Score multiple leads and return enriched dictionaries.
    
    Args:
        leads: List of lead dictionaries
    
    Returns:
        List of leads with scoring fields added
    """
    scored_leads = []
    
    for lead in leads:
        result = score_lead(lead)
        
        # Add scoring fields to lead
        scored_lead = lead.copy()
        scored_lead["lead_score"] = result.lead_score
        scored_lead["priority"] = result.priority
        scored_lead["confidence"] = result.confidence
        scored_lead["reasons"] = result.reasons
        scored_lead["review_summary"] = result.review_summary
        
        scored_leads.append(scored_lead)
    
    return scored_leads


def get_scoring_summary(scored_leads: List[Dict]) -> Dict:
    """
    Generate summary statistics for scored leads.
    
    Args:
        scored_leads: List of leads with scoring fields
    
    Returns:
        Summary dictionary
    """
    if not scored_leads:
        return {"total": 0}
    
    scores = [l.get("lead_score", 0) for l in scored_leads]
    confidences = [l.get("confidence", 0) for l in scored_leads]
    priorities = [l.get("priority", "Unknown") for l in scored_leads]
    
    high_priority = sum(1 for p in priorities if p == "High")
    medium_priority = sum(1 for p in priorities if p == "Medium")
    low_priority = sum(1 for p in priorities if p == "Low")
    
    return {
        "total_leads": len(scored_leads),
        "score": {
            "avg": round(sum(scores) / len(scores), 1),
            "min": min(scores),
            "max": max(scores),
        },
        "confidence": {
            "avg": round(sum(confidences) / len(confidences), 2),
            "min": min(confidences),
            "max": max(confidences),
        },
        "priority": {
            "high": high_priority,
            "high_pct": round(high_priority / len(scored_leads) * 100, 1),
            "medium": medium_priority,
            "medium_pct": round(medium_priority / len(scored_leads) * 100, 1),
            "low": low_priority,
            "low_pct": round(low_priority / len(scored_leads) * 100, 1),
        }
    }
