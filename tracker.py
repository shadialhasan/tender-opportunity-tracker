# -*- coding: utf-8 -*-
"""
Government & Sovereign Fund Tender Opportunity Scraper & Tracker
Author: Eng. MHD. Shadi AL-Hasan <mhd.shadi.alhasan@gmail.com>
Phone: +963934005922
Copyright (c) 2026 MHD. Shadi AL-Hasan
"""

import os
import sys
import time
import json
import argparse
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Optional, List, Dict, Any, Union

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')


# --- Environment Loader ---

def load_env_file(filepath: Optional[Path] = None) -> Dict[str, str]:
    """Loads environment configuration without third-party dependencies."""
    env_vars: Dict[str, str] = {}
    if filepath is None:
        filepath = Path(".env")
    if not filepath.exists():
        return env_vars

    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip("'\"")
            env_vars[key] = val
            if key not in os.environ:
                os.environ[key] = val
    return env_vars


# --- Scraper Extractor & Normalizer ---

DEFAULT_SIMULATED_PORTAL_DATA = [
    {
        "id": "TND-2026-0891",
        "title": "توريد وتطوير البنية التحتية للحوسبة السحابية ومراكز البيانات",
        "entity": "وزارة الاتصالات والتقانة",
        "deadline": "2026-11-15",
        "category": "IT & Cloud Infrastructure",
        "status": "OPEN",
        "estimated_budget_usd": 1200000.0
    },
    {
        "id": "TND-2026-0904",
        "title": "مشروع حوسبة وأتمتة منظومة إدارة الموارد للمؤسسات العامة (ERP)",
        "entity": "الصندوق السيادي للاستثمار",
        "deadline": "2026-11-30",
        "category": "Enterprise Software",
        "status": "OPEN",
        "estimated_budget_usd": 850000.0
    },
    {
        "id": "TND-2026-0912",
        "title": "توريد تجهيزات الشبكات الضوئية والألياف عالية السرعة للربط البيني",
        "entity": "الشركة السورية للاتصالات",
        "deadline": "2026-10-25",
        "category": "Telecommunications",
        "status": "OPEN",
        "estimated_budget_usd": 450000.0
    },
    {
        "id": "TND-2026-0740",
        "title": "صيانة وتحديث أنظمة الحماية الجدارية ومكافحة التهديدات السيبرانية",
        "entity": "الهيئة الوطنية لخدمات الشبكات",
        "deadline": "2026-09-15",
        "category": "Cybersecurity",
        "status": "CLOSED",
        "estimated_budget_usd": 320000.0
    }
]

def extract_opportunity_record(raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Validates, extracts, and normalizes a single tender record.
    Supports Arabic text, dates, categories, and numerical budgets.
    """
    if not isinstance(raw, dict):
        return None

    tender_id = str(raw.get("id") or "").strip()
    title = str(raw.get("title") or "").strip()
    entity = str(raw.get("entity") or "").strip()
    deadline = str(raw.get("deadline") or "").strip()
    category = str(raw.get("category") or "General Procurement").strip()
    status = str(raw.get("status") or "OPEN").strip().upper()

    # Minimum mandatory fields
    if not tender_id or not title:
        return None

    budget = raw.get("estimated_budget_usd")
    try:
        budget_val = float(budget) if budget is not None else None
    except (ValueError, TypeError):
        budget_val = None

    return {
        "id": tender_id,
        "title": title,
        "entity": entity or "Unspecified Entity",
        "deadline": deadline or "TBD",
        "category": category,
        "status": status,
        "estimated_budget_usd": budget_val
    }

def extract_opportunities(raw_input: Union[List[Dict[str, Any]], str, Path]) -> List[Dict[str, Any]]:
    """
    Extracts a list of validated opportunities from raw list, JSON string, or JSON file.
    Deduplicates records by unique ID.
    """
    records: List[Dict[str, Any]] = []

    if isinstance(raw_input, Path) or (isinstance(raw_input, str) and (Path(raw_input).exists() or raw_input.endswith(".json"))):
        path = Path(raw_input)
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = []
    elif isinstance(raw_input, str):
        try:
            data = json.loads(raw_input)
        except Exception:
            data = []
    elif isinstance(raw_input, list):
        data = raw_input
    else:
        data = []

    seen_ids = set()
    for item in data:
        extracted = extract_opportunity_record(item)
        if extracted and extracted["id"] not in seen_ids:
            seen_ids.add(extracted["id"])
            records.append(extracted)

    return records


# --- JSON Filtering Engine ---

def filter_opportunities(
    tenders: List[Dict[str, Any]],
    category: Optional[str] = None,
    status: Optional[str] = None,
    entity: Optional[str] = None,
    keyword: Optional[str] = None,
    min_budget: Optional[float] = None
) -> List[Dict[str, Any]]:
    """
    Filters opportunities based on criteria: category, status, entity, Arabic keyword, or budget.
    """
    results: List[Dict[str, Any]] = []

    for t in tenders:
        if category and category.lower() not in t.get("category", "").lower():
            continue
        if status and t.get("status", "").upper() != status.upper():
            continue
        if entity and entity.lower() not in t.get("entity", "").lower():
            continue
        if min_budget is not None:
            t_budget = t.get("estimated_budget_usd")
            if t_budget is None or t_budget < min_budget:
                continue
        if keyword:
            kw = keyword.lower()
            in_title = kw in t.get("title", "").lower()
            in_entity = kw in t.get("entity", "").lower()
            in_cat = kw in t.get("category", "").lower()
            in_id = kw in t.get("id", "").lower()
            if not (in_title or in_entity or in_cat or in_id):
                continue

        results.append(t)

    return results


# --- Telegram Notification Templates ---

def render_new_tender_template(tender: Dict[str, Any]) -> str:
    """Renders formatted Telegram Markdown alert for a newly indexed tender opportunity."""
    t_id = tender.get("id", "N/A")
    title = tender.get("title", "No Title")
    entity = tender.get("entity", "Unknown Entity")
    deadline = tender.get("deadline", "TBD")
    category = tender.get("category", "General")
    status = tender.get("status", "OPEN")
    budget = tender.get("estimated_budget_usd")
    budget_str = f"${budget:,.2f} USD" if budget else "Competitive Bidding"

    return (
        "📑 *NEW TENDER OPPORTUNITY DETECTED*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🏷 *Tender ID:* `{t_id}`\n"
        f"🏛 *Issuing Entity:* {entity}\n"
        f"📌 *Title:* *{title}*\n"
        f"📁 *Category:* `{category}`\n"
        f"⏱ *Submission Deadline:* `{deadline}`\n"
        f"💰 *Estimated Value:* `{budget_str}`\n"
        f"📊 *Status:* 🟢 `{status}`\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "💼 _Sovereign Fund & Government RFP Tracker_"
    )

def render_tenders_digest_template(
    tenders: List[Dict[str, Any]],
    title: Optional[str] = None
) -> str:
    """Renders summary digest bulletin of multiple active tenders."""
    header = title or "TENDER OPPORTUNITIES SUMMARY DIGEST"
    ts = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())
    lines = [
        f"📊 *{header}*",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"⏱ *Generated:* `{ts}`",
        f"🔢 *Active Matching Tenders:* {len(tenders)}",
        ""
    ]

    for idx, t in enumerate(tenders, 1):
        t_id = t.get("id")
        t_title = t.get("title")
        entity = t.get("entity")
        deadline = t.get("deadline")
        status_icon = "🟢" if t.get("status") == "OPEN" else "⚪"
        lines.append(f"{idx}. {status_icon} *{t_title}*")
        lines.append(f"   └ ID: `{t_id}` | 🏛 {entity}")
        lines.append(f"   └ ⏱ Deadline: `{deadline}`")

    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("💼 _Sovereign Fund & Government RFP Tracker_")
    return "\n".join(lines)

def render_deadline_warning_template(tender: Dict[str, Any], days_left: int) -> str:
    """Renders urgent alert for tenders nearing closure."""
    return (
        "⏳ *URGENT: TENDER DEADLINE EXPIRING SOON*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⚠️ *Time Remaining:* `{days_left}` Day(s) until bid closure!\n"
        f"🏷 *ID:* `{tender.get('id')}`\n"
        f"📌 *Title:* *{tender.get('title')}*\n"
        f"🏛 *Entity:* {tender.get('entity')}\n"
        f"⏱ *Hard Deadline:* `{tender.get('deadline')}`\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "💼 _Immediate Action Required for Submission_"
    )


# --- Dispatcher ---

def send_telegram_notification(
    message: str,
    bot_token: Optional[str] = None,
    chat_id: Optional[str] = None,
    parse_mode: str = "Markdown",
    timeout: int = 5
) -> bool:
    """Sends notification via Telegram Bot API."""
    token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
    chat = chat_id or os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat:
        print("[WARN] Telegram bot credentials not fully provided. Skipping network dispatch.")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps({
        "chat_id": chat,
        "text": message,
        "parse_mode": parse_mode
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            return res.status == 200
    except Exception as e:
        print(f"[ERROR] Failed to send Telegram alert: {e}")
        return False


# --- Core Tracker ---

class TenderTracker:
    def __init__(
        self,
        output_file: Path,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None
    ):
        self.output_file = Path(output_file)
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")

    def scan_opportunities(
        self,
        source: Optional[Union[str, Path, List[Dict[str, Any]]]] = None,
        filter_category: Optional[str] = None,
        filter_status: Optional[str] = None,
        keyword: Optional[str] = None,
        notify: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Extracts, filters, indexes, and stores tender opportunities.
        Dispatches Telegram notifications if enabled.
        """
        print("[*] Initiating tender & procurement opportunities scan...")

        raw_data = source if source is not None else DEFAULT_SIMULATED_PORTAL_DATA
        opportunities = extract_opportunities(raw_data)

        # Apply filtering if criteria specified
        if filter_category or filter_status or keyword:
            opportunities = filter_opportunities(
                opportunities,
                category=filter_category,
                status=filter_status,
                keyword=keyword
            )

        print(f"[+] Found {len(opportunities)} active matching opportunities.")

        self.output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.output_file, "w", encoding="utf-8") as f:
            json.dump(opportunities, f, ensure_ascii=False, indent=2)

        print(f"[+] Tender opportunities catalog saved to: {self.output_file}")

        if notify and opportunities:
            digest = render_tenders_digest_template(opportunities)
            send_telegram_notification(digest, bot_token=self.bot_token, chat_id=self.chat_id)

        return opportunities


def main():
    load_env_file()
    parser = argparse.ArgumentParser(description="Scan, filter, and index government & corporate procurement opportunities.")
    parser.add_argument(
        "--out", "-o",
        default=os.getenv("OUTPUT_PATH", "tenders_report.json"),
        help="Output catalog file (JSON)"
    )
    parser.add_argument(
        "--input", "-i",
        default=None,
        help="Input JSON file or source path (defaults to simulated procurement portal)"
    )
    parser.add_argument(
        "--filter-category",
        default=os.getenv("DEFAULT_FILTER_CATEGORY"),
        help="Filter opportunities by category"
    )
    parser.add_argument(
        "--filter-status",
        default=os.getenv("DEFAULT_FILTER_STATUS"),
        help="Filter opportunities by status (e.g. OPEN, CLOSED)"
    )
    parser.add_argument(
        "--keyword",
        default=None,
        help="Keyword search in title, entity, or category (supports Arabic & English)"
    )
    parser.add_argument(
        "--notify",
        action="store_true",
        help="Dispatch summary digest to configured Telegram chat"
    )
    args = parser.parse_args()

    tracker = TenderTracker(Path(args.out))
    tracker.scan_opportunities(
        source=args.input,
        filter_category=args.filter_category,
        filter_status=args.filter_status,
        keyword=args.keyword,
        notify=args.notify
    )

if __name__ == "__main__":
    main()
