"""
Web search module - fetches market/competitor data using Claude's web search capabilities.

This module uses Claude (via Langdock) to search the web for recent competitor
intelligence on each company in the watchlist.
"""

import os
import json
from anthropic import Anthropic


def get_client():
    """Create an Anthropic client configured for Langdock."""
    api_key = os.environ.get("LANGDOCK_API_KEY")
    if not api_key:
        raise ValueError("LANGDOCK_API_KEY environment variable is not set")

    return Anthropic(
        base_url="https://api.langdock.com/anthropic/eu/",
        api_key=api_key,
    )


def search_competitor(client, competitor_name):
    """
    Search for recent news and updates about a specific competitor.

    Args:
        client: Anthropic client instance
        competitor_name: Name of the competitor to research

    Returns:
        dict with competitor name and raw findings text
    """
    search_prompt = f"""Search the web for the most recent news, updates, and announcements
about {competitor_name} in the mobile advertising / adtech space from the past 30 days.

Look for:
1. Product launches, feature releases, SDK updates
2. AI/ML advancements (bidding algorithms, creative optimization)
3. Privacy and measurement innovations (SKAN, Privacy Sandbox, clean rooms)
4. New partnerships (MMPs, ad exchanges, data providers, agencies)
5. Funding rounds, M&A activity, leadership changes
6. Conference talks, thought leadership articles
7. Hiring patterns indicating strategic direction
8. Website or positioning changes
9. New case studies or customer wins

For EACH finding, provide:
- What happened (specific details)
- When it happened (exact date if available)
- The direct source URL (full permalink, not a homepage)
- A brief quote or summary from the source

If you cannot find significant updates from the past 30 days, explicitly state that.
Do NOT fabricate or guess any information. Only report what you can verify."""

    message = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=4096,
        messages=[{"role": "user", "content": search_prompt}],
    )

    return {
        "competitor": competitor_name,
        "findings": message.content[0].text,
    }


def search_industry_trends(client):
    """
    Search for general mobile adtech industry trends and news.

    Args:
        client: Anthropic client instance

    Returns:
        dict with industry trends findings
    """
    trends_prompt = """Search the web for the most important mobile advertising and
programmatic adtech industry trends and news from the past 30 days.

Focus on:
1. Major industry shifts (privacy changes, platform policies)
2. Regulatory developments affecting mobile advertising
3. Emerging technologies (AI in advertising, privacy-preserving measurement)
4. Market consolidation (M&A activity in mobile adtech)
5. Platform updates from Apple (SKAN, ATT) and Google (Privacy Sandbox)
6. Notable industry reports or research publications

For EACH finding, provide:
- What happened (specific details)
- When it happened (exact date if available)
- The direct source URL (full permalink)
- A brief summary

Only report verified information. Do NOT fabricate anything."""

    message = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=4096,
        messages=[{"role": "user", "content": trends_prompt}],
    )

    return {
        "topic": "Industry Trends",
        "findings": message.content[0].text,
    }


def run_all_searches():
    """
    Run web searches for all competitors and industry trends.

    Returns:
        dict containing all search results
    """
    client = get_client()
    competitors = ["Adikteev", "Aarki", "RevX", "YouAppi"]

    print("Starting web searches...")
    results = {"competitors": [], "industry_trends": None}

    for competitor in competitors:
        print(f"  Searching for {competitor}...")
        result = search_competitor(client, competitor)
        results["competitors"].append(result)
        print(f"  Done with {competitor}")

    print("  Searching for industry trends...")
    results["industry_trends"] = search_industry_trends(client)
    print("  Done with industry trends")

    print("All searches complete!")
    return results


if __name__ == "__main__":
    results = run_all_searches()
    # Print a summary
    for comp in results["competitors"]:
        print(f"\n{'='*60}")
        print(f"COMPETITOR: {comp['competitor']}")
        print(f"{'='*60}")
        print(comp["findings"][:500] + "...")

