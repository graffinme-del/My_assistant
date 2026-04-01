from __future__ import annotations


KAD_BROWSER_NOTES = {
    "site": "kad.arbitr.ru",
    "mode": "semi_auto_browser",
    "notes": [
        "Use browser-driven automation instead of plain HTTP parsing.",
        "Prefer slow paced downloads with explicit waits and retry-safe status updates.",
        "If captcha or manual confirmation appears, switch job status to needs_manual_step.",
        "Keep selectors tolerant and rely on visible labels where possible.",
    ],
}
