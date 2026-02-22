import streamlit as st
import io
import pandas as pd
import plotly.express as px
from langchain_core.documents import Document

from dotenv import load_dotenv

from backend.retriever import retriever
from backend.log_filter import ERROR_PATTERNS, categorize_error, extract_error_code, process_log_stream, create_download_link

# Load env variables (OPENROUTER_API_KEY etc.)
load_dotenv()


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
                
                # Create LangChain document from filtered errors
                if not filtered_df.empty and "qa_chain" not in st.session_state:
                    # Combine all error messages into one text
                    all_errors = "\n".join(filtered_df['content'].tolist())
                    
                    # Create simple LangChain document
                    doc = Document(
                        page_content=all_errors,
                        metadata={"source": uploaded_file.name}
                    )
                    
                    # Create QA chain
                    st.session_state.qa_chain = retriever(doc)
                        
            else:
                st.success("✅ No errors found with the selected patterns!")
        
        # CHAT INTERFACE - Always visible after file upload
        st.markdown("---")
        st.subheader("💬 Ask Questions About Your Logs")
        
        # Initialize chat history
        if "messages" not in st.session_state:
            st.session_state.messages = []
        
        # Display chat messages
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
        
        # Chat input - always visible
        user_question = st.chat_input("Ask something like: Why did the server crash?")
        
        if user_question:
            # Show user message
            st.session_state.messages.append({"role": "user", "content": user_question})
            with st.chat_message("user"):
                st.markdown(user_question)
            
            # Get assistant response
            with st.chat_message("assistant"):
                with st.spinner("Analyzing logs..."):
                    try:
                        # Check if analysis is complete and QA chain exists
                        if 'analysis_results' in st.session_state and "qa_chain" in st.session_state:
                            result = st.session_state.qa_chain.invoke({"query": user_question})
                            answer = result.get("result", "No answer generated.")
                            sources = result.get("source_documents", [])
                            
                            st.markdown(answer)
                            
                            # Show evidence (sources)
                            if sources:
                                with st.expander("🧾 Evidence (retrieved log chunks)"):
                                    for i, doc in enumerate(sources, start=1):
                                        st.markdown(f"**Chunk {i}:**")
                                        st.code(doc.page_content[:500])
                        
                        elif 'analysis_results' not in st.session_state:
                            answer = "⏳ Please click 'Analyze Log File' to start processing your logs first."
                            st.markdown(answer)
                        else:
                            answer = "🔄 Log analysis in progress. Please wait a moment and try again."
                            st.markdown(answer)
                        
                        # Save assistant response
                        st.session_state.messages.append({"role": "assistant", "content": answer})
                    
                    except Exception as e:
                        error_msg = f"Error: {str(e)}"
                        st.error(error_msg)
                        st.session_state.messages.append({"role": "assistant", "content": error_msg})
                
    else:
        # Welcome/instructions (shown when no file is uploaded)
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
        5. **Ask questions** about your logs in the chat
        
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
        - AI-powered chat about your errors
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