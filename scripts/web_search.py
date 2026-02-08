"""
Web search module - fetches market/competitor data using Langdock's Agent API
with web search enabled.

Uses gpt-4o-mini for web searches (fast, cheap, separate rate limit from Claude).
"""

import os
import json
import uuid
import time
import requests


LANGDOCK_AGENT_URL = "https://api.langdock.com/agent/v1/chat/completions"
REQUEST_TIMEOUT = 300  # 5 minutes per request
MAX_RETRIES = 3
SEARCH_MODEL = "gpt-4o-mini"  # Fast model for web search step


def get_headers():
    """Get authorization headers for Langdock API."""
    api_key = os.environ.get("LANGDOCK_API_KEY")
    if not api_key:
        raise ValueError("LANGDOCK_API_KEY environment variable is not set")

    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def call_agent(prompt, agent_name="Competitive Intel Researcher"):
    """
    Call the Langdock Agent API with web search enabled.
    Includes retry logic for timeout, server, and rate limit errors.
    """
    headers = get_headers()

    payload = {
        "agent": {
            "name": agent_name,
            "instructions": (
                "You are a competitive intelligence researcher specializing in "
                "mobile adtech and programmatic advertising. Use web search to find "
                "the most recent, verified information. Always provide direct source "
                "URLs for every claim. If you cannot find information, say so — do "
                "not fabricate anything."
            ),
            "model": SEARCH_MODEL,
            "capabilities": {
                "webSearch": True,
            },
        },
        "messages": [
            {
                "id": str(uuid.uuid4()),
                "role": "user",
                "parts": [
                    {
                        "type": "text",
                        "text": prompt,
                    }
                ],
            }
        ],
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(f"    API call attempt {attempt}...")
            response = requests.post(
                LANGDOCK_AGENT_URL, headers=headers, json=payload, timeout=REQUEST_TIMEOUT
            )

            # Retry on rate limit (429)
            if response.status_code == 429:
                wait_time = 90 * attempt
                print(f"    Rate limited. Waiting {wait_time}s...")
                time.sleep(wait_time)
                continue

            # Retry on server errors (500, 502, 503, 504)
            if response.status_code >= 500:
                print(f"    Server error {response.status_code}: {response.text[:200]}")
                if attempt < MAX_RETRIES:
                    wait_time = 30 * attempt
                    print(f"    Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                else:
                    return f"Search failed after {MAX_RETRIES} attempts (server error)."

            # Print detailed error info for other errors
            if not response.ok:
                print(f"    ERROR {response.status_code}: {response.text}")
                response.raise_for_status()

            data = response.json()

            # Extract text from the response parts
            text_parts = []
            if "parts" in data:
                for part in data["parts"]:
                    if part.get("type") == "text" and "text" in part:
                        text_parts.append(part["text"])

            if not text_parts:
                if isinstance(data, dict):
                    if "text" in data:
                        text_parts.append(data["text"])
                    elif "content" in data:
                        if isinstance(data["content"], str):
                            text_parts.append(data["content"])
                        elif isinstance(data["content"], list):
                            for item in data["content"]:
                                if isinstance(item, dict) and "text" in item:
                                    text_parts.append(item["text"])

            result = "\n".join(text_parts) if text_parts else str(data)
            return result

        except requests.exceptions.ReadTimeout:
            print(f"    Timeout on attempt {attempt}")
            if attempt < MAX_RETRIES:
                wait_time = 30 * attempt
                print(f"    Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                return "Search timed out after multiple attempts. No data retrieved."

    return "Search failed after all retry attempts."


def search_competitor(competitor_name):
    """Search for recent news about a specific competitor."""
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

    findings = call_agent(search_prompt, agent_name=f"Research: {competitor_name}")

    return {
        "competitor": competitor_name,
        "findings": findings,
    }


def search_industry_trends():
    """Search for general mobile adtech industry trends."""
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

    findings = call_agent(trends_prompt, agent_name="Research: Industry Trends")

    return {
        "topic": "Industry Trends",
        "findings": findings,
    }


def run_all_searches():
    """Run web searches for all competitors and industry trends."""
    competitors = ["Adikteev", "Aarki", "RevX", "YouAppi"]

    print("Starting web searches...")
    results = {"competitors": [], "industry_trends": None}

    for competitor in competitors:
        print(f"  Searching for {competitor}...")
        result = search_competitor(competitor)
        results["competitors"].append(result)
        print(f"  Done with {competitor}")
        print("  Waiting 60s before next search (rate limit)...")
        time.sleep(60)

    print("  Searching for industry trends...")
    results["industry_trends"] = search_industry_trends()
    print("  Done with industry trends")

    print("All searches complete!")
    return results


if __name__ == "__main__":
    results = run_all_searches()
    for comp in results["competitors"]:
        print(f"\n{'='*60}")
        print(f"COMPETITOR: {comp['competitor']}")
        print(f"{'='*60}")
        print(comp["findings"][:500] + "...")
