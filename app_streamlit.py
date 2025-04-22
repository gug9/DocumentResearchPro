import asyncio
import streamlit as st
from research_system import ResearchSystem
from contextlib import asynccontextmanager

# Configure page
st.set_page_config(
    page_title="Sistema di Ricerca Avanzata",
    page_icon="🔍",
    layout="wide"
)

# Initialize session state
if "research_system" not in st.session_state:
    st.session_state.research_system = None
if "research_results" not in st.session_state:
    st.session_state.research_results = None

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
    if not api_key:
        st.sidebar.warning("Per usare Gemini Pro è necessaria una API key")

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
                results = await system.execute_research_workflow(query)
                st.session_state.research_results = results
                return results
            except Exception as e:
                st.error(f"Errore durante l'esecuzione della ricerca: {str(e)}")
                return None


# Main UI
st.title("🔍 Sistema di Ricerca Documentale Avanzato")
st.markdown("### Ricerca e analisi documentale con DeepSeek e Gemini")

# Input section
query = st.text_area("Inserisci la tua query di ricerca:", height=100)

if st.button("Avvia Ricerca", disabled=not query):
    if model_type == "gemini-pro" and not api_key:
        st.error("È necessaria una API key per utilizzare Gemini Pro")
    else:
        with st.spinner("Inizializzazione del sistema di ricerca..."):
            asyncio.run(run_research(query))

# Display results
if st.session_state.research_results:
    results = st.session_state.research_results

    st.success("Ricerca completata!")

    # Display document sections
    for i, section in enumerate(results.sections, 1):
        st.subheader(f"Sezione {i}: {section.title}")
        st.markdown(section.content)

        # Display sources
        with st.expander("Fonti utilizzate"):
            for source in section.sources:
                st.write(f"- [{source.title}]({source.url})")