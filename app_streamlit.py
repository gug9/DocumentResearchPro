import asyncio
import streamlit as st
import logging
from research_system import ResearchSystem
from contextlib import asynccontextmanager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set page configuration
st.set_page_config(
    page_title="Advanced Research System",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if "research_system" not in st.session_state:
    st.session_state.research_system = None
if "research_plan" not in st.session_state:
    st.session_state.research_plan = None
if "research_output" not in st.session_state:
    st.session_state.research_output = None
if "processing" not in st.session_state:
    st.session_state.processing = False


@asynccontextmanager
async def get_research_system():
    """Context manager to initialize and close the research system."""
    system = ResearchSystem()
    try:
        yield system
    finally:
        if system.browser:
            await system.close_browser()


async def run_research_task(query):
    """Run the research task."""
    try:
        async with get_research_system() as system:
            st.session_state.research_system = system
            
            # Create research plan
            with st.spinner("Generating research plan..."):
                plan = await system.create_research_plan(query)
                st.session_state.research_plan = plan
                
            # Execute research
            with st.spinner("Executing web research..."):
                findings = await system.execute_web_research(plan)
                
            # Validate findings
            with st.spinner("Validating findings..."):
                validated = await system.validate_findings(findings)
                
            # Generate output
            with st.spinner("Generating final research output..."):
                output = await system.generate_output(plan, validated)
                st.session_state.research_output = output
                
    except Exception as e:
        logger.error(f"Error running research task: {str(e)}")
        st.error(f"Error running research task: {str(e)}")
    finally:
        st.session_state.processing = False


def main():
    """Main Streamlit app."""
    # Header
    st.title("🔍 Advanced Research System")
    st.markdown("### Integrating DeepSeek Local & Gemini Pro for advanced document research")
    
    # Sidebar - Configuration
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        # API Key input
        gemini_api_key = st.text_input("Gemini API Key", type="password", value=st.session_state.get("gemini_api_key", ""))
        if gemini_api_key:
            st.session_state.gemini_api_key = gemini_api_key
            
        st.markdown("---")
        st.subheader("Models Configuration")
        
        # DeepSeek configuration
        st.markdown("**DeepSeek Local (via Ollama)**")
        planner_model = st.selectbox("Planning Model", ["deepseek-coder:instruct"], index=0)
        validator_model = st.selectbox("Validation Model", ["deepseek-coder:instruct"], index=0)
        
        # Gemini configuration
        st.markdown("**Gemini Pro**")
        st.checkbox("Enable Gemini", value=True, disabled=not gemini_api_key, 
                   help="Requires API key to enable")
        
        st.markdown("---")
        st.markdown("### Research Components")
        st.markdown("✅ Planning: DeepSeek")
        st.markdown("✅ Web Research: Gemini + Playwright")
        st.markdown("✅ Content Analysis: DeepSeek + Gemini")
        st.markdown("✅ Document Generation: DeepSeek")
    
    # Main content area
    # Research Input Section
    st.subheader("Research Query")
    research_query = st.text_area("Enter your research topic or question", height=100, 
                                 placeholder="e.g., How has EU cybersecurity regulation evolved from 2018 to 2023?")
    
    col1, col2 = st.columns([1, 3])
    with col1:
        depth = st.select_slider("Research Depth", options=[1, 2, 3], value=2, 
                               help="1=Basic, 2=Standard, 3=Deep")
    
    # Submit button
    if st.button("Start Research", disabled=st.session_state.processing or not research_query or not gemini_api_key):
        st.session_state.processing = True
        st.session_state.research_plan = None
        st.session_state.research_output = None
        
        # Start async task
        asyncio.run(run_research_task(research_query))
    
    # Display Results
    if st.session_state.processing:
        st.info("Research in progress... This may take a few minutes.")
        
    # Display Research Plan
    if st.session_state.research_plan:
        st.subheader("Research Plan")
        plan = st.session_state.research_plan
        
        st.markdown(f"**Objective:** {plan.objective}")
        st.markdown(f"**Depth:** {plan.depth}/3")
        
        with st.expander("Research Questions", expanded=True):
            for i, question in enumerate(plan.questions):
                st.markdown(f"**Question {i+1}:** {question.question}")
                st.markdown("**Sources:**")
                for source in question.sources:
                    st.markdown(f"- [{source}]({source})")
    
    # Display Research Output
    if st.session_state.research_output:
        output = st.session_state.research_output
        
        st.subheader("Research Results")
        st.markdown(f"**Objective:** {output.objective}")
        
        # Display findings
        with st.expander("Detailed Findings", expanded=False):
            for i, finding in enumerate(output.findings):
                st.markdown(f"### Source {i+1}: [{finding.metadata.title}]({finding.source})")
                
                # Display key points
                st.markdown("**Key Points:**")
                for point in finding.key_points:
                    st.markdown(f"- {point.text}")
                
                st.markdown("**Summary:**")
                st.markdown(finding.summary)
                st.markdown("---")
        
        # Display final summary
        st.subheader("Research Summary")
        st.markdown(output.summary)
        
        # Download options
        st.download_button(
            label="Download Full Report (JSON)",
            data=output.json(indent=2),
            file_name="research_results.json",
            mime="application/json"
        )


if __name__ == "__main__":
    main()