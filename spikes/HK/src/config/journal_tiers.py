"""
Journal Tier Classification for Oncology RAG

Classifies journals into tiers based on impact factor and relevance to oncology research.
This enables filtering by journal quality in RAG retrieval.

Tier Definitions:
-----------------
- tier1: Top-tier journals (IF > 30, CNS + top oncology journals)
- tier2: High-quality journals (IF 10-30, major specialty journals)
- tier3: Good journals (IF 5-10, solid peer-reviewed journals)
- tier4: Standard journals (IF < 5, all other indexed journals)

Note: Impact factors are approximate and based on 2023-2024 data.

Author: HK
Created: 2025-12-31
"""

from typing import Optional


# Tier 1: Top-tier journals (IF > 30)
# CNS (Cell, Nature, Science) + top oncology/medicine journals
TIER1_JOURNALS = {
    # CNS Main
    "nature",
    "science",
    "cell",

    # Nature family - high impact
    "nature medicine",
    "nature genetics",
    "nature biotechnology",
    "nature cancer",
    "nature immunology",
    "nature cell biology",
    "nature methods",
    "nature communications",  # IF ~17 but very high volume/influence

    # Cell family
    "cell stem cell",
    "cancer cell",
    "cell metabolism",
    "immunity",
    "molecular cell",

    # Top medical journals
    "new england journal of medicine",
    "nejm",
    "the lancet",
    "lancet",
    "lancet oncology",
    "jama",
    "jama oncology",
    "bmj",

    # Top oncology
    "journal of clinical oncology",
    "jco",
    "annals of oncology",
    "clinical cancer research",
}

# Tier 2: High-quality journals (IF 10-30)
TIER2_JOURNALS = {
    # Nature family - specialized
    "nature reviews cancer",
    "nature reviews clinical oncology",
    "nature reviews drug discovery",
    "nature reviews immunology",
    "nature reviews genetics",

    # Cell family - specialized
    "cell reports",
    "cell reports medicine",
    "cancer discovery",
    "cell host & microbe",

    # High-impact oncology
    "cancer research",
    "oncogene",
    "leukemia",
    "blood",
    "gut",
    "gastroenterology",
    "hepatology",
    "journal of hepatology",
    "breast cancer research",
    "molecular cancer",
    "npj precision oncology",
    "npj breast cancer",

    # High-impact general science
    "science translational medicine",
    "science advances",
    "pnas",
    "proceedings of the national academy of sciences",
    "elife",
    "embo journal",
    "nucleic acids research",
    "genome research",
    "genome biology",

    # Clinical
    "journal of the national cancer institute",
    "jnci",
    "european journal of cancer",
    "british journal of cancer",
    "international journal of cancer",
    "cancers",
}

# Tier 3: Good journals (IF 5-10)
TIER3_JOURNALS = {
    # Solid oncology journals
    "oncotarget",
    "cancer letters",
    "cancer science",
    "cancer medicine",
    "cancer biology & therapy",
    "cancer immunology research",
    "cancer immunology immunotherapy",
    "molecular cancer therapeutics",
    "molecular cancer research",
    "clinical lung cancer",
    "lung cancer",
    "breast cancer research and treatment",
    "prostate",
    "prostate cancer and prostatic diseases",
    "gynecologic oncology",
    "neuro-oncology",
    "journal of neuro-oncology",
    "bmc cancer",
    "plos one",  # High volume, variable quality but indexed
    "frontiers in oncology",
    "frontiers in immunology",
    "scientific reports",

    # Specialty journals
    "journal of thoracic oncology",
    "thyroid",
    "endocrine-related cancer",
    "cancer epidemiology biomarkers & prevention",
    "carcinogenesis",
    "cancer genetics",
    "genes & cancer",
    "tumor biology",
    "journal of experimental & clinical cancer research",
    "cancer management and research",

    # Methodology/bioinformatics
    "bioinformatics",
    "bmc bioinformatics",
    "bmc genomics",
    "briefings in bioinformatics",
}


def get_journal_tier(journal_name: Optional[str]) -> str:
    """
    Get the tier classification for a journal.

    Args:
        journal_name: Name of the journal (case-insensitive)

    Returns:
        Tier string: 'tier1', 'tier2', 'tier3', or 'tier4'

    Examples:
        >>> get_journal_tier("Nature")
        'tier1'
        >>> get_journal_tier("Cancer Research")
        'tier2'
        >>> get_journal_tier("BMC Cancer")
        'tier3'
        >>> get_journal_tier("Unknown Journal")
        'tier4'
    """
    if not journal_name:
        return "tier4"

    # Normalize journal name
    normalized = journal_name.lower().strip()

    # Remove common prefixes/suffixes
    normalized = normalized.replace("the ", "")

    # PRIORITY ORDER: Check lower tiers first for exact/close matches to avoid
    # false positives (e.g., "Cancer Research" should not match "cancer" in tier1)

    # Check tier3 exact matches first
    if normalized in TIER3_JOURNALS:
        return "tier3"

    # Check tier2 exact matches
    if normalized in TIER2_JOURNALS:
        return "tier2"

    # Check tier1 exact matches
    if normalized in TIER1_JOURNALS:
        return "tier1"

    # Now check partial matches, but be more careful
    # Only match if the full tier journal name is contained in the input
    # (not the other way around, to avoid "cell" matching "cancer cell")

    for tier3_journal in TIER3_JOURNALS:
        # Match if tier journal is a substring of input (e.g., "bmc cancer" in "bmc cancer research")
        if tier3_journal in normalized:
            return "tier3"

    for tier2_journal in TIER2_JOURNALS:
        if tier2_journal in normalized:
            return "tier2"

    for tier1_journal in TIER1_JOURNALS:
        if tier1_journal in normalized:
            return "tier1"

    # Reverse partial match: input is substring of tier journal
    # Be more selective - only for short, specific names
    if len(normalized) >= 6:  # Avoid matching too short strings
        for tier1_journal in TIER1_JOURNALS:
            if normalized in tier1_journal and len(normalized) > len(tier1_journal) * 0.5:
                return "tier1"

        for tier2_journal in TIER2_JOURNALS:
            if normalized in tier2_journal and len(normalized) > len(tier2_journal) * 0.5:
                return "tier2"

        for tier3_journal in TIER3_JOURNALS:
            if normalized in tier3_journal and len(normalized) > len(tier3_journal) * 0.5:
                return "tier3"

    # Default to tier4 for unknown journals
    return "tier4"


def get_tier_description(tier: str) -> str:
    """Get human-readable description of a tier."""
    descriptions = {
        "tier1": "Top-tier (CNS, NEJM, Lancet, Nature family, top oncology)",
        "tier2": "High-quality (IF 10-30, major specialty journals)",
        "tier3": "Good (IF 5-10, solid peer-reviewed journals)",
        "tier4": "Standard (other indexed journals)",
    }
    return descriptions.get(tier, "Unknown tier")


# Export all tiers for reference
JOURNAL_TIERS = {
    "tier1": TIER1_JOURNALS,
    "tier2": TIER2_JOURNALS,
    "tier3": TIER3_JOURNALS,
}


if __name__ == "__main__":
    # Test the classification
    test_journals = [
        "Nature",
        "Nature Medicine",
        "Cancer Cell",
        "Cancer Research",
        "BMC Cancer",
        "PLOS ONE",
        "Random Unknown Journal",
        "Journal of Clinical Oncology",
        "Cell Reports",
        None,
    ]

    print("=== Journal Tier Classification Test ===\n")
    for journal in test_journals:
        tier = get_journal_tier(journal)
        desc = get_tier_description(tier)
        print(f"{journal or 'None':40} -> {tier} ({desc})")
