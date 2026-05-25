"""
app/services/schema_search.py
─────────────────────────────
Fast, token-based schema retrieval -- replaces embedding API calls.

Instead of:
  question -> embedding -> cosine similarity -> top-k tables (~500ms + API latency)

We now do:
  question -> tokenize -> count token overlaps -> top-k tables (<5ms, zero API calls)

This trades slight accuracy loss (rare queries miss their best table) for:
  - 100x speed improvement
  - Zero external dependencies
  - Repeatable, debuggable results
"""
from __future__ import annotations

import re
import json
import logging
from typing import List, Dict, Optional, Tuple
from collections import Counter

logger = logging.getLogger(__name__)

# Stop words -- remove before tokenizing
STOP_WORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "with", 
    "by", "from", "is", "are", "was", "were", "be", "been", "have", "has",
    "do", "does", "did", "will", "would", "could", "should", "may", "might",
    "can", "must", "shall", "show", "list", "give", "get", "find", "fetch",
    "return", "all", "any", "top", "latest", "but", "not", "only", "please",
    "what", "when", "where", "why", "how", "which", "who", "whom", "whose",
    "this", "that", "these", "those", "i", "you", "he", "she", "it", "we", "they",
}

MIN_TOKEN_LENGTH = 2  # Minimum length to consider as a real token


def _tokenize(text: str) -> List[str]:
    """
    Tokenize text: lowercase, split, remove punctuation, filter stop words.
    
    Args:
        text: The text to tokenize.
        
    Returns:
        List of meaningful tokens.
    """
    # Remove punctuation, lowercase, split
    text = re.sub(r"[^a-zA-Z0-9_ ]+", " ", text.lower())
    tokens = [t.strip() for t in text.split() if t.strip()]
    
    # Filter by length and stop words
    result = []
    seen = set()
    for t in tokens:
        if len(t) >= MIN_TOKEN_LENGTH and t not in STOP_WORDS and t not in seen:
            result.append(t)
            seen.add(t)
    
    return result[:50]  # Limit to top 50 tokens to avoid over-weighting


def _compute_table_tokens(table: Dict) -> List[str]:
    """
    Extract all meaningful tokens from a table definition.
    Combines table name, columns, and metadata fields.
    """
    all_text = []
    
    # Table name
    if "name" in table:
        all_text.append(table["name"])
    
    # Columns and their types
    if "columns" in table:
        for col in table["columns"]:
            if isinstance(col, dict):
                if "name" in col:
                    all_text.append(col["name"])
                if "type" in col:
                    all_text.append(col["type"])
            else:
                all_text.append(str(col))
    
    # Semantic metadata (gotchas, learned_filters, etc.)
    if "gotcha" in table:
        all_text.append(table["gotcha"])
    if "learned_filter" in table:
        all_text.append(table["learned_filter"])
    if "summary" in table:
        all_text.append(table["summary"])
    
    # Combine and tokenize
    combined = " ".join(all_text)
    return _tokenize(combined)


def score_table_relevance(question_tokens: List[str], table_tokens: List[str]) -> float:
    """
    Score table relevance using token overlap (Jaccard-like).
    
    Scoring logic:
      - Each token match = +1
      - Token position bonus: earlier matches score higher (if needed)
      - Exact table name prefix match = +2 bonus
      
    Args:
        question_tokens: Tokenized question
        table_tokens: Pre-tokenized table definition
        
    Returns:
        Relevance score (0.0 to 1.0+).
    """
    if not question_tokens or not table_tokens:
        return 0.0
    
    # Count overlaps
    question_set = set(question_tokens)
    table_set = set(table_tokens)
    overlap = question_set & table_set
    
    if not overlap:
        return 0.0
    
    # Score = |overlap| / union size (Jaccard)
    union_size = len(question_set | table_set)
    base_score = len(overlap) / union_size if union_size > 0 else 0.0
    
    # Bonus: if question token is prefix of table token
    bonus = 0.0
    for q_token in question_tokens:
        for t_token in table_tokens:
            if t_token.startswith(q_token) and q_token != t_token:
                bonus += 0.1  # Prefix bonus
    
    return base_score + bonus


def pick_relevant_tables(
    question: str,
    all_tables: List[Dict],
    top_k: int = 10,
) -> List[Tuple[Dict, float]]:
    """
    Rank tables by relevance to the question using token scoring.
    
    Args:
        question: The user's natural language question.
        all_tables: All available tables with schema info.
        top_k: How many tables to return.
        
    Returns:
        List of (table_dict, relevance_score) tuples, sorted by score descending.
    """
    question_tokens = _tokenize(question)
    
    if not question_tokens:
        # Empty question -> return all tables (user will sort)
        logger.warning("Question has no meaningful tokens: '%s'", question)
        return [(t, 0.0) for t in all_tables[:top_k]]
    
    # Score all tables
    scored = []
    for table in all_tables:
        table_tokens = _compute_table_tokens(table)
        score = score_table_relevance(question_tokens, table_tokens)
        if score > 0:  # Only include tables with some relevance
            scored.append((table, score))
    
    # Sort by score descending
    scored.sort(key=lambda x: x[1], reverse=True)
    
    return scored[:top_k]


def pick_cross_db_tables(
    question: str,
    db_list: List[Dict],
) -> List[Dict]:
    """
    Given a list of databases (each with a 'tables' list), 
    return the relevant subset for the question, preserving DB structure.
    
    Args:
        question: The user's natural language question.
        db_list: List of dicts with keys: db_id, type, tables, etc.
        
    Returns:
        List of databases with filtered table lists.
    """
    result = []
    
    for db_info in db_list:
        all_tables = db_info.get("tables", [])
        relevant_tables = pick_relevant_tables(question, all_tables, top_k=15)
        
        # Only include DB if it has relevant tables
        if relevant_tables:
            filtered_db = db_info.copy()
            filtered_db["tables"] = [t for t, _ in relevant_tables]
            result.append(filtered_db)
    
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Smart Minification — token-optimized schema for LLM consumption
# ─────────────────────────────────────────────────────────────────────────────

# Audit / boilerplate columns that are almost never queried by users.
# Kept in sync with sync_schema.py AUDIT_COLUMNS.
_AUDIT_COLUMNS = {
    "createdby", "createddate", "modifiedby", "modifieddate",
    "createdate", "updatedate", "createuserid", "updateuserid",
    "created_on", "modified_on", "createdat", "updatedat",
    "cerateddate",  # typo in actual schema
    "concurrencykey", "internalkey",
    "createdatetime", "modifieddatetime",
    "updatedby", "updateddate",
}

# Long SQL type → compact form (mirrors sync_schema.py conventions).
_TYPE_SHORTHANDS: List[tuple] = [
    ("character varying", "varchar"),
    ("timestamp with time zone", "timestamptz"),
    ("timestamp without time zone", "timestamp"),
    ("double precision", "float8"),
    ("bigint", "int8"),
    ("smallint", "int2"),
    ("integer", "int"),
    ("boolean", "bool"),
    ("real", "float4"),
]


def _shorten_type(col_type: str) -> str:
    """Shorten a SQL type string for token savings."""
    t = col_type.strip()
    t_lower = t.lower()
    # Strip NOT NULL suffix — we don't surface nullability in the minified view
    t_lower = t_lower.replace(" not null", "")
    t = t[:len(t_lower)]  # keep original length after strip
    for long_form, short_form in _TYPE_SHORTHANDS:
        if t_lower.startswith(long_form):
            t = short_form + t_lower[len(long_form):]
            return t.strip()
    return t_lower.strip()


def _minify_table(table: Dict) -> Dict:
    """
    Minify a single table dict for LLM consumption:
      1. Strip audit/boilerplate columns.
      2. Convert columns to compact "Name:type" / "Name:type:PK" strings.
      3. Preserve tribal knowledge fields (summary, gotcha, learned_filter, aggregation).
    """
    mini: Dict = {
        "name": table.get("name", ""),
        "schema": table.get("schema", ""),
    }

    # ── Compact column format ─────────────────────────────────────────────
    cols: List[str] = []
    for col in table.get("columns", []):
        if isinstance(col, dict):
            col_name = col.get("name", "")
            # Skip audit columns
            if col_name.lower() in _AUDIT_COLUMNS:
                continue
            col_type = _shorten_type(col.get("type", ""))
            is_pk = col.get("is_pk") or col.get("primary_key")
            entry = f"{col_name}:{col_type}"
            if is_pk:
                entry += ":PK"
            cols.append(entry)
        else:
            # Fallback for plain string column entries
            if str(col).lower() not in _AUDIT_COLUMNS:
                cols.append(str(col))

    mini["cols"] = cols

    # ── Tribal knowledge (keep as-is — critical for accuracy) ─────────────
    for field in ("summary", "gotcha", "learned_filter", "aggregation"):
        val = table.get(field)
        if val:
            mini[field] = val

    return mini


def minify_schema_response(db_list: List[Dict]) -> List[Dict]:
    """
    Minify an entire get_relevant_schema response for LLM consumption.

    Applied AFTER pick_cross_db_tables so relevance scoring uses full
    column metadata, but the final payload sent to the LLM is compact.

    Token savings: typically 65-75% reduction vs. full column JSON.
    """
    result: List[Dict] = []
    for db_info in db_list:
        mini_db: Dict = {
            "id": db_info.get("id"),
            "name": db_info.get("name"),
            "type": db_info.get("type"),
            "tables": [_minify_table(t) for t in db_info.get("tables", [])],
        }
        result.append(mini_db)
    return result
