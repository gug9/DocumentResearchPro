import asyncio
import streamlit as st
from research_system import ResearchSystem
from contextlib import asynccontextmanager
import os
from datetime import datetime

# Configure page
st.set_page_config(
    page_title="Sistema di Ricerca Avanzata",
    page_icon="🔍",
    layout="wide"
)

# Versione adattata di ResearchOutput
class Section:
    def __init__(self, title, content, sources=None):
        self.title = title
        self.content = content
        self.sources = sources or []

# Initialize session state
if "research_system" not in st.session_state:
    st.session_state.research_system = None
if "research_results" not in st.session_state:
    st.session_state.research_results = None
if "api_keys" not in st.session_state:
    st.session_state.api_keys = {}

# API Keys Management
with st.sidebar.expander("🔑 Gestione API Keys"):
    gemini_key = st.text_input("Gemini API Key", type="password", key="gemini_key")
    if gemini_key:
        st.session_state.api_keys["gemini"] = gemini_key
        # Set environment variable for the current session
        os.environ["GEMINI_API_KEY"] = gemini_key

# Sidebar configuration
st.sidebar.title("Configurazione")

# Model selection
model_type = st.sidebar.selectbox(
    "Seleziona il modello",
    ["deepseek-r1:7b", "gemini-pro"]
)

# API Key input for Gemini
if model_type == "gemini-pro":
    api_key = st.sidebar.text_input("Inserisci Gemini API Key", type="password")
    if not api_key and "gemini" not in st.session_state.api_keys:
        st.sidebar.warning("Per usare Gemini Pro è necessaria una API key")
    elif api_key:
        os.environ["GEMINI_API_KEY"] = api_key

# Research depth
research_depth = st.sidebar.slider(
    "Profondità della ricerca",
    min_value=1,
    max_value=3,
    value=2,
    help="1: Base, 2: Dettagliata, 3: Approfondita"
)

@asynccontextmanager
async def get_research_system():
    system = ResearchSystem()
    try:
        yield system
    finally:
        if system:
            await system.close()

async def run_research(query: str):
    async with get_research_system() as system:
        st.session_state.research_system = system
        with st.spinner("Esecuzione ricerca in corso..."):
            try:
                # Create research plan
                plan = await system.create_research_plan(query)
                
                # Execute research
                findings = await system.execute_web_research(plan)
                
                # Validate findings
                validated = await system.validate_findings(findings)
                
                # Generate output
                results = await system.generate_output(plan, validated)
                
                # Crea sezioni per Streamlit
                sections = create_sections_from_results(results)
                
                # Aggiungi le sezioni ai risultati
                results.sections = sections
                
                st.session_state.research_results = results
                return results
            except Exception as e:
                st.error(f"Errore durante l'esecuzione della ricerca: {str(e)}")
                return None

def create_sections_from_results(results):
    """Crea sezioni per la visualizzazione in Streamlit dai risultati della ricerca."""
    sections = []
    
    # Sezione di riepilogo
    sections.append(Section(
        title="Riepilogo della ricerca",
        content=results.summary,
        sources=[]
    ))
    
    # Sezioni per ogni findings
    for i, finding in enumerate(results.findings, 1):
        content = ""
        if finding.key_points:
            content += "## Punti chiave\n\n"
            for point in finding.key_points:
                content += f"- {point.text}\n"
            content += "\n"
        
        if finding.summary:
            content += f"## Sintesi\n\n{finding.summary}\n\n"
        
        sources = [finding.metadata] if finding.metadata else []
        
        sections.append(Section(
            title=finding.metadata.title if finding.metadata and finding.metadata.title else f"Fonte {i}",
            content=content,
            sources=sources
        ))
    
    return sections

# Main UI
st.title("🔍 Sistema di Ricerca Documentale Avanzato")
st.markdown("### Ricerca e analisi documentale con DeepSeek e Gemini")

# Input section
query = st.text_area("Inserisci la tua query di ricerca:", height=100)

if st.button("Avvia Ricerca", disabled=not query):
    if model_type == "gemini-pro" and not api_key and "gemini" not in st.session_state.api_keys:
        st.error("È necessaria una API key per utilizzare Gemini Pro")
    else:
        with st.spinner("Inizializzazione del sistema di ricerca..."):
            asyncio.run(run_research(query))

# Display results
if st.session_state.research_results:
    results = st.session_state.research_results
    
    st.success("Ricerca completata!")
    
    # Display document sections
    if hasattr(results, 'sections'):
        for i, section in enumerate(results.sections, 1):
            st.subheader(f"Sezione {i}: {section.title}")
            st.markdown(section.content)
            
            # Display sources
            if section.sources:
                with st.expander("Fonti utilizzate"):
                    for source in section.sources:
                        if hasattr(source, 'url'):
                            st.write(f"- [{source.title or source.url}]({source.url})")
    else:
        # Fallback to original structure
        st.header("Riepilogo della ricerca")
        st.markdown(results.summary)
        
        st.header("Dettagli dei risultati")
        for i, finding in enumerate(results.findings, 1):
            with st.expander(f"Fonte {i}: {finding.metadata.title or finding.source}"):
                st.subheader("Punti chiave")
                for point in finding.key_points:
                    st.markdown(f"- {point.text} (Confidenza: {point.confidence:.2f})")
                
                st.subheader("Sintesi")
                st.markdown(finding.summary or "Nessuna sintesi disponibile")
                
                st.subheader("Fonte")
                st.markdown(f"[{finding.source}]({finding.source})")