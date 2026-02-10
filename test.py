import streamlit as st
import io
import re
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import time
from collections import Counter
import base64

# Set page config
st.set_page_config(
    page_title="Log Error Analyzer",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        background: linear-gradient(90deg, #FF4B4B, #FF7A45);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        margin-bottom: 1rem;
    }
    
    .stat-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 10px;
        color: white;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    
    .stat-value {
        font-size: 2.5rem;
        font-weight: bold;
        margin-bottom: 5px;
    }
    
    .stat-label {
        font-size: 0.9rem;
        opacity: 0.9;
    }
    
    .error-line {
        font-family: 'Courier New', monospace;
        background: #f8f9fa;
        padding: 10px;
        border-radius: 5px;
        margin: 5px 0;
        border-left: 4px solid #FF4B4B;
        word-break: break-all;
    }
    
    .progress-bar {
        height: 10px;
        background: #e0e0e0;
        border-radius: 5px;
        overflow: hidden;
        margin: 10px 0;
    }
    
    .progress-fill {
        height: 100%;
        background: linear-gradient(90deg, #667eea, #764ba2);
        border-radius: 5px;
        transition: width 0.3s;
    }
    
    .stButton button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        width: 100%;
    }
    
    .stButton button:hover {
        background: linear-gradient(135deg, #764ba2 0%, #667eea 100%);
        color: white;
    }
    
    .category-tag {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 15px;
        font-size: 0.8rem;
        margin: 2px;
    }
    
    .database { background: #4299E1; color: white; }
    .performance { background: #48BB78; color: white; }
    .security { background: #ED8936; color: white; }
    .network { background: #9F7AEA; color: white; }
    .resource { background: #F56565; color: white; }
    .application { background: #667eea; color: white; }
    .io { background: #ED64A6; color: white; }
</style>
""", unsafe_allow_html=True)

# Error patterns with descriptions
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
        return f"HTTP_{http_match.group(1)}"
    
    # Error codes like ERR_123, ERROR_500, etc.
    code_patterns = [
        r'ERR[_-](\w+)',
        r'ERROR[_-](\w+)',
        r'code[:\s]+(\w+)',
        r'error\s+code\s*[=:]\s*(\w+)',
        r'\[(\w+)\]',
    ]
    
    for pattern in code_patterns:
        match = re.search(pattern, line, re.IGNORECASE)
        if match:
            return match.group(1).upper()
    
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
                         if pattern in selected_patterns]
    
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

def main():
    """Main Streamlit app"""
    
    # Header
    st.markdown('<h1 class="main-header">🔍 Log Error Analyzer</h1>', unsafe_allow_html=True)
    st.markdown("Upload log files to find and analyze errors, exceptions, and issues")
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ Settings")
        
        # File upload
        uploaded_file = st.file_uploader(
            "Choose a log file",
            type=['log', 'txt', 'out', 'err'],
            help="Upload .log, .txt, or similar text files"
        )
        
        st.markdown("---")
        
        # Pattern selection
        st.subheader("🔍 Error Patterns")
        
        # Quick select buttons
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Select All", use_container_width=True):
                st.session_state.selected_patterns = list(ERROR_PATTERNS.keys())
        with col2:
            if st.button("Clear All", use_container_width=True):
                st.session_state.selected_patterns = []
        
        # Pattern checkboxes
        if 'selected_patterns' not in st.session_state:
            st.session_state.selected_patterns = list(ERROR_PATTERNS.keys())
        
        for pattern, description in ERROR_PATTERNS.items():
            checked = pattern in st.session_state.selected_patterns
            if st.checkbox(f"{description}", value=checked, key=pattern):
                if pattern not in st.session_state.selected_patterns:
                    st.session_state.selected_patterns.append(pattern)
            else:
                if pattern in st.session_state.selected_patterns:
                    st.session_state.selected_patterns.remove(pattern)
        
        st.markdown("---")
        
        # Custom patterns
        st.subheader("➕ Custom Patterns")
        custom_patterns = st.text_area(
            "Add custom patterns (one per line)",
            height=100,
            help="Enter regular expressions for custom error detection"
        )
        
        st.markdown("---")
        
        # Analysis button
        analyze_button = st.button(
            "🚀 Analyze Log File",
            type="primary",
            use_container_width=True,
            disabled=uploaded_file is None
        )
    
    # Main content area
    if uploaded_file is not None:
        # File info
        file_size = uploaded_file.size
        st.info(f"📁 **File:** {uploaded_file.name} | 📏 **Size:** {file_size:,} bytes")
        
        if analyze_button:
            # Initialize session state for results
            if 'analysis_results' not in st.session_state:
                st.session_state.analysis_results = None
            
            # Create progress indicators
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            try:
                # Convert uploaded file to text stream
                text_stream = io.TextIOWrapper(uploaded_file, encoding='utf-8', errors='ignore')
                
                # Process the file
                with st.spinner("Processing log file..."):
                    errors, stats = process_log_stream(
                        text_stream, 
                        st.session_state.selected_patterns,
                        progress_bar,
                        status_text
                    )
                
                # Store results in session state
                st.session_state.analysis_results = {
                    'errors': errors,
                    'stats': stats,
                    'filename': uploaded_file.name
                }
                
                # Reset file pointer for possible re-use
                uploaded_file.seek(0)
                
            except Exception as e:
                st.error(f"Error processing file: {str(e)}")
        
        # Display results if available
        if 'analysis_results' in st.session_state and st.session_state.analysis_results:
            results = st.session_state.analysis_results
            errors = results['errors']
            stats = results['stats']
            
            # Summary metrics
            st.markdown("## 📊 Analysis Summary")
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.markdown("""
                <div class="stat-card">
                    <div class="stat-value">{:,}</div>
                    <div class="stat-label">Total Lines</div>
                </div>
                """.format(stats['total_lines']), unsafe_allow_html=True)
            
            with col2:
                st.markdown("""
                <div class="stat-card">
                    <div class="stat-value">{:,}</div>
                    <div class="stat-label">Errors Found</div>
                </div>
                """.format(stats['error_count']), unsafe_allow_html=True)
            
            with col3:
                error_rate = (stats['error_count'] / stats['total_lines'] * 100) if stats['total_lines'] > 0 else 0
                st.markdown("""
                <div class="stat-card">
                    <div class="stat-value">{:.2f}%</div>
                    <div class="stat-label">Error Rate</div>
                </div>
                """.format(error_rate), unsafe_allow_html=True)
            
            with col4:
                st.markdown("""
                <div class="stat-card">
                    <div class="stat-value">{}</div>
                    <div class="stat-label">Categories</div>
                </div>
                """.format(len(stats['categories'])), unsafe_allow_html=True)
            
            # Charts
            col1, col2 = st.columns(2)
            
            with col1:
                # Category distribution
                if stats['categories']:
                    cat_df = pd.DataFrame(
                        list(stats['categories'].items()), 
                        columns=['Category', 'Count']
                    ).sort_values('Count', ascending=False)
                    
                    fig = px.pie(
                        cat_df, 
                        values='Count', 
                        names='Category',
                        title='Error Categories Distribution',
                        hole=0.4
                    )
                    fig.update_traces(textposition='inside', textinfo='percent+label')
                    st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                # Top error patterns
                if stats['pattern_matches']:
                    pattern_df = pd.DataFrame(
                        list(stats['pattern_matches'].items()), 
                        columns=['Pattern', 'Count']
                    ).sort_values('Count', ascending=False).head(10)
                    
                    fig = px.bar(
                        pattern_df,
                        x='Count',
                        y='Pattern',
                        orientation='h',
                        title='Top 10 Error Patterns',
                        color='Count'
                    )
                    fig.update_layout(yaxis={'categoryorder': 'total ascending'})
                    st.plotly_chart(fig, use_container_width=True)
            
            # Error codes table
            if stats['error_codes']:
                st.markdown("### 🔢 Error Codes Found")
                error_codes_df = pd.DataFrame(
                    list(stats['error_codes'].items()), 
                    columns=['Error Code', 'Count']
                ).sort_values('Count', ascending=False)
                
                st.dataframe(
                    error_codes_df,
                    use_container_width=True,
                    hide_index=True
                )
            
            # Errors list with filtering
            st.markdown("### 📋 Detected Errors")
            
            if errors:
                # Create DataFrame for errors
                errors_df = pd.DataFrame(errors)
                
                # Filter options
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    search_term = st.text_input("🔍 Search in errors", "")
                
                with col2:
                    categories = ['All'] + sorted(errors_df['category'].unique().tolist())
                    selected_category = st.selectbox("Filter by category", categories)
                
                # Apply filters
                filtered_df = errors_df.copy()
                
                if search_term:
                    filtered_df = filtered_df[
                        filtered_df['content'].str.contains(search_term, case=False, na=False)
                    ]
                
                if selected_category != 'All':
                    filtered_df = filtered_df[filtered_df['category'] == selected_category]
                
                # Display count
                st.info(f"Showing {len(filtered_df):,} of {len(errors):,} errors")
                
                # Display errors with pagination
                page_size = 50
                total_pages = max(1, (len(filtered_df) + page_size - 1) // page_size)
                
                page_number = st.number_input(
                    "Page", 
                    min_value=1, 
                    max_value=total_pages, 
                    value=1,
                    step=1
                )
                
                start_idx = (page_number - 1) * page_size
                end_idx = min(start_idx + page_size, len(filtered_df))
                
                # Display errors
                for idx, error in filtered_df.iloc[start_idx:end_idx].iterrows():
                    with st.expander(f"Line {error['line_number']}: {error['content'][:100]}..."):
                        col1, col2 = st.columns([3, 1])
                        
                        with col1:
                            st.markdown(f"**Full Error:**")
                            st.code(error['content'], language='text')
                        
                        with col2:
                            st.markdown("**Metadata:**")
                            st.markdown(f"""
                            <div class="category-tag {error['category']}">
                                {error['category'].upper()}
                            </div>
                            """, unsafe_allow_html=True)
                            
                            if error['error_code']:
                                st.markdown(f"**Code:** `{error['error_code']}`")
                            
                            st.markdown(f"**Pattern:** {error['matched_pattern']}")
                
                # Export options
                st.markdown("---")
                st.markdown("### 📤 Export Results")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    # Download CSV
                    if not filtered_df.empty:
                        st.markdown(
                            create_download_link(filtered_df, f"errors_{results['filename']}.csv"),
                            unsafe_allow_html=True
                        )
                
                with col2:
                    # Copy to clipboard
                    if st.button("📋 Copy Error Counts to Clipboard"):
                        summary_text = f"""
                        Log Analysis Summary:
                        - File: {results['filename']}
                        - Total Lines: {stats['total_lines']:,}
                        - Errors Found: {stats['error_count']:,}
                        - Error Rate: {error_rate:.2f}%
                        - Categories: {', '.join(f'{k} ({v})' for k, v in stats['categories'].items())}
                        """
                        st.code(summary_text, language='text')
                        
            else:
                st.success("✅ No errors found with the selected patterns!")
                
    else:
        # Welcome/instructions
        st.markdown("""
        ## 👋 Welcome to Log Error Analyzer
        
        ### How to use:
        1. **Upload a log file** using the sidebar
        2. **Select error patterns** to detect (or use all)
        3. **Click "Analyze Log File"** to start processing
        4. **View results** including:
           - Error counts and rates
           - Category breakdown
           - Detailed error listings
           - Export options
        
        ### Supported Files:
        - Web server logs (Apache, Nginx)
        - Application logs (Python, Java, Node.js)
        - System logs
        - Any text-based log files
        
        ### Features:
        - Handles files with millions of lines
        - Real-time progress tracking
        - Smart error categorization
        - Search and filtering
        - Export to CSV
        - Visual analytics
        """)
        
        # Example section
        with st.expander("📋 Example Log Formats Detected"):
            st.code("""
            # Common formats recognized:
            
            # JSON logs
            {"timestamp": "2024-01-15T14:30:22Z", "level": "ERROR", "message": "Database connection failed"}
            
            # Web server logs
            192.168.1.1 - - [15/Jan/2024:14:30:22 +0000] "GET /api" 500 1024
            
            # Application logs
            2024-01-15 14:30:22 ERROR PaymentService - Transaction failed: timeout
            
            # System logs
            Jan 15 14:30:22 server kernel: [12345.678] Out of memory: Kill process 1234
            """, language='text')

if __name__ == "__main__":
    main()