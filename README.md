# Sistema di Ricerca Avanzata con AI

Un sistema Python modulare per ricerca avanzata che integra diversi modelli AI (Gemini, OpenAI, DeepSeek) per analisi multimodale, ricerca web e generazione di documenti.

## Funzionalità Principali

### Modelli AI Supportati
- **Google (Gemini)**: Analisi multimodale e comprensione del testo
- **OpenAI (GPT)**: Elaborazione avanzata del linguaggio naturale
- **DeepSeek Local** (opzionale, via Ollama): Elaborazione locale dei task

### Capacità Core
- **Pianificazione Task**: Generazione di piani di ricerca strutturati
- **Validazione Contenuti**: Analisi di qualità e rilevanza
- **Ricerca Web**: Navigazione e analisi di contenuti online
- **Generazione Documenti**: Sintesi e reportistica avanzata

## Architettura del Sistema

```
┌─────────────────────┐     ┌─────────────────────┐     ┌─────────────────────┐
│                     │     │                     │     │                     │
│    Google Gemini    │     │      OpenAI         │     │  DeepSeek (Ollama) │
│                     │     │                     │     │     [Opzionale]     │
└──────────┬──────────┘     └──────────┬──────────┘     └──────────┬──────────┘
           │                            │                            │
           └────────────────┬───────────┴────────────────┬──────────┘
                           │                             │
                ┌──────────▼─────────────┐     ┌────────▼───────────┐
                │                        │     │                     │
                │    Model Adapter       │     │  Browser Control    │
                │                        │     │                     │
                └──────────┬─────────────┘     └────────┬───────────┘
                          │                             │
                          └──────────────┬──────────────┘
                                        │
                           ┌────────────▼───────────┐
                           │                        │
                           │   Research System      │
                           │                        │
                           └────────────┬───────────┘
                                       │
                           ┌───────────▼────────────┐
                           │                        │
                           │ Interfaccia Streamlit  │
                           │                        │
                           └────────────────────────┘
```

## Requisiti Tecnologici

- Python 3.11+
- Dipendenze principali:
  - streamlit
  - google-generativeai
  - openai
  - ollama (opzionale)
  - playwright
  - flask
  - langchain
  - prefect
  - pydantic

## Setup e Configurazione

1. **Configurazione API Keys**:
   - Configurare le API key tramite l'interfaccia Streamlit
   - Supporto per Gemini API e OpenAI API

2. **Installazione**:
   ```bash
   pip install -r requirements.txt
   python -m playwright install
   ```

3. **Avvio**:
   ```bash
   streamlit run streamlit_main.py
   ```

## Struttura del Progetto

- `app_streamlit.py`: Interfaccia utente Streamlit
- `model_adapter.py`: Gestione dei modelli AI
- `browser_controller.py`: Controllo della navigazione web
- `research_system.py`: Core del sistema di ricerca
- `validator.py`: Sistema di validazione contenuti
- `generator.py`: Generazione documenti
- `orchestrator.py`: Orchestrazione dei workflow


## Casi d'Uso

1. **Ricerca Accademica**: Analisi di letteratura scientifica con sintesi strutturata
2. **Analisi Regolamentare**: Ricerca su normative e framework legali
3. **Ricerca di Mercato**: Analisi di trend e concorrenti in settori specifici
4. **Documentazione Tecnica**: Creazione di report tecnici basati su ricerca web