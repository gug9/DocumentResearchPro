# Sistema di Ricerca Avanzata con DeepSeek e Gemini

Un sistema Python modulare per ricerca avanzata che integra modelli DeepSeek locali (via Ollama) e Gemini Pro 1.5 per analisi multimodale, ricerca web e generazione di documenti.

## Funzionalità Principali

### DeepSeek Local (via Ollama)
- **Pianificazione Task**: Generazione di piani di ricerca strutturati
- **Validazione Contenuti**: Analisi di qualità e rilevanza dei contenuti
- **Generazione Documenti**: Sintesi e creazione di reportistica avanzata

### Gemini Pro 1.5 (API Google)
- **Analisi Multimodale**: Elaborazione di testi, immagini e dati strutturati
- **Ricerca Web Avanzata**: Navigazione e analisi di contenuti online
- **Elaborazione Documenti Complessi**: Comprensione di documenti estesi e tecnici

## Architettura del Sistema

```
┌────────────────────────┐     ┌────────────────────────┐
│                        │     │                        │
│   DeepSeek via Ollama  │     │  Gemini Pro 1.5 API    │
│                        │     │                        │
└───────────┬────────────┘     └────────────┬───────────┘
            │                               │
            ▼                               ▼
┌────────────────────────┐     ┌────────────────────────┐
│                        │     │                        │
│  Pianificazione        │     │  Analisi Multimodale   │
│  Validazione           │     │  Ricerca Web           │
│  Generazione           │     │  Elaborazione Dati     │
│                        │     │                        │
└───────────┬────────────┘     └────────────┬───────────┘
            │                               │
            └───────────────┬───────────────┘
                            │
                            ▼
                ┌────────────────────────┐
                │                        │
                │    Sistema Ricerca     │
                │                        │
                └────────────┬───────────┘
                            │
                            ▼
                ┌────────────────────────┐
                │                        │
                │ Interfaccia Streamlit  │
                │                        │
                └────────────────────────┘
```

## Requisiti Tecnologici

- **Ambiente**: Python 3.10+
- **Modelli Locali**: Ollama con DeepSeek-R1
- **Cloud API**: Gemini Pro 1.5
- **Browser Automation**: Playwright
- **Orchestrazione**: Prefect
- **Interfaccia**: Streamlit

## Come Iniziare

### Prerequisiti

1. **Installare Ollama**:
   ```
   # Visita https://ollama.ai per l'installazione
   ollama serve  # Avvia il server Ollama
   ```

2. **Installare i Modelli DeepSeek**:
   ```
   ollama pull deepseek-coder:instruct
   ```

3. **Configurare l'API Key di Gemini**:
   ```
   export GEMINI_API_KEY="tua-chiave-api"
   ```

### Avvio del Sistema

1. Installare le dipendenze:
   ```
   pip install -r requirements.txt
   python -m playwright install
   ```

2. Avviare l'applicazione:
   ```
   python streamlit_main.py
   ```

3. Accedere all'interfaccia web:
   ```
   http://localhost:8501
   ```

## Struttura del Progetto

- `research_system.py`: Sistema principale di ricerca
- `deepseek_integration.py`: Integrazione con DeepSeek via Ollama
- `gemini_integration.py`: Integrazione con Gemini Pro 1.5
- `browser_controller_new.py`: Controller browser con Playwright
- `orchestration.py`: Orchestrazione workflow con Prefect
- `app_streamlit.py`: Interfaccia utente Streamlit
- `streamlit_main.py`: Script di avvio dell'applicazione

## Casi d'Uso

1. **Ricerca Accademica**: Analisi di letteratura scientifica con sintesi strutturata
2. **Analisi Regolamentare**: Ricerca su normative e framework legali
3. **Ricerca di Mercato**: Analisi di trend e concorrenti in settori specifici
4. **Documentazione Tecnica**: Creazione di report tecnici basati su ricerca web