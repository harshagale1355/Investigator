import io
import re
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import time
from collections import Counter
import base64


ERROR_PATTERNS = {
    r'\bERROR\b': 'General Error',
    r'\bFAIL(ED)?\b': 'Failure',
    r'\bEXCEPTION\b': 'Exception',
    r'\bCRITICAL\b': 'Critical Error',
    r'\bFATAL\b': 'Fatal Error',
    r'\bPANIC\b': 'System Panic',
    r'\bTIMEOUT\b': 'Timeout',
    r'\bDENIED\b': 'Access Denied',
    r'\bREJECTED\b': 'Request Rejected',
    r'\bABORT\b': 'Operation Aborted',
    r'\bSEGMENTATION FAULT\b': 'Segmentation Fault',
    r'\bOUT OF MEMORY\b': 'Out of Memory',
    r'\bSTACK TRACE\b': 'Stack Trace',
    r'\bTRACEBACK\b': 'Python Traceback',
    r'\bUNHANDLED\b': 'Unhandled Error',
    r'HTTP/\d\.\d"\s(5\d\d|4\d\d)': 'HTTP Error',
    r'\s(5\d\d|4\d\d)\s': 'HTTP Status Code',
    r'\[error\]': 'Nginx/Apache Error',
    r'\[emerg\]': 'Emergency Error',
    r'\[crit\]': 'Critical Log',
    r'\[alert\]': 'Alert',
}

def categorize_error(line):
    """Categorize error type with improved detection"""
    line_lower = line.lower()
    
    category_keywords = {
        'database': ['database', 'sql', 'mysql', 'postgres', 'oracle', 'mongodb', 'query', 'transaction'],
        'performance': ['timeout', 'slow', 'latency', 'performance', 'bottleneck', 'response time'],
        'security': ['auth', 'authentication', 'login', 'password', 'permission', 'access', 'unauthorized', 'forbidden'],
        'resource': ['memory', 'heap', 'disk', 'cpu', 'resource', 'out of memory', 'oom', 'disk full'],
        'network': ['network', 'connection', 'socket', 'http', 'https', 'tcp', 'udp', 'connection refused'],
        'io': ['file', 'io', 'read', 'write', 'permission denied', 'file not found', 'eof'],
        'application': ['exception', 'null pointer', 'index out of bounds', 'type error', 'syntax error']
    }
    
    for category, keywords in category_keywords.items():
        if any(keyword in line_lower for keyword in keywords):
            return category
    return 'application'

def extract_error_code(line):
    """Extract error codes from log line"""
    # HTTP status codes
    http_match = re.search(r'\b(\d{3})\b', line)
    if http_match and http_match.group(1).startswith(('4', '5')):
        return f"HTTP_{http_match.group(1)}" #This returns the error code like HTTP_404 OR HTTP_500

    code_patterns = [
        r'ERR[_-](\w+)', #ERR_123,ERR-DBFAIL
        r'ERROR[_-](\w+)', #ERROR_TIMEOUT,ERROR-401
        r'code[:\s]+(\w+)', #code: 404,code  DB_ERR
        r'error\s+code\s*[=:]\s*(\w+)', #error code = 500,error code:AUTH_FAIL
        r'\[(\w+)\]', #[ERROR123],[DB_FAIL]
    ]
    for pattern in code_patterns:
        match = re.search(pattern, line, re.IGNORECASE)
        if match:
            return match.group(1).upper()  #Finds pattern in the line
    
    return None


def process_log_stream(text_stream, selected_patterns, progress_bar=None, status_text=None):
    """Process log file stream with progress tracking"""
    errors = []
    stats = {
        'total_lines': 0,
        'error_count': 0,
        'categories': Counter(),
        'error_codes': Counter(),
        'pattern_matches': Counter()
    }
    
    # Compile selected patterns
    compiled_patterns = [(re.compile(pattern, re.IGNORECASE), desc) 
                         for pattern, desc in ERROR_PATTERNS.items() 
                         if pattern in selected_patterns]  #This stores regex and thier description in the compiled patterns
                    
    
    # Read and process line by line
    line_buffer = []
    chunk_size = 10000  # Process in chunks for progress updates
    
    for line_num, line in enumerate(text_stream, 1):
        line = line.rstrip('\n')
        stats['total_lines'] += 1
        
        # Check if line matches any selected pattern
        matched = False
        matched_pattern = None
        
        for pattern, desc in compiled_patterns:
            if pattern.search(line):
                matched = True
                matched_pattern = desc
                stats['pattern_matches'][desc] += 1
                break
        
        if matched:
            stats['error_count'] += 1
            
            # Categorize error
            category = categorize_error(line)
            stats['categories'][category] += 1
            
            # Extract error code
            error_code = extract_error_code(line)
            if error_code:
                stats['error_codes'][error_code] += 1
            
            # Store error details
            errors.append({
                'line_number': line_num,
                'content': line,
                'category': category,
                'error_code': error_code,
                'matched_pattern': matched_pattern
            })
        
        # Store line for context (keep last few lines)
        line_buffer.append(line)
        if len(line_buffer) > 10:
            line_buffer.pop(0)
        
        # Update progress every chunk_size lines
        if line_num % chunk_size == 0:
            if progress_bar:
                progress_bar.progress(min(line_num / 1000000, 1.0))  # Cap at 1M lines for progress
            if status_text:
                status_text.text(f"Processed {line_num:,} lines... Found {stats['error_count']:,} errors")
    
    return errors, stats

def create_download_link(df, filename="errors_export.csv"):
    """Create a download link for DataFrame"""
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="{filename}">📥 Download CSV</a>'
    return href


        
