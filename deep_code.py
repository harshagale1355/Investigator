from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
import os
import re
import tempfile
import json
from datetime import datetime
import threading
import queue

app = Flask(__name__)
CORS(app)

# Store processing results in memory (use Redis in production)
processing_results = {}
result_queue = queue.Queue()

# Enhanced error patterns
ERROR_PATTERNS = [
    r'\bERROR\b',
    r'\bFAIL\b',
    r'\bFAILED\b',
    r'\bEXCEPTION\b',
    r'\bCRITICAL\b',
    r'\bFATAL\b',
    r'\bPANIC\b',
    r'\bTIMEOUT\b',
    r'\bDENIED\b',
    r'\bREJECTED\b',
    r'\bABORT\b',
    r'\bSEGMENTATION FAULT\b',
    r'\bOUT OF MEMORY\b',
    r'\bSTACK TRACE\b',
    r'\bTRACEBACK\b',
    r'\bUNHANDLED\b',
    r'\bHTTP/\d\.\d"\s(5\d\d|4\d\d)',
    r'\s(5\d\d|4\d\d)\s',
    r'\[error\]',
    r'\[emerg\]',
    r'\[crit\]',
    r'\[alert\]',
]

def detect_log_format(first_lines):
    """Detect log format for smarter parsing"""
    sample = ' '.join(first_lines[:5])
    
    if '"level":"error"' in sample or '"severity":"ERROR"' in sample:
        return 'json'
    elif re.search(r'\d+\.\d+\.\d+\.\d+.*\[.*\].*".*"', sample):
        return 'apache_nginx'
    elif re.search(r'\[\d{4}-\d{2}-\d{2}.*\].*\[(ERROR|error)\]', sample):
        return 'bracketed_timestamp'
    elif re.search(r'\d{4}-\d{2}-\d{2}.*ERROR', sample):
        return 'timestamp_prefix'
    else:
        return 'plain'

def categorize_error(line):
    """Categorize error type"""
    line_lower = line.lower()
    
    if any(word in line_lower for word in ['database', 'sql', 'mysql', 'postgres', 'query']):
        return 'database'
    elif any(word in line_lower for word in ['timeout', 'slow', 'latency', 'performance']):
        return 'performance'
    elif any(word in line_lower for word in ['memory', 'heap', 'disk', 'cpu', 'resource']):
        return 'resource'
    elif any(word in line_lower for word in ['auth', 'login', 'password', 'permission', 'access']):
        return 'security'
    elif any(word in line_lower for word in ['network', 'connection', 'socket', 'http']):
        return 'network'
    elif any(word in line_lower for word in ['file', 'io', 'read', 'write']):
        return 'io'
    else:
        return 'application'

def extract_error_code(line):
    """Try to extract error codes like HTTP 500, ERR_123, etc."""
    # HTTP status codes
    http_match = re.search(r'\b(\d{3})\b', line)
    if http_match and http_match.group(1).startswith(('4', '5')):
        return f"HTTP_{http_match.group(1)}"
    
    # Common error codes
    code_patterns = [
        r'ERR_(\w+)',
        r'ERROR_(\w+)',
        r'code[:\s]+(\w+)',
        r'\[(\w+)\]',
    ]
    
    for pattern in code_patterns:
        match = re.search(pattern, line, re.IGNORECASE)
        if match:
            return match.group(1)
    
    return None

def process_log_file(filepath, filters=None, max_results=10000):
    """Process log file efficiently with streaming"""
    if filters is None:
        filters = ERROR_PATTERNS
    
    compiled_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in filters]
    
    results = []
    categories = {}
    error_codes = {}
    line_count = 0
    error_count = 0
    
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        for line_number, line in enumerate(f, 1):
            line_count += 1
            
            # Check if line matches any error pattern
            is_error = False
            matched_pattern = None
            
            for pattern in compiled_patterns:
                if pattern.search(line):
                    is_error = True
                    matched_pattern = pattern.pattern
                    break
            
            if is_error:
                error_count += 1
                
                # Categorize error
                category = categorize_error(line)
                categories[category] = categories.get(category, 0) + 1
                
                # Extract error code
                error_code = extract_error_code(line)
                if error_code:
                    error_codes[error_code] = error_codes.get(error_code, 0) + 1
                
                # Store result (limit to max_results)
                if error_count <= max_results:
                    results.append({
                        'line_number': line_number,
                        'content': line.strip(),
                        'category': category,
                        'error_code': error_code,
                        'matched_pattern': matched_pattern
                    })
            
            # Yield progress every 10000 lines
            if line_count % 10000 == 0:
                yield {
                    'type': 'progress',
                    'processed': line_count,
                    'errors_found': error_count
                }
    
    # Final result
    yield {
        'type': 'complete',
        'total_lines': line_count,
        'total_errors': error_count,
        'results': results,
        'categories': categories,
        'error_codes': error_codes,
        'error_rate': (error_count / line_count * 100) if line_count > 0 else 0
    }

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/process', methods=['POST'])
def process_logs():
    """API endpoint for log processing"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    # Get custom filters if provided
    custom_filters = request.form.get('filters', '').split(',')
    custom_filters = [f.strip() for f in custom_filters if f.strip()]
    
    # Use custom filters or default patterns
    filters = custom_filters if custom_filters else ERROR_PATTERNS
    
    # Save uploaded file temporarily
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.log')
    file.save(temp_file.name)
    temp_file.close()
    
    try:
        # Process the file
        result = None
        for progress in process_log_file(temp_file.name, filters):
            if progress['type'] == 'complete':
                result = progress
                break
        
        # Clean up temp file
        os.unlink(temp_file.name)
        
        if result:
            return jsonify({
                'success': True,
                'summary': {
                    'total_lines': result['total_lines'],
                    'total_errors': result['total_errors'],
                    'error_rate': round(result['error_rate'], 2),
                    'categories': result['categories'],
                    'top_error_codes': dict(sorted(
                        result['error_codes'].items(), 
                        key=lambda x: x[1], 
                        reverse=True
                    )[:10])
                },
                'errors': result['results'][:1000],  # Limit initial display
                'has_more': len(result['results']) > 1000,
                'total_results': len(result['results'])
            })
        
        return jsonify({'error': 'Processing failed'}), 500
        
    except Exception as e:
        # Clean up on error
        if os.path.exists(temp_file.name):
            os.unlink(temp_file.name)
        return jsonify({'error': str(e)}), 500

@app.route('/api/process-large', methods=['POST'])
def process_large_logs():
    """Process large files asynchronously"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    
    # Generate unique job ID
    job_id = datetime.now().strftime('%Y%m%d_%H%M%S_') + file.filename
    
    # Save file
    upload_dir = 'uploads'
    os.makedirs(upload_dir, exist_ok=True)
    filepath = os.path.join(upload_dir, job_id)
    file.save(filepath)
    
    # Start processing in background thread
    def process_in_background():
        try:
            results = []
            for progress in process_log_file(filepath, ERROR_PATTERNS):
                if progress['type'] == 'complete':
                    processing_results[job_id] = progress
                    break
            # Clean up file after processing
            os.unlink(filepath)
        except Exception as e:
            processing_results[job_id] = {'error': str(e)}
    
    thread = threading.Thread(target=process_in_background)
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'job_id': job_id,
        'message': 'Processing started in background',
        'status_url': f'/api/status/{job_id}',
        'results_url': f'/api/results/{job_id}'
    })

@app.route('/api/status/<job_id>')
def get_status(job_id):
    """Check processing status"""
    if job_id in processing_results:
        return jsonify({
            'status': 'complete',
            'result_available': True
        })
    return jsonify({'status': 'processing'})

@app.route('/api/results/<job_id>')
def get_results(job_id):
    """Get processing results"""
    if job_id not in processing_results:
        return jsonify({'error': 'Job not found or still processing'}), 404
    
    result = processing_results[job_id]
    if 'error' in result:
        return jsonify({'error': result['error']}), 500
    
    return jsonify({
        'success': True,
        'summary': {
            'total_lines': result['total_lines'],
            'total_errors': result['total_errors'],
            'error_rate': round(result['error_rate'], 2),
            'categories': result['categories']
        },
        'errors': result['results'][:1000],
        'has_more': len(result['results']) > 1000
    })

@app.route('/api/export/<job_id>')
def export_results(job_id):
    """Export results as CSV"""
    if job_id not in processing_results:
        return jsonify({'error': 'Job not found'}), 404
    
    result = processing_results[job_id]
    
    # Create CSV content
    csv_lines = ['Line Number,Category,Error Code,Content']
    for error in result['results']:
        # Escape quotes and commas in content
        content = error['content'].replace('"', '""').replace(',', ';')
        csv_lines.append(
            f'{error["line_number"]},'
            f'{error["category"]},'
            f'{error.get("error_code", "")},'
            f'"{content}"'
        )
    
    csv_content = '\n'.join(csv_lines)
    
    # Create temp file for download
    temp_csv = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv', encoding='utf-8')
    temp_csv.write(csv_content)
    temp_csv.close()
    
    return send_file(
        temp_csv.name,
        as_attachment=True,
        download_name=f'errors_{job_id}.csv',
        mimetype='text/csv'
    )

if __name__ == '__main__':
    app.run(debug=True, port=5000)