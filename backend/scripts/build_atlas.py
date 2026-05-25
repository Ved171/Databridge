import asyncio
import json
import logging
import os
import sys
from collections import defaultdict
from typing import Any, Dict, List, Optional

# Setup paths to import from app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy.future import select
from app.core.database import AsyncSessionLocal
from app.models import Connector

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("atlas_builder")

# ── Security / PII column name patterns ───────────────────────────────────────
_PII_COLUMNS = {
    "email", "emailaddress", "email_address",
    "ssn", "socialsecuritynumber",
    "passport", "passportnumber",
    "dob", "dateofbirth", "birthdate",
    "nationalid", "national_id",
    "pan", "pannumber", "aadhar", "aadharnumber",
}
_SENSITIVE_COLUMNS = {
    "mobileno", "mobile", "mobile_no", "phone", "phoneno", "phone_no",
    "contactno", "contact_no", "cellphone",
    "salary", "ctc", "compensation", "wage",
    "bankaccount", "bank_account", "accountnumber", "account_number",
    "creditcard", "credit_card", "cardnumber", "card_number",
    "password", "passwordhash", "password_hash",
    "ipaddress", "ip_address",
}
_CONFIDENTIAL_COLUMNS = {
    "address", "homeaddress", "home_address", "permanentaddress",
    "latitude", "longitude", "geolocation",
}

# ── Soft-delete / active-flag patterns ────────────────────────────────────────
_SOFT_DELETE_FILTER: Dict[str, str] = {
    "isdeleted":  "Soft deletion enabled; filter by isdeleted=false",
    "is_deleted": "Soft deletion enabled; filter by is_deleted=false",
    "isactive":   "Active-flag table; filter by isactive=true",
    "is_active":  "Active-flag table; filter by is_active=true",
    "active":     "Active-flag column present; filter by active=true",
    "deleted":    "Soft deletion enabled; filter by deleted=false",
    "isenabled":  "Enable-flag table; filter by isenabled=true",
    "is_enabled": "Enable-flag table; filter by is_enabled=true",
}

# ── Unit heuristics: substring -> unit label ───────────────────────────────────
_UNIT_HINTS: List[tuple] = [
    ("monthofexp",  "Months"),
    ("months",      "Months"),
    ("yearofexp",   "Years"),
    ("totalexp",    "Years"),
    ("experience",  "Years"),          # default; overridden if "month" present
    ("amount",      "Currency"),
    ("price",       "Currency"),
    ("cost",        "Currency"),
    ("salary",      "Currency"),
    ("revenue",     "Currency"),
    ("weight",      "Kilograms"),
    ("height",      "Centimeters"),
    ("distance",    "Kilometers"),
    ("duration",    "Seconds"),
    ("percentage",  "Percent"),
    ("percent",     "Percent"),
    ("rate",        "Percent"),
    ("count",       "Count"),
    ("qty",         "Count"),
    ("quantity",    "Count"),
    ("age",         "Years"),
    ("score",       "Score"),
    ("rating",      "Score"),
    ("latitude",    "Degrees"),
    ("longitude",   "Degrees"),
]


def _generate_summary(table_name: str, columns: List[str]) -> str:
    """Rule-based fallback summary generator."""
    short = table_name.lower()
    if "employee" in short:
        return "Master directory of employee / staff records."
    if "order" in short:
        return "Records of customer orders and their line items."
    if "product" in short:
        return "Product catalogue with pricing and inventory details."
    if "appraisal" in short:
        return "Performance appraisal and review data."
    return f"Data table '{table_name}' containing {len(columns)} columns."

def _detect_units(columns: List[str]) -> Dict[str, str]:
    """Map column names to measurement units."""
    result: Dict[str, str] = {}
    for col in columns:
        cl = col.lower()
        for substr, unit in _UNIT_HINTS:
            if substr in cl:
                if col in result and "month" in cl:
                    result[col] = "Months"
                elif col not in result:
                    result[col] = unit
                break
    return result

def _detect_security(columns: List[str]) -> Dict[str, str]:
    """Classify columns as PII, Sensitive, or Confidential."""
    result: Dict[str, str] = {}
    for col in columns:
        cl = col.lower().replace("_", "").replace(" ", "")
        if cl in _PII_COLUMNS or any(p in cl for p in ("email", "ssn", "passport", "aadhaar", "aadhar", "pan")):
            result[col] = "PII"
        elif cl in _SENSITIVE_COLUMNS or any(s in cl for s in ("mobile", "phone", "salary", "bank", "card", "password", "ctc")):
            result[col] = "Sensitive"
        elif cl in _CONFIDENTIAL_COLUMNS or any(c in cl for c in ("address", "latitude", "longitude")):
            result[col] = "Confidential"
    return result

def _detect_gotchas(columns: List[str]) -> List[str]:
    """Emit human-readable warnings about common query pitfalls for this table."""
    warnings: List[str] = []
    col_set = set(c.lower() for c in columns)

    # Soft-delete / active flags
    for flag, message in _SOFT_DELETE_FILTER.items():
        if flag in col_set:
            warnings.append(message)

    # Date/time columns that are commonly NULL in legacy data
    nullable_date_hints = {
        "joiningdate":    "JoiningDate",
        "joining_date":   "JoiningDate",
        "dateofjoining":  "DateOfJoining",
        "date_of_joining":"DateOfJoining",
        "terminationdate":"TerminationDate",
        "exitdate":       "ExitDate",
        "dob":            "DOB",
        "dateofbirth":    "DateOfBirth",
    }
    for col_key, display in nullable_date_hints.items():
        if col_key in col_set:
            warnings.append(f"{display} can be NULL for records migrated from legacy systems.")

    # Wide tables -- discourage SELECT *
    if len(columns) > 20:
        warnings.append(f"Wide table ({len(columns)} columns) -- avoid SELECT *; always project only needed columns.")

    # Status column and deleted flag (double-filter trap)
    has_status = any(c in col_set for c in ("status", "statusid", "status_id"))
    has_deleted = any(c in col_set for c in _SOFT_DELETE_FILTER.keys())
    if has_status and has_deleted:
        warnings.append("Table has both a status column and a soft-delete flag -- apply BOTH filters to avoid counting inactive/deleted rows.")

    return warnings

async def build_atlas():
    """Iterates through all Connectors, enriches the schema cache with Atlas insights, and saves to DB."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Connector).where(Connector.is_active == True))
        connectors = result.scalars().all()
        
        updated_count = 0
        for connector in connectors:
            if not connector.schema_cache:
                continue
                
            logger.info(f"Enriching Atlas for Connector: {connector.name} ({connector.id})")
            tables = connector.schema_cache.get("tables", [])
            
            for table in tables:
                table_name = table.get("name", "")
                columns = [c.get("name", "") for c in table.get("columns", [])]
                
                # Apply Atlas Heuristics
                if "summary" not in table or not table["summary"]:
                    table["summary"] = _generate_summary(table_name, columns)
                
                table["units"] = _detect_units(columns)
                table["security"] = _detect_security(columns)
                
                # Merge existing gotchas from `record_discovery` with automated ones
                existing_gotchas = table.get("gotchas", [])
                auto_gotchas = _detect_gotchas(columns)
                # Keep unique gotchas
                table["gotchas"] = list(set(existing_gotchas + auto_gotchas))
                
            # Update schema_cache in DB
            connector.schema_cache["tables"] = tables
            session.add(connector)
            updated_count += 1
            
        await session.commit()
        logger.info(f"Atlas Builder complete! Enriched {updated_count} connectors.")

if __name__ == "__main__":
    asyncio.run(build_atlas())
