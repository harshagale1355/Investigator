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


