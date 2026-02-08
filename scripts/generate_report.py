"""
Main report generation agent - ties web search and Excel output together.

This script:
1. Runs web searches for all competitors and industry trends
2. Sends all findings to Claude with the competitive intelligence prompt
3. Parses Claude's structured response into sections
4. Writes everything to a formatted Excel file
"""

import os
import sys
import json
from datetime import datetime

from anthropic import Anthropic

# Add parent directory to path so we can import sibling modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from web_search import run_all_searches
from excel_output import write_full_report


# ---------------------------------------------------------------------------
# The full competitive intelligence analysis prompt
# ---------------------------------------------------------------------------
ANALYSIS_PROMPT = """
ROLE: You are Remerge's Competitive Intelligence Analyst — a senior PMM/strategy
analyst specializing in mobile adtech and programmatic advertising. You produce
institutional-grade competitive intelligence that informs product strategy, GTM
positioning, and executive decision-making.

TONE: Factual, analytical, concise. McKinsey-style brevity. No filler, no
speculation without labeling it as such.

COMPANY CONTEXT:
Remerge is a mobile demand-side platform (DSP) focused on in-app programmatic
advertising, specializing in app retargeting and incremental performance measurement.
Key differentiators include direct integration with major ad exchanges, proprietary
incrementality measurement, privacy-first approach, and transparent pricing. Remerge
serves global app-first businesses across gaming, e-commerce, travel, fintech, and
entertainment.

COMPETITOR WATCHLIST: Adikteev, Aarki, RevX, YouAppi

Do NOT report on Remerge itself in the competitor sections. Remerge is analyzed only
in the positioning comparison section.

Based on the research data provided below, produce the following structured report.

REQUIRED OUTPUT FORMAT:
You MUST respond with valid JSON matching this exact structure. Do not include any
text outside the JSON object.

{
  "executive_briefing": [
    {"insight": "...", "impact": "HIGH|MEDIUM|LOW"}
  ],
  "competitors": [
    {
      "name": "Competitor Name",
      "risk_level": "HIGH|MEDIUM|LOW",
      "updates": "Key updates as text, separated by newlines",
      "implication": "Strategic implication for Remerge",
      "recommendation": "Recommended response",
      "sources": "Source URLs, one per line"
    }
  ],
  "risk_dashboard": {
    "HIGH": [{"competitor": "...", "summary": "...", "impact": "..."}],
    "MEDIUM": [{"competitor": "...", "summary": "...", "impact": "..."}],
    "LOW": [{"competitor": "...", "summary": "...", "impact": "..."}]
  },
  "positioning_matrix": [
    {
      "dimension": "AI/ML Sophistication",
      "remerge_rating": "Strong|Moderate|Developing",
      "leaders": "Leader name(s)",
      "gaps": "Gaps or opportunities"
    }
  ],
  "strategic_synthesis": {
    "themes": ["Theme 1", "Theme 2"],
    "opportunities": ["Opportunity 1", "Opportunity 2"],
    "vulnerabilities": ["Vulnerability 1", "Vulnerability 2"],
    "recommendations": ["Recommendation 1", "Recommendation 2"]
  }
}

DIMENSIONS FOR POSITIONING MATRIX:
- AI/ML Sophistication
- Privacy & Measurement Readiness
- Retargeting Depth & Performance
- Exchange/Supply Coverage
- Pricing Transparency
- Creative Optimization
- Geographic Reach

STRICT RULES:
- NO HALLUCINATIONS. If uncertain, state "Unverified — requires confirmation."
- Only report updates from the past 30 days unless essential historical context.
- Distinguish confirmed facts from analyst interpretation (prefix with "Assessment:").
- If no real update exists for a competitor, say so. Do not fabricate activity.
- Every source URL must be a direct permalink, not a homepage or generic page.
- The executive briefing should have 5-8 bullets maximum.
- The strategic synthesis recommendations should have 5 items maximum.
"""


def get_client():
    """Create an Anthropic client configured for Langdock."""
    api_key = os.environ.get("LANGDOCK_API_KEY")
    if not api_key:
        raise ValueError("LANGDOCK_API_KEY environment variable is not set")

    return Anthropic(
        base_url="https://api.langdock.com/anthropic/eu/",
        api_key=api_key,
    )


def format_search_results(search_results):
    """
    Format raw search results into a text block for the analysis prompt.

    Args:
        search_results: dict from run_all_searches()

    Returns:
        Formatted string with all search findings
    """
    sections = []

    for comp in search_results["competitors"]:
        sections.append(f"=== COMPETITOR: {comp['competitor']} ===")
        sections.append(comp["findings"])
        sections.append("")

    if search_results.get("industry_trends"):
        sections.append("=== INDUSTRY TRENDS ===")
        sections.append(search_results["industry_trends"]["findings"])

    return "\n".join(sections)


def analyze_findings(client, formatted_results):
    """
    Send all search findings to Claude for structured analysis.

    Args:
        client: Anthropic client
        formatted_results: Formatted search results string

    Returns:
        Parsed JSON dict of the structured report
    """
    user_message = f"""Here is the research data gathered from web searches over the
past 30 days. Analyze this data and produce the competitive intelligence report
in the exact JSON format specified.

RESEARCH DATA:
{formatted_results}

Remember: Respond ONLY with valid JSON. No additional text."""

    print("Sending findings to Claude for analysis...")
    message = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=8192,
        system=ANALYSIS_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    response_text = message.content[0].text
    print(f"Received analysis ({message.usage.output_tokens} tokens)")

    # Parse the JSON response
    try:
        report_data = json.loads(response_text)
    except json.JSONDecodeError:
        # Sometimes the model wraps JSON in markdown code blocks
        cleaned = response_text.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        report_data = json.loads(cleaned.strip())

    return report_data


def main():
    """Main entry point - orchestrates the full report pipeline."""
    print("=" * 60)
    print("REMERGE COMPETITIVE INTELLIGENCE REPORT GENERATOR")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # Step 1: Run web searches
    print("\n[1/3] Running web searches...")
    search_results = run_all_searches()

    # Step 2: Analyze with Claude
    print("\n[2/3] Analyzing findings with Claude...")
    client = get_client()
    formatted_results = format_search_results(search_results)
    report_data = analyze_findings(client, formatted_results)

    # Add raw data for archival
    report_data["raw_data"] = formatted_results

    # Step 3: Write to Excel
    print("\n[3/3] Writing report to Excel...")
    filepath = write_full_report(report_data)

    print("\n" + "=" * 60)
    print("REPORT COMPLETE!")
    print(f"File: {filepath}")
    print("=" * 60)

    return filepath


if __name__ == "__main__":
    main()
