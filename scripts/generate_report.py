"""
Main report generation agent - ties web search and Excel output together.

This script:
1. Runs web searches for all competitors and industry trends (gpt-4o-mini via Langdock)
2. Sends all findings to Claude for structured analysis (claude-sonnet-4-5 via Langdock)
3. Parses Claude's structured response into sections
4. Writes everything to a formatted Excel file
"""

import os
import sys
import json
import uuid
import time
from datetime import datetime

import requests

# Add parent directory to path so we can import sibling modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from web_search import run_all_searches
from excel_output import write_full_report


LANGDOCK_AGENT_URL = "https://api.langdock.com/agent/v1/chat/completions"
ANALYSIS_MODEL = "claude-sonnet-4-5@20250929"  # Smart model for analysis
MAX_RETRIES = 3

# ---------------------------------------------------------------------------
# The full competitive intelligence analysis prompt
# ---------------------------------------------------------------------------
ANALYSIS_INSTRUCTIONS = """You are Remerge's Competitive Intelligence Analyst — a senior PMM/strategy
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

STRICT RULES:
- NO HALLUCINATIONS. If uncertain, state "Unverified — requires confirmation."
- Only report updates from the past 30 days unless essential historical context.
- Distinguish confirmed facts from analyst interpretation (prefix with "Assessment:").
- If no real update exists for a competitor, say so. Do not fabricate activity.
- Every source URL must be a direct permalink, not a homepage or generic page.
- The executive briefing should have 5-8 bullets maximum.
- The strategic synthesis recommendations should have 5 items maximum.

You MUST respond with valid JSON matching the exact structure the user specifies.
Do not include any text outside the JSON object."""


def get_headers():
    """Get authorization headers for Langdock API."""
    api_key = os.environ.get("LANGDOCK_API_KEY")
    if not api_key:
        raise ValueError("LANGDOCK_API_KEY environment variable is not set")

    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def format_search_results(search_results):
    """Format raw search results into a text block for the analysis prompt."""
    sections = []

    for comp in search_results["competitors"]:
        sections.append(f"=== COMPETITOR: {comp['competitor']} ===")
        sections.append(comp["findings"])
        sections.append("")

    if search_results.get("industry_trends"):
        sections.append("=== INDUSTRY TRENDS ===")
        sections.append(search_results["industry_trends"]["findings"])

    return "\n".join(sections)


def analyze_findings(formatted_results):
    """Send all search findings to Claude for structured analysis."""
    user_message = f"""Here is the research data gathered from web searches over the
past 30 days. Analyze this data and produce the competitive intelligence report
in the exact JSON format specified below.

REQUIRED OUTPUT FORMAT:
You MUST respond with valid JSON matching this exact structure. Do not include any
text outside the JSON object.

{{
  "executive_briefing": [
    {{"insight": "...", "impact": "HIGH|MEDIUM|LOW"}}
  ],
  "competitors": [
    {{
      "name": "Competitor Name",
      "risk_level": "HIGH|MEDIUM|LOW",
      "updates": "Key updates as text, separated by newlines",
      "implication": "Strategic implication for Remerge",
      "recommendation": "Recommended response",
      "sources": "Source URLs, one per line"
    }}
  ],
  "risk_dashboard": {{
    "HIGH": [{{"competitor": "...", "summary": "...", "impact": "..."}}],
    "MEDIUM": [{{"competitor": "...", "summary": "...", "impact": "..."}}],
    "LOW": [{{"competitor": "...", "summary": "...", "impact": "..."}}]
  }},
  "positioning_matrix": [
    {{
      "dimension": "AI/ML Sophistication",
      "remerge_rating": "Strong|Moderate|Developing",
      "leaders": "Leader name(s)",
      "gaps": "Gaps or opportunities"
    }}
  ],
  "strategic_synthesis": {{
    "themes": ["Theme 1", "Theme 2"],
    "opportunities": ["Opportunity 1", "Opportunity 2"],
    "vulnerabilities": ["Vulnerability 1", "Vulnerability 2"],
    "recommendations": ["Recommendation 1", "Recommendation 2"]
  }}
}}

DIMENSIONS FOR POSITIONING MATRIX:
- AI/ML Sophistication
- Privacy & Measurement Readiness
- Retargeting Depth & Performance
- Exchange/Supply Coverage
- Pricing Transparency
- Creative Optimization
- Geographic Reach

RESEARCH DATA:
{formatted_results}

Remember: Respond ONLY with valid JSON. No additional text."""

    headers = get_headers()

    payload = {
        "agent": {
            "name": "Competitive Intel Analyst",
            "instructions": ANALYSIS_INSTRUCTIONS,
            "model": ANALYSIS_MODEL,
            "capabilities": {},
        },
        "messages": [
            {
                "id": str(uuid.uuid4()),
                "role": "user",
                "parts": [
                    {
                        "type": "text",
                        "text": user_message,
                    }
                ],
            }
        ],
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(f"  Analysis attempt {attempt}...")
            response = requests.post(
                LANGDOCK_AGENT_URL, headers=headers, json=payload, timeout=300
            )

            # Retry on rate limit (429)
            if response.status_code == 429:
                wait_time = 90 * attempt
                print(f"  Rate limited. Waiting {wait_time}s...")
                time.sleep(wait_time)
                continue

            # Retry on server errors
            if response.status_code >= 500:
                print(f"  Server error {response.status_code}: {response.text[:200]}")
                if attempt < MAX_RETRIES:
                    wait_time = 30 * attempt
                    print(f"  Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                else:
                    raise Exception(f"Analysis failed after {MAX_RETRIES} attempts")

            if not response.ok:
                print(f"  ERROR {response.status_code}: {response.text}")
                response.raise_for_status()

            data = response.json()

            # Extract text from the response parts
            response_text = ""
            if "parts" in data:
                for part in data["parts"]:
                    if part.get("type") == "text" and "text" in part:
                        response_text += part["text"]

            if not response_text:
                if isinstance(data, dict):
                    if "text" in data:
                        response_text = data["text"]
                    elif "content" in data:
                        if isinstance(data["content"], str):
                            response_text = data["content"]
                        elif isinstance(data["content"], list):
                            for item in data["content"]:
                                if isinstance(item, dict) and "text" in item:
                                    response_text += item["text"]

            if not response_text:
                response_text = str(data)

            print(f"  Received analysis ({len(response_text)} chars)")

            # Parse the JSON response
            try:
                report_data = json.loads(response_text)
            except json.JSONDecodeError:
                cleaned = response_text.strip()
                if cleaned.startswith("```json"):
                    cleaned = cleaned[7:]
                if cleaned.startswith("```"):
                    cleaned = cleaned[3:]
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3]
                report_data = json.loads(cleaned.strip())

            return report_data

        except requests.exceptions.ReadTimeout:
            print(f"  Timeout on attempt {attempt}")
            if attempt < MAX_RETRIES:
                wait_time = 60 * attempt
                print(f"  Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                raise Exception("Analysis timed out after all attempts")

    raise Exception("Analysis failed after all retry attempts")


def main():
    """Main entry point - orchestrates the full report pipeline."""
    print("=" * 60)
    print("REMERGE COMPETITIVE INTELLIGENCE REPORT GENERATOR")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # Step 1: Run web searches (uses gpt-4o-mini)
    print("\n[1/3] Running web searches...")
    search_results = run_all_searches()

    # Step 2: Analyze with Claude (uses claude-sonnet-4-5)
    print("\n[2/3] Analyzing findings with Claude...")
    formatted_results = format_search_results(search_results)
    report_data = analyze_findings(formatted_results)

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
