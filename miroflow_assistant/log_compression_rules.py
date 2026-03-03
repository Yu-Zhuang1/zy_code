import re
from urllib.parse import urlparse

# Strip internal thinking while keeping visible actions/results.
THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.IGNORECASE | re.DOTALL)
BOXED_ANSWER_RE = re.compile(r"\\boxed\{[^}]+\}")
DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
NUMBER_RE = re.compile(r"[-+]?\d+(?:\.\d+)?")
SEARCH_QUERY_RE = re.compile(r'"q"\s*:\s*"([^"]+)"')

MESSAGE_CHAR_BUDGET = {
    "main_user": 2600,
    "main_assistant": 1600,
    "sub_user": 1500,
    "sub_assistant": 1200,
    "tool_call": 800,
    "webpage_markdown": 1400,
    "fallback": 900,
}

PROMPT_SECTION_CHAR_BUDGET = {
    "task_context": 3000,
    "decisive_evidence": 4200,
    "conflict_evidence": 2600,
    "error_summary": 2200,
    "residual_context": 3200,
}

EVIDENCE_LIMITS = {
    "decisive_max_items": 8,
    "conflict_max_items": 6,
    "excerpt_max_chars": 320,
}

RESIDUAL_CONTEXT_LIMITS = {
    "main_recent_messages": 12,
    "sub_recent_messages": 5,
    "message_max_chars": 280,
}

SEARCH_RESULT_TOP_K = 3
SEARCH_SNIPPET_MAX_CHARS = 160

WEBPAGE_NOISE_PREFIXES = (
    "skip to main content",
    "[skip to main content]",
    "[skip to main-content]",
    "close ad",
    "pause all rotators",
    "main navigation menu",
    "menu",
    "* sports",
    "## main navigation menu",
)

WEBPAGE_NOISE_CONTAINS = (
    "scorecardresearch.com",
    "sidearm.nextgen.sites",
    "buy tickets",
    "facebook",
    "instagram",
    "privacy policy",
    "complaints",
)

DECISIVE_KEYWORDS = (
    "final score",
    "winner",
    "won",
    "victory",
    "conclusion",
    "total net flow",
    "net inflow",
    "net outflow",
    "resolved",
    "\\boxed{",
)

CONFLICT_KEYWORDS = (
    "contradict",
    "conflict",
    "however",
    "but",
    "no flows",
    "0.0",
    "as of",
    "not found",
    "failed",
)

TASK_CONSTRAINT_KEYWORDS = (
    "this market will resolve",
    "resolution source",
    "if flows are exactly 0",
    "result will be determined",
    "scheduled for",
)

ERROR_SIGNATURE_PATTERNS = (
    (
        "tool_server_not_found",
        re.compile(
            r"Tool call to .* failed\. Error: Server '([^']+)' not found\.",
            re.IGNORECASE,
        ),
    ),
    (
        "tool_result_error",
        re.compile(r"Tool result error - tool:\s*([A-Za-z0-9_\-]+)", re.IGNORECASE),
    ),
    (
        "sandbox_connect_failed",
        re.compile(r"Failed to connect to sandbox", re.IGNORECASE),
    ),
    (
        "http_403",
        re.compile(r"status\s*403|Failed to retrieve page", re.IGNORECASE),
    ),
)


def extract_domain(url: str) -> str:
    if not isinstance(url, str) or not url:
        return ""
    try:
        parsed = urlparse(url)
    except ValueError:
        return ""
    return (parsed.netloc or "").lower().replace("www.", "")
