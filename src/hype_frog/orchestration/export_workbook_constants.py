"""Static playbook copy for full-suite workbook export."""

from __future__ import annotations

PLAYBOOK_QUICK_REFERENCE_ROWS = [
        {"Section": "[Meta Data Standards]", "Item": "", "Guideline": "", "Why It Matters": ""},
        {
            "Section": "",
            "Item": "Meta Title",
            "Guideline": "50-60 characters. Place primary keyword at the front. Avoid brand repetition unless there is space.",
            "Why It Matters": "Improves clarity and reduces SERP truncation risk.",
        },
        {
            "Section": "",
            "Item": "Meta Description",
            "Guideline": "120-160 characters. Must contain a clear Call-To-Action (CTA) and active verbs.",
            "Why It Matters": "Supports stronger click-through and intent alignment.",
        },
        {
            "Section": "",
            "Item": "Target Keywords",
            "Guideline": "1 Primary, 2 Secondary per page. Do not keyword stuff; focus on user intent.",
            "Why It Matters": "Keeps copy focused on topical relevance over keyword density.",
        },
        {"Section": "", "Item": "", "Guideline": "", "Why It Matters": ""},
        {"Section": "[On-Page Structure (H-Tags)]", "Item": "", "Guideline": "", "Why It Matters": ""},
        {
            "Section": "",
            "Item": "H1 Tag",
            "Guideline": "Exactly ONE per page. Must contain the primary topic/keyword. Think of it as the 'Book Title'.",
            "Why It Matters": "Provides the clearest top-level topical signal.",
        },
        {
            "Section": "",
            "Item": "H2 Tags",
            "Guideline": "Main sections. Use question formats (Who, What, How) to trigger Answer Engine extraction.",
            "Why It Matters": "Improves structured scannability for users and LLMs.",
        },
        {
            "Section": "",
            "Item": "H3 Tags",
            "Guideline": "Sub-sections under H2s. Use for lists, steps, or detailed breakdowns.",
            "Why It Matters": "Strengthens hierarchy and supports extraction-ready formatting.",
        },
        {
            "Section": "",
            "Item": "H4-H6 Tags",
            "Guideline": "Use sparingly. Only for granular formatting within complex H3 topics.",
            "Why It Matters": "Avoids over-nesting while preserving semantic structure.",
        },
        {"Section": "", "Item": "", "Guideline": "", "Why It Matters": ""},
        {"Section": "[AEO (Answer Engine Optimisation) & Content]", "Item": "", "Guideline": "", "Why It Matters": ""},
        {
            "Section": "",
            "Item": "AEO Answer Blocks",
            "Guideline": "40-60 words. Placed directly beneath an H2 question. Must be factual, objective, and devoid of marketing fluff.",
            "Why It Matters": "Optimises direct extraction for answer engines and voice search.",
        },
        {
            "Section": "",
            "Item": "FAQ Schema",
            "Guideline": "Minimum 2-3 questions per informational page. Answers must be direct and stand alone without needing the rest of the page for context.",
            "Why It Matters": "Improves machine readability and rich-answer eligibility.",
        },
        {
            "Section": "",
            "Item": "Content Readability",
            "Guideline": "Keep sentences under 20 words. Use bullet points for any list of 3 or more items.",
            "Why It Matters": "Increases comprehension and snippet usability.",
        },
        {"Section": "", "Item": "", "Guideline": "", "Why It Matters": ""},
        {
            "Section": "[2025 AEO STRATEGY & STANDARDS]",
            "Item": "",
            "Guideline": "",
            "Why It Matters": "",
        },
        {
            "Section": "",
            "Item": "The 'Nugget' Rule",
            "Guideline": (
                "The direct answer to a query must be located within the first 100 words "
                "of the relevant section."
            ),
            "Why It Matters": "Answer engines surface the earliest concise fact block; burying the answer loses extraction priority.",
        },
        {
            "Section": "",
            "Item": "Objective Fact-Density",
            "Guideline": (
                "Avoid subjective adjectives ('award-winning', 'best'). LLMs prioritize "
                "objective nouns and verified data points."
            ),
            "Why It Matters": "Verifiable, concrete phrasing is easier to quote and less likely to be filtered as promotional noise.",
        },
        {
            "Section": "",
            "Item": "Inverted Pyramid Structure",
            "Guideline": (
                "Question Heading > Concise 50-word Answer > Supporting Data/List > "
                "Detailed Context."
            ),
            "Why It Matters": "Mirrors how models chunk content: lead with the extractable answer, then evidence, then depth.",
        },
        {
            "Section": "",
            "Item": "Schema as an API",
            "Guideline": (
                "View Schema not just for Google snippets, but as a direct data-feed for "
                "AI Answer Engines."
            ),
            "Why It Matters": "Structured types (FAQ, HowTo, Speakable) become machine-addressable facts when kept in sync with visible copy.",
        },
        {"Section": "", "Item": "", "Guideline": "", "Why It Matters": ""},
        {"Section": "[Visual & Social Branding]", "Item": "", "Guideline": "", "Why It Matters": ""},
        {
            "Section": "",
            "Item": "OG Image",
            "Guideline": "1200 x 630 pixels. Keep text centered (safe zone) so it isn't cropped by mobile devices on LinkedIn/X.",
            "Why It Matters": "Ensures consistent social card presentation.",
        },
        {
            "Section": "",
            "Item": "Social Share Note",
            "Guideline": "Customize the message for the platform. LinkedIn = Professional insight. X (Twitter) = Quick hook. Facebook = Conversational.",
            "Why It Matters": "Improves engagement by matching platform context.",
        },
    ]

PLAYBOOK_LEGEND_ROWS = [
    {
        "Section": "How To Use",
        "Term": "Step 1: Start on Dashboard",
        "Meaning": "Review pass rate, critical URL count, and Immediate Actions to understand overall risk first.",
        "Values/Threshold": "5-minute executive scan",
        "Related Tabs": "Dashboard, Priority URLs",
    },
    {
        "Section": "How To Use",
        "Term": "Step 2: Prioritize and Assign",
        "Meaning": "Use Priority URLs and FixPlan to pick highest-impact items, assign owner, and set status/sprint.",
        "Values/Threshold": "Work top-down by Business Risk Score",
        "Related Tabs": "Priority URLs, FixPlan",
    },
    {
        "Section": "How To Use",
        "Term": "Step 3: Execute and Validate",
        "Meaning": "Implement fixes, then verify by checking Technical/Indexability/AEO tabs and rerunning the audit.",
        "Values/Threshold": "Close loop every sprint",
        "Related Tabs": "Technical, Indexability, AEO, AIOSEO",
    },
    {
        "Section": "Orientation",
        "Term": "Where to Start",
        "Meaning": "If you're short on time, work only Critical and Warning issues first, then return to Observation items.",
        "Values/Threshold": "Critical > Warning > Observation",
        "Related Tabs": "Summary, FixPlan, Technical",
    },
    {
        "Section": "Color Key",
        "Term": "Green",
        "Meaning": "Pass / aligned with best practice or completed workflow item.",
        "Values/Threshold": "Good",
        "Related Tabs": "All",
    },
    {
        "Section": "Color Key",
        "Term": "Orange",
        "Meaning": "Warning / in progress / medium-priority attention needed.",
        "Values/Threshold": "Medium risk",
        "Related Tabs": "All",
    },
    {
        "Section": "Color Key",
        "Term": "Red",
        "Meaning": "Failure / high-priority issue or to-do critical task.",
        "Values/Threshold": "High risk",
        "Related Tabs": "All",
    },
]

