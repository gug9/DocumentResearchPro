"""
Modulo Executor per il Sistema AI di Ricerca Documentale.
Responsabile dell'esecuzione delle ricerche web e dell'analisi delle fonti.

Utilizza Gemini Pro 1.5 Multimodale per:
1. Navigare e analizzare pagine web
2. Estrarre informazioni rilevanti
3. Generare contenuti in formato Markdown
4. Citare le fonti consultate
"""

import os
import json
import logging
import asyncio
from typing import Dict, Any, List, Optional, Union, Tuple
import time
from datetime import datetime
import uuid
import re
from urllib.parse import urlparse

from model_adapter import ModelAdapter, ModelType
from pydantic import BaseModel, Field

try:
    from playwright.async_api import async_playwright, Page, Browser
    playwright_available = True
except ImportError:
    playwright_available = False
    logging.warning("Playwright non è disponibile. Alcune funzionalità di navigazione web saranno limitate.")

# Configurazione del logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Schema per le attività di ricerca
class ResearchTask(BaseModel):
    """Attività di ricerca da eseguire."""
    task_id: str
    plan_id: str
    section: str
    objective: str
    question: str
    sources: List[str] = Field(default_factory=list)
    depth: int = Field(2, ge=1, le=3)
    importance: int = Field(5, ge=1, le=10)
    status: str = "pending"
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())

class WebPage(BaseModel):
    """Pagina web analizzata."""
    url: str
    title: Optional[str] = None
    text_content: Optional[str] = None
    html_content: Optional[str] = None
    screenshot_path: Optional[str] = None
    load_status: str = "pending"
    load_time_ms: Optional[int] = None

class PageContent(BaseModel):
    """Contenuto estratto da una pagina."""
    url: str
    title: Optional[str] = None
    main_content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    summary: Optional[str] = None
    key_points: List[str] = Field(default_factory=list)
    extracted_at: str = Field(default_factory=lambda: datetime.now().isoformat())

class ResearchResult(BaseModel):
    """Risultato di una attività di ricerca."""
    task_id: str
    plan_id: str
    section: str
    question: str
    content: str  # Markdown content
    sources_used: List[str] = Field(default_factory=list)
    sources_analysis: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(ge=0.0, le=1.0, default=0.8)
    completion_time: int  # milliseconds
    completed_at: str = Field(default_factory=lambda: datetime.now().isoformat())

# Prompt template per l'executor
EXECUTOR_PROMPT_TEMPLATE = """
# Istruzioni per la Ricerca e Sintesi

Sei un ricercatore esperto e il tuo compito è analizzare le informazioni fornite per rispondere alla seguente domanda di ricerca:

DOMANDA: {question}

OBIETTIVO GENERALE: {objective}

## Contesto
Questa domanda fa parte della sezione "{section}" di un progetto di ricerca più ampio.

## Fonti fornite:
{sources_details}

## Compiti:
1. Analizza attentamente il contenuto delle fonti
2. Identifica le informazioni più rilevanti per rispondere alla domanda
3. Sintetizza i contenuti in modo coerente e completo
4. Includi dati specifici, statistiche e citazioni quando disponibili
5. Mantieni un tono neutrale e obiettivo
6. Cita le fonti utilizzando link in formato Markdown

## Output:
Fornisci una risposta completa strutturata in formato Markdown che:
- Risponda direttamente alla domanda di ricerca
- Utilizzi intestazioni e sottointestazioni per organizzare il contenuto
- Includa elenchi puntati o numerati quando appropriato
- Includa citazioni nel formato [Testo della citazione](URL della fonte)
- Mantenga una lunghezza appropriata (500-1000 parole)
- Termini con una sezione "Fonti" che elenca tutte le fonti utilizzate

IMPORTANTE: Basa la tua risposta SOLO sulle informazioni contenute nelle fonti fornite. Se le fonti non contengono informazioni sufficienti, indicalo chiaramente e suggerisci quali ulteriori dati sarebbero necessari.
"""

class ResearchExecutor:
    """
    Esecutore di ricerche web.
    Utilizza Playwright per la navigazione web e Gemini per l'analisi dei contenuti.
    """
    
    def __init__(self):
        """Inizializza l'esecutore con l'adattatore del modello."""
        self.model = ModelAdapter()
        self.browser = None
        self.context = None
        self.playwright = None
        logger.info("ResearchExecutor inizializzato")
        
        # Verifica la disponibilità di Gemini
        status = self.model.check_ollama_installation()
        if not status["gemini_available"]:
            logger.warning("Gemini API non configurata. L'esecuzione delle ricerche sarà limitata.")
    
    async def initialize_browser(self):
        """Inizializza il browser Playwright."""
        if not playwright_available:
            logger.error("Playwright non è disponibile. Impossibile inizializzare il browser.")
            return False
        
        try:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(headless=True)
            self.context = await self.browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            )
            logger.info("Browser inizializzato con successo")
            return True
        except Exception as e:
            logger.error(f"Errore nell'inizializzazione del browser: {str(e)}")
            return False
    
    async def close_browser(self):
        """Chiude il browser Playwright."""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        logger.info("Browser chiuso")
    
    async def browse_url(self, url: str) -> WebPage:
        """
        Naviga a un URL e estrae il contenuto.
        
        Args:
            url: URL da visitare
            
        Returns:
            Oggetto WebPage con i contenuti
        """
        if not self.browser:
            success = await self.initialize_browser()
            if not success:
                logger.error("Impossibile inizializzare il browser per la navigazione")
                return WebPage(
                    url=url,
                    load_status="failed",
                    title="Browser non disponibile",
                    text_content=""
                )
        
        try:
            start_time = time.time()
            page = await self.context.new_page()
            
            # Impostiamo un timeout di 30 secondi
            await page.goto(url, timeout=30000, wait_until="domcontentloaded")
            
            # Attendiamo che la pagina sia caricata
            await page.wait_for_load_state("networkidle", timeout=10000)
            
            # Estraiamo il titolo
            title = await page.title()
            
            # Estraiamo il contenuto testuale
            text_content = await page.evaluate("document.body.innerText")
            
            # Estraiamo l'HTML
            html_content = await page.content()
            
            # Facciamo uno screenshot
            screenshot_path = f"screenshots/{uuid.uuid4()}.png"
            os.makedirs("screenshots", exist_ok=True)
            await page.screenshot(path=screenshot_path)
            
            # Calcoliamo il tempo di caricamento
            load_time = int((time.time() - start_time) * 1000)
            
            await page.close()
            
            return WebPage(
                url=url,
                title=title,
                text_content=text_content,
                html_content=html_content,
                screenshot_path=screenshot_path,
                load_status="success",
                load_time_ms=load_time
            )
            
        except Exception as e:
            logger.error(f"Errore nella navigazione a {url}: {str(e)}")
            return WebPage(
                url=url,
                load_status="failed",
                title=f"Errore: {str(e)}",
                text_content=""
            )
    
    async def extract_content(self, webpage: WebPage) -> PageContent:
        """
        Estrae il contenuto rilevante da una pagina web.
        
        Args:
            webpage: Pagina web da analizzare
            
        Returns:
            Contenuto estratto
        """
        try:
            # Prepariamo un prompt per Gemini per estrarre il contenuto
            prompt = f"""
            Sei un esperto nell'estrazione di contenuti rilevanti da pagine web.
            Analizza il seguente contenuto testuale estratto dalla pagina {webpage.url} con titolo "{webpage.title or 'Sconosciuto'}"
            e estrai il contenuto principale, ignorando menu, pubblicità, footer e altri elementi non rilevanti.
            
            # Contenuto testuale della pagina:
            {webpage.text_content[:50000] if webpage.text_content else "Nessun contenuto disponibile"}
            
            # Compiti:
            1. Estrai il contenuto principale e informativo della pagina
            2. Identifica 3-5 punti chiave
            3. Genera un breve sommario (max 100 parole)
            4. Estrai metadati come autore, data di pubblicazione, etc. se disponibili
            
            Fornisci i risultati in formato JSON con i seguenti campi:
            - main_content: il contenuto principale
            - key_points: lista di punti chiave
            - summary: breve sommario
            - metadata: dizionario con eventuali metadati trovati
            """
            
            # Chiamata a Gemini
            result = self.model.generate(
                prompt=prompt,
                task_type=ModelType.EXECUTOR,
                temperature=0.2,
                max_tokens=4000
            )
            
            if "error" in result and result.get("error"):
                logger.error(f"Errore nell'estrazione del contenuto: {result['error']}")
                return PageContent(
                    url=webpage.url,
                    title=webpage.title,
                    main_content=webpage.text_content[:5000] if webpage.text_content else "Errore nell'estrazione",
                    summary="Errore nell'estrazione del contenuto",
                    key_points=["Errore nell'estrazione del contenuto"]
                )
            
            # Estraiamo il JSON dalla risposta
            response_text = result.get("response", "")
            
            # Troviamo i delimitatori del JSON
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                content_dict = json.loads(json_str)
                
                return PageContent(
                    url=webpage.url,
                    title=webpage.title,
                    main_content=content_dict.get("main_content", ""),
                    metadata=content_dict.get("metadata", {}),
                    summary=content_dict.get("summary", ""),
                    key_points=content_dict.get("key_points", [])
                )
            else:
                # Se non troviamo JSON, usiamo la risposta come contenuto principale
                return PageContent(
                    url=webpage.url,
                    title=webpage.title,
                    main_content=response_text,
                    summary="Nessun sommario disponibile",
                    key_points=["Nessun punto chiave identificato"]
                )
                
        except Exception as e:
            logger.error(f"Errore nell'estrazione del contenuto da {webpage.url}: {str(e)}")
            return PageContent(
                url=webpage.url,
                title=webpage.title,
                main_content="Errore nell'estrazione del contenuto",
                summary=f"Errore: {str(e)}",
                key_points=["Errore nell'estrazione del contenuto"]
            )
    
    async def execute_task(self, task: ResearchTask) -> ResearchResult:
        """
        Esegue un'attività di ricerca completa.
        
        Args:
            task: Attività di ricerca da eseguire
            
        Returns:
            Risultato della ricerca
        """
        logger.info(f"Esecuzione task: {task.task_id} - {task.question}")
        start_time = time.time()
        
        # Naviga e analizza le fonti
        sources_data = {}
        for url in task.sources:
            try:
                # Skip URL non validi
                if not url.startswith(("http://", "https://")):
                    logger.warning(f"URL non valido: {url}")
                    continue
                
                # Naviga alla pagina
                webpage = await self.browse_url(url)
                
                if webpage.load_status == "success" and webpage.text_content:
                    # Estrai il contenuto
                    content = await self.extract_content(webpage)
                    sources_data[url] = {
                        "title": webpage.title,
                        "status": "success",
                        "content": content.main_content,
                        "summary": content.summary,
                        "key_points": content.key_points,
                        "metadata": content.metadata
                    }
                else:
                    sources_data[url] = {
                        "title": webpage.title,
                        "status": "failed",
                        "error": "Errore nel caricamento della pagina"
                    }
            except Exception as e:
                logger.error(f"Errore nell'analisi di {url}: {str(e)}")
                sources_data[url] = {
                    "title": None,
                    "status": "error",
                    "error": str(e)
                }
        
        # Prepara i dettagli delle fonti per il prompt
        sources_details = ""
        for url, data in sources_data.items():
            if data["status"] == "success":
                sources_details += f"\n\n## Fonte: {data['title'] or url}\n"
                sources_details += f"URL: {url}\n"
                sources_details += f"Contenuto principale:\n{data['content'][:5000]}...\n"
            else:
                sources_details += f"\n\n## Fonte: {url}\n"
                sources_details += f"Stato: {data['status']}\n"
                sources_details += f"Errore: {data.get('error', 'Sconosciuto')}\n"
        
        # Se non ci sono fonti disponibili, aggiungiamo una nota
        if not sources_details:
            sources_details = "Nessuna fonte disponibile. Utilizza la tua conoscenza generale per rispondere alla domanda."
        
        # Generiamo la risposta
        prompt = EXECUTOR_PROMPT_TEMPLATE.format(
            question=task.question,
            objective=task.objective,
            section=task.section,
            sources_details=sources_details
        )
        
        result = self.model.generate(
            prompt=prompt,
            task_type=ModelType.EXECUTOR,
            temperature=0.5,
            max_tokens=4000
        )
        
        if "error" in result and result.get("error"):
            logger.error(f"Errore nella generazione della risposta: {result['error']}")
            content = f"# Errore nella ricerca\n\nNon è stato possibile completare la ricerca per il seguente motivo:\n\n{result['error']}"
        else:
            content = result.get("response", "Nessuna risposta generata")
        
        # Estraiamo le fonti citate dal contenuto markdown
        cited_sources = self.extract_urls_from_markdown(content)
        
        # Calcoliamo il tempo di completamento
        completion_time = int((time.time() - start_time) * 1000)
        
        # Creiamo il risultato
        research_result = ResearchResult(
            task_id=task.task_id,
            plan_id=task.plan_id,
            section=task.section,
            question=task.question,
            content=content,
            sources_used=list(sources_data.keys()),
            sources_analysis=sources_data,
            confidence=0.8,  # Valore di default
            completion_time=completion_time,
            completed_at=datetime.now().isoformat()
        )
        
        logger.info(f"Task completato: {task.task_id} in {completion_time/1000:.2f} secondi")
        return research_result
    
    def extract_urls_from_markdown(self, markdown_text: str) -> List[str]:
        """
        Estrae gli URL da un testo markdown.
        
        Args:
            markdown_text: Testo markdown
            
        Returns:
            Lista di URL trovati
        """
        # Pattern per trovare URL in markdown link
        markdown_link_pattern = r'\[.*?\]\((https?://[^\s)]+)\)'
        markdown_links = re.findall(markdown_link_pattern, markdown_text)
        
        # Pattern per trovare URL semplici
        url_pattern = r'(?<!\()(https?://[^\s)]+)(?![\w\s]*[\)])'
        direct_urls = re.findall(url_pattern, markdown_text)
        
        # Unisci i risultati e rimuovi duplicati
        all_urls = list(set(markdown_links + direct_urls))
        return all_urls
    
    def is_url_valid(self, url: str) -> bool:
        """
        Verifica se un URL è valido.
        
        Args:
            url: URL da verificare
            
        Returns:
            True se l'URL è valido, False altrimenti
        """
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False

# Test del modulo
async def test_executor():
    executor = ResearchExecutor()
    
    # Test di navigazione
    url = "https://www.enisa.europa.eu/topics/cybersecurity-policy/nis-2-directive"
    webpage = await executor.browse_url(url)
    print(f"Navigazione a {url}: {webpage.load_status}")
    print(f"Titolo: {webpage.title}")
    print(f"Contenuto (primi 200 caratteri): {webpage.text_content[:200] if webpage.text_content else 'Nessun contenuto'}")
    
    # Test di estrazione contenuto
    if webpage.load_status == "success":
        content = await executor.extract_content(webpage)
        print("\nContenuto estratto:")
        print(f"Sommario: {content.summary}")
        print("\nPunti chiave:")
        for point in content.key_points:
            print(f"- {point}")
    
    # Test di esecuzione task
    task = ResearchTask(
        task_id="test_task",
        plan_id="test_plan",
        section="Regolamentazione",
        objective="Comprendere l'evoluzione della regolamentazione UE sulla cybersecurity",
        question="Quali sono i principali cambiamenti introdotti dalla Direttiva NIS2?",
        sources=["https://www.enisa.europa.eu/topics/cybersecurity-policy/nis-2-directive",
                 "https://ec.europa.eu/commission/presscorner/detail/en/ip_22_2985"],
        depth=2
    )
    
    result = await executor.execute_task(task)
    print("\nTask completato:")
    print(f"Tempo di completamento: {result.completion_time/1000:.2f} secondi")
    print(f"Contenuto (primi 500 caratteri):\n{result.content[:500]}...")
    print(f"Fonti utilizzate: {result.sources_used}")
    
    await executor.close_browser()

if __name__ == "__main__":
    asyncio.run(test_executor())