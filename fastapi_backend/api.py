"""
FastAPI wrapper for the log analyzer backend.
Run: uvicorn fastapi_backend.api:app --reload
"""

import io
import threading
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain_core.documents import Document

# ── Your existing backend modules (unchanged) ──────────────────────────────────
from backend.retriever  import retriever
from backend.query      import query
from backend.log_filter import (
    ERROR_PATTERNS,
    categorize_error,
    extract_error_code,
    process_log_stream,
)

# ── Persistent storage for error-only log files ────────────────────────────────
UPLOAD_DIR = Path("./uploaded_logs")
UPLOAD_DIR.mkdir(exist_ok=True)

# ── Global state ───────────────────────────────────────────────────────────────
_state: dict = {
    "qa_chain"   : None,
    "filename"   : None,
    "saved_path" : None,
    "rag_status" : "idle",   # idle | building | ready | error
    "rag_error"  : None,
}

# ── Helpers ────────────────────────────────────────────────────────────────────

def _scan_stream(raw_bytes: bytes, selected_patterns: list) -> dict:
    """
    Wraps your existing process_log_stream() which already streams line-by-line.
    We just feed it an io.TextIOWrapper over the raw bytes.
    """
    text_stream = io.TextIOWrapper(
        io.BytesIO(raw_bytes), encoding="utf-8", errors="replace"
    )
    errors, stats = process_log_stream(text_stream, selected_patterns)

    return {
        "total_lines"    : stats["total_lines"],
        "error_count"    : stats["error_count"],
        "errors"         : [
            {
                "line_number"    : e["line_number"],
                "content"        : e["content"],
                "category"       : e["category"],
                "error_code"     : e["error_code"],
                "matched_pattern": e["matched_pattern"],
            }
            for e in errors
        ],
        "categories"     : dict(stats["categories"]),
        "error_codes"    : dict(stats["error_codes"]),
        "pattern_matches": dict(stats["pattern_matches"]),
    }


def _build_rag_in_background(error_lines: list, filename: str) -> None:
    """
    Background thread.
    Vectorises only the matched error lines — mirrors original Streamlit behaviour.
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
    allow_origins=["http://localhost:4200", "http://localhost"],
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
    """Return all available error patterns from log_filter.py."""
    return {"patterns": list(ERROR_PATTERNS.keys()), "descriptions": ERROR_PATTERNS}


@app.post("/upload")
async def upload_log(file: UploadFile = File(...)):
    """
    1. Read bytes into memory — full file is never written to disk.
    2. Scan using your existing process_log_stream() from log_filter.py.
    3. Save ONLY the matched error lines to ./uploaded_logs/.
    4. Build RAG index in background from those error lines.
    5. Return scan results immediately.
    """
    safe_name = Path(file.filename).name
    raw_bytes = await file.read()

    _state["filename"]   = safe_name
    _state["rag_status"] = "building"
    _state["rag_error"]  = None

    # ── Scan using your existing log_filter logic ──────────────────────────────
    result = _scan_stream(raw_bytes, list(ERROR_PATTERNS.keys()))
    result["filename"]   = safe_name
    result["rag_status"] = "building"

    # ── Save only the error lines to disk ─────────────────────────────────────
    error_lines = [e["content"] for e in result["errors"]]
    saved_path  = UPLOAD_DIR / safe_name
    saved_path.write_text("\n".join(error_lines), encoding="utf-8")
    _state["saved_path"] = saved_path

    # ── Build RAG in background ────────────────────────────────────────────────
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
    Uses your existing process_log_stream() from log_filter.py.
    """
    saved_path = _state.get("saved_path")
    if not saved_path or not Path(saved_path).exists():
        raise HTTPException(400, "No log file on disk. Upload a file first.")

    raw_bytes = Path(saved_path).read_bytes()
    result = _scan_stream(raw_bytes, req.patterns)
    result["filename"] = _state["filename"]
    result["errors"]   = result["errors"][:500]
    return result


@app.get("/rag-status")
def rag_status():
    """Angular polls this to know when AI chat becomes available."""
    return {
        "status"  : _state["rag_status"],
        "filename": _state["filename"],
        "saved"   : _state["saved_path"] is not None and Path(_state["saved_path"]).exists(),
        "error"   : _state["rag_error"],
    }


@app.get("/status")
def status():
    return {
        "ready"   : _state["rag_status"] == "ready",
        "filename": _state["filename"],
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