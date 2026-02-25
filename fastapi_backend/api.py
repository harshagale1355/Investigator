"""
FastAPI wrapper for the log analyzer backend.
Run: uvicorn fastapi_backend.api:app --reload
"""

import re
import io
import os
import threading
from pathlib import Path
from collections import Counter
from typing import Optional

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain_core.documents import Document

from backend.retriever import retriever
from backend.query     import query

# ── Persistent upload directory ────────────────────────────────────────────────
UPLOAD_DIR = Path("./uploaded_logs")
UPLOAD_DIR.mkdir(exist_ok=True)

# ── Error patterns ─────────────────────────────────────────────────────────────
ERROR_PATTERNS = {
    r'\bERROR\b'                   : 'General Error',
    r'\bFAIL(ED)?\b'              : 'Failure',
    r'\bEXCEPTION\b'              : 'Exception',
    r'\bCRITICAL\b'               : 'Critical Error',
    r'\bFATAL\b'                  : 'Fatal Error',
    r'\bPANIC\b'                  : 'System Panic',
    r'\bTIMEOUT\b'                : 'Timeout',
    r'\bDENIED\b'                 : 'Access Denied',
    r'\bREJECTED\b'               : 'Request Rejected',
    r'\bABORT\b'                  : 'Operation Aborted',
    r'\bSEGMENTATION FAULT\b'     : 'Segmentation Fault',
    r'\bOUT OF MEMORY\b'          : 'Out of Memory',
    r'\bSTACK TRACE\b'            : 'Stack Trace',
    r'\bTRACEBACK\b'              : 'Python Traceback',
    r'\bUNHANDLED\b'              : 'Unhandled Error',
    r'HTTP/\d\.\d"\s(5\d\d|4\d\d)': 'HTTP Error',
    r'\s(5\d\d|4\d\d)\s'          : 'HTTP Status Code',
    r'\[error\]'                   : 'Nginx/Apache Error',
    r'\[emerg\]'                   : 'Emergency Error',
    r'\[crit\]'                    : 'Critical Log',
    r'\[alert\]'                   : 'Alert',
}

CATEGORY_KEYWORDS = {
    'database'   : ['database','sql','mysql','postgres','oracle','mongodb','query','transaction'],
    'performance': ['timeout','slow','latency','performance','bottleneck','response time'],
    'security'   : ['auth','authentication','login','password','permission','access','unauthorized','forbidden'],
    'resource'   : ['memory','heap','disk','cpu','resource','out of memory','oom','disk full'],
    'network'    : ['network','connection','socket','http','https','tcp','udp','connection refused'],
    'io'         : ['file','io','read','write','permission denied','file not found','eof'],
    'application': ['exception','null pointer','index out of bounds','type error','syntax error'],
}

# ── Global state ───────────────────────────────────────────────────────────────
_state: dict = {
    "qa_chain"   : None,
    "filename"   : None,
    "saved_path" : None,   # Path to the saved log file on disk
    "rag_status" : "idle", # idle | building | ready | error
    "rag_error"  : None,
}

# ── Helpers ────────────────────────────────────────────────────────────────────

def _categorize(line: str) -> str:
    ll = line.lower()
    for cat, kws in CATEGORY_KEYWORDS.items():
        if any(k in ll for k in kws):
            return cat
    return 'application'


def _extract_code(line: str) -> Optional[str]:
    m = re.search(r'\b(\d{3})\b', line)
    if m and m.group(1).startswith(('4', '5')):
        return f"HTTP_{m.group(1)}"
    for p in [r'ERR[_-](\w+)', r'ERROR[_-](\w+)', r'code[:\s]+(\w+)',
              r'error\s+code\s*[=:]\s*(\w+)', r'\[(\w+)\]']:
        mm = re.search(p, line, re.IGNORECASE)
        if mm:
            return mm.group(1).upper()
    return None


def _stream_scan_bytes(raw_bytes: bytes, selected_patterns: list) -> dict:
    """
    Stream-scan raw bytes line-by-line in memory.
    The full file is never written to disk — only matched error lines are saved.
    """
    compiled = [
        (re.compile(p, re.IGNORECASE), desc)
        for p, desc in ERROR_PATTERNS.items()
        if p in selected_patterns
    ]

    errors       = []
    categories   = Counter()
    codes        = Counter()
    pattern_hits = Counter()
    total_lines  = 0

    stream = io.StringIO(raw_bytes.decode("utf-8", errors="replace"))
    for line in stream:
        total_lines += 1
        line = line.rstrip("\n")

        for pat, desc in compiled:
            if pat.search(line):
                cat  = _categorize(line)
                code = _extract_code(line)
                errors.append({
                    "line_number"    : total_lines,
                    "content"        : line,
                    "category"       : cat,
                    "error_code"     : code,
                    "matched_pattern": desc,
                })
                categories[cat]    += 1
                pattern_hits[desc] += 1
                if code:
                    codes[code] += 1
                break

    return {
        "total_lines"    : total_lines,
        "error_count"    : len(errors),
        "errors"         : errors,
        "categories"     : dict(categories),
        "error_codes"    : dict(codes),
        "pattern_matches": dict(pattern_hits),
    }


def _build_rag_in_background(error_lines: list, filename: str) -> None:
    """
    Background thread.
    Vectorises only the matched error lines — not the full file.
    This matches the original Streamlit behaviour exactly.
    """
    _state["rag_status"] = "building"
    _state["qa_chain"]   = None
    try:
        error_text = "\n".join(error_lines)
        doc = Document(page_content=error_text, metadata={"source": filename})
        _state["qa_chain"]   = retriever(doc)
        _state["rag_status"] = "ready"
    except Exception as e:
        _state["rag_status"] = "error"
        _state["rag_error"]  = str(e)


# ── App ────────────────────────────────────────────────────────────────────────

app = FastAPI(title="Log Analyzer API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Schemas ────────────────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    question: str

class RescanRequest(BaseModel):
    patterns: list[str]

# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.get("/patterns")
def get_patterns():
    return {"patterns": list(ERROR_PATTERNS.keys()), "descriptions": ERROR_PATTERNS}


@app.post("/upload")
async def upload_log(file: UploadFile = File(...)):
    """
    1. Save the uploaded file to ./uploaded_logs/<filename>  (persists on disk).
    2. Stream-scan from disk line-by-line  →  fast, ~10-15 s for 57 MB.
    3. Build RAG index in background from error lines only.
    4. Return scan results immediately.
    """
    # ── Stream-scan from raw bytes in memory (never write the full file) ───────
    safe_name = Path(file.filename).name
    raw_bytes = await file.read()

    _state["filename"]   = safe_name
    _state["rag_status"] = "building"
    _state["rag_error"]  = None

    # Scan the full file in memory
    result = _stream_scan_bytes(raw_bytes, list(ERROR_PATTERNS.keys()))
    result["filename"]   = safe_name
    result["rag_status"] = "building"

    # ── Save ONLY the error lines to disk ─────────────────────────────────────
    error_lines = [e["content"] for e in result["errors"]]
    saved_path  = UPLOAD_DIR / safe_name
    saved_path.write_text("\n".join(error_lines), encoding="utf-8")
    _state["saved_path"] = saved_path
    threading.Thread(
        target=_build_rag_in_background,
        args=(error_lines, safe_name),
        daemon=True,
    ).start()

    result["errors"] = result["errors"][:500]
    return result


@app.post("/rescan")
def rescan(req: RescanRequest):
    """
    Re-scan the saved error-lines file with a custom pattern subset.
    Since only error lines were saved, this is fast and lightweight.
    """
    saved_path = _state.get("saved_path")
    if not saved_path or not Path(saved_path).exists():
        raise HTTPException(400, "No log file on disk. Upload a file first.")

    raw_bytes = Path(saved_path).read_bytes()
    result = _stream_scan_bytes(raw_bytes, req.patterns)
    result["filename"] = _state["filename"]
    result["errors"]   = result["errors"][:500]
    return result


@app.get("/rag-status")
def rag_status():
    """Angular polls this to know when AI chat becomes available."""
    return {
        "status"   : _state["rag_status"],
        "filename" : _state["filename"],
        "saved"    : _state["saved_path"] is not None and Path(_state["saved_path"]).exists(),
        "error"    : _state["rag_error"],
    }


@app.get("/status")
def status():
    return {
        "ready"   : _state["rag_status"] == "ready",
        "filename": _state["filename"],
        "saved"   : _state["saved_path"] is not None and Path(_state["saved_path"]).exists(),
    }


@app.post("/query")
def query_log(req: QueryRequest):
    if _state["rag_status"] == "building":
        raise HTTPException(202, "RAG index is still building — please wait a moment.")
    if _state["qa_chain"] is None:
        raise HTTPException(400, "No log uploaded yet.")
    try:
        return query(_state["qa_chain"], req.question)
    except Exception as e:
        raise HTTPException(500, f"LLM query failed: {e}")