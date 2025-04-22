"""
Modulo Planner per il Sistema AI di Ricerca Documentale.
Responsabile della generazione del piano di ricerca strutturato a partire da una query.

Utilizza DeepSeek via Ollama (con fallback a Gemini) per generare:
1. Interpretazione semantica della query
2. Struttura gerarchica di task di ricerca
3. Fonti suggerite per ogni task
"""

import json
import logging
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
import uuid

from model_adapter import ModelAdapter, ModelType
from pydantic import BaseModel, Field

# Configurazione del logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Schema per la struttura del piano di ricerca
class ResearchQuestion(BaseModel):
    """Domanda di ricerca con fonti suggerite."""
    question: str
    sources: List[str] = Field(default_factory=list)
    importance: int = Field(5, ge=1, le=10)
    notes: Optional[str] = None

class ResearchSection(BaseModel):
    """Sezione del piano di ricerca."""
    title: str
    description: str
    questions: List[ResearchQuestion] = Field(default_factory=list)
    order: int = 0

class ResearchPlan(BaseModel):
    """Piano di ricerca completo."""
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    objective: str
    description: str
    sections: List[ResearchSection] = Field(default_factory=list)
    depth: int = Field(2, ge=1, le=3)
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())

# Prompt template per il Planner
PLANNER_PROMPT_TEMPLATE = """
# Istruzioni per la Pianificazione di Ricerca Documentale

Sei un esperto pianificatore di ricerca documentale. Il tuo compito è creare un piano strutturato per condurre una ricerca approfondita sul seguente argomento:

ARGOMENTO: {query}

## Compiti:
1. Analizza attentamente la query e identifica l'obiettivo principale della ricerca
2. Crea 2-5 sezioni logiche per strutturare la ricerca
3. Per ogni sezione, genera 1-3 domande di ricerca specifiche
4. Per ogni domanda, suggerisci 1-5 potenziali fonti online (URL) da consultare
5. Assegna un livello di importanza a ogni domanda (da 1 a 10)
6. Determina la profondità di ricerca necessaria (da 1 a 3, dove 1=base, 2=standard, 3=approfondita)

## Output:
Fornisci un piano di ricerca completo in formato JSON con la seguente struttura:
- task_id: un identificatore univoco
- objective: l'obiettivo principale della ricerca
- description: una descrizione generale della ricerca
- sections: un array di sezioni, ciascuna con:
  - title: il titolo della sezione
  - description: una breve descrizione della sezione
  - questions: un array di domande, ciascuna con:
    - question: la domanda di ricerca
    - sources: un array di URL suggeriti
    - importance: l'importanza della domanda (1-10)
- depth: la profondità di ricerca consigliata (1-3)

IMPORTANTE: Le fonti suggerite devono essere URL realistici e pertinenti, come articoli accademici, siti ufficiali, o forum specializzati.
"""

class ResearchPlanner:
    """
    Pianificatore per la ricerca documentale.
    Utilizza un LLM per generare un piano di ricerca strutturato.
    """
    
    def __init__(self):
        """Inizializza il pianificatore con l'adattatore del modello."""
        self.model = ModelAdapter()
        logger.info("ResearchPlanner inizializzato")
        
        # Verifica la disponibilità dei modelli
        status = self.model.check_ollama_installation()
        if status["ollama_available"]:
            logger.info("Utilizzo DeepSeek via Ollama per la pianificazione")
            if not status["deepseek_available"]:
                logger.warning("Modello DeepSeek non disponibile in Ollama")
        else:
            logger.info("Utilizzo Gemini per la pianificazione (fallback)")
    
    def create_research_plan(self, query: str) -> ResearchPlan:
        """
        Crea un piano di ricerca strutturato a partire da una query.
        
        Args:
            query: La query di ricerca dell'utente
            
        Returns:
            Piano di ricerca strutturato
        """
        logger.info(f"Creazione piano di ricerca per query: {query}")
        
        # Preparazione del prompt
        prompt = PLANNER_PROMPT_TEMPLATE.format(query=query)
        
        # Chiamata al modello
        result = self.model.generate(
            prompt=prompt,
            task_type=ModelType.PLANNER,
            temperature=0.3,  # Temperatura bassa per output più deterministici
            max_tokens=4000,   # Risposta lunga per un piano dettagliato
            format_output=True,
            output_format=ResearchPlan.schema()
        )
        
        if "error" in result and result.get("error"):
            logger.error(f"Errore nella generazione del piano: {result['error']}")
            # Crea un piano minimo in caso di errore
            return ResearchPlan(
                objective=query,
                description=f"Piano di ricerca per: {query}",
                sections=[
                    ResearchSection(
                        title="Ricerca generale",
                        description=f"Informazioni generali su: {query}",
                        questions=[
                            ResearchQuestion(
                                question=f"Quali sono le informazioni principali su {query}?",
                                sources=["https://www.google.com"]
                            )
                        ]
                    )
                ],
                depth=1
            )
        
        # Estrai e analizza la risposta JSON
        try:
            # In alcuni casi, il modello potrebbe rispondere con testo prima o dopo il JSON
            response_text = result.get("response", "")
            
            # Trova l'inizio e la fine del JSON
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                plan_dict = json.loads(json_str)
                
                # Valida e crea il piano
                plan = ResearchPlan(**plan_dict)
                logger.info(f"Piano creato con successo: {plan.task_id}")
                return plan
            else:
                raise ValueError("Nessun JSON valido trovato nella risposta")
                
        except Exception as e:
            logger.error(f"Errore nella conversione del piano: {str(e)}")
            logger.error(f"Risposta raw: {result.get('response', 'Nessuna risposta')}")
            
            # Crea un piano di fallback
            return ResearchPlan(
                objective=query,
                description=f"Piano di ricerca per: {query}",
                sections=[
                    ResearchSection(
                        title="Ricerca generale",
                        description=f"Informazioni generali su: {query}",
                        questions=[
                            ResearchQuestion(
                                question=f"Quali sono le informazioni principali su {query}?",
                                sources=["https://www.google.com"]
                            )
                        ]
                    )
                ],
                depth=1
            )
    
    def convert_plan_to_tasks(self, plan: ResearchPlan) -> List[Dict[str, Any]]:
        """
        Converte un piano di ricerca in una lista di task eseguibili.
        
        Args:
            plan: Il piano di ricerca
            
        Returns:
            Lista di task per l'orchestratore
        """
        tasks = []
        
        for section_idx, section in enumerate(plan.sections):
            for question_idx, question in enumerate(section.questions):
                task = {
                    "task_id": f"{plan.task_id}_s{section_idx}_q{question_idx}",
                    "plan_id": plan.task_id,
                    "section": section.title,
                    "objective": plan.objective,
                    "question": question.question,
                    "sources": question.sources,
                    "importance": question.importance,
                    "depth": plan.depth,
                    "status": "pending"
                }
                tasks.append(task)
        
        return tasks

# Test del modulo
if __name__ == "__main__":
    planner = ResearchPlanner()
    
    # Test di creazione piano
    test_query = "Come è cambiata la regolamentazione UE sulla cybersecurity dal 2018 al 2023?"
    plan = planner.create_research_plan(test_query)
    
    print(f"Piano creato con ID: {plan.task_id}")
    print(f"Obiettivo: {plan.objective}")
    print(f"Profondità: {plan.depth}")
    print(f"Sezioni: {len(plan.sections)}")
    
    for section in plan.sections:
        print(f"\nSEZIONE: {section.title}")
        print(f"Descrizione: {section.description}")
        print(f"Domande: {len(section.questions)}")
        
        for question in section.questions:
            print(f"  - {question.question} (Importanza: {question.importance})")
            for source in question.sources:
                print(f"    * {source}")
    
    # Test di conversione in task
    tasks = planner.convert_plan_to_tasks(plan)
    print(f"\nTask generati: {len(tasks)}")
    for task in tasks:
        print(f"- {task['task_id']}: {task['question']}")