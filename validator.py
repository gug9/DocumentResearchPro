"""
Modulo Validator per il Sistema AI di Ricerca Documentale.
Responsabile della validazione dei contenuti generati per ridurre le allucinazioni.

Utilizza DeepSeek via Ollama (con fallback a Gemini) per:
1. Verificare l'accuratezza delle informazioni
2. Controllare la pertinenza rispetto alla query
3. Verificare la coerenza interna dei contenuti
4. Validare le fonti citate
"""

import json
import logging
from typing import Dict, Any, List, Optional, Union, Tuple
import re

from model_adapter import ModelAdapter, ModelType
from pydantic import BaseModel, Field

# Configurazione del logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Schema per la validazione
class ValidationCriteria(BaseModel):
    """Criteri per la validazione dei contenuti."""
    check_factual_accuracy: bool = True
    check_source_validity: bool = True
    check_content_relevance: bool = True
    check_internal_consistency: bool = True
    check_citation_validity: bool = True

class ValidationResult(BaseModel):
    """Risultato della validazione di un contenuto."""
    is_valid: bool
    score: float = Field(ge=0.0, le=1.0)
    issues: List[str] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)
    
class SourceValidation(BaseModel):
    """Validazione di una fonte citata."""
    source: str
    is_valid: bool
    relevance_score: float = Field(ge=0.0, le=1.0)
    comments: Optional[str] = None

class ContentValidation(BaseModel):
    """Validazione completa di un contenuto."""
    task_id: str
    content_id: str
    validation_passed: bool
    overall_score: float = Field(ge=0.0, le=1.0)
    criteria_scores: Dict[str, float] = Field(default_factory=dict)
    issues_found: List[str] = Field(default_factory=list)
    sources_validation: List[SourceValidation] = Field(default_factory=list)
    improvement_suggestions: List[str] = Field(default_factory=list)
    new_content: Optional[str] = None
    validation_date: str

# Prompt template per il Validator
VALIDATOR_PROMPT_TEMPLATE = """
# Istruzioni per la Validazione di Contenuto di Ricerca

Sei un rigoroso validatore di contenuti di ricerca con un'attenzione particolare all'accuratezza e alla verità. 
Il tuo compito è analizzare il seguente contenuto di ricerca, verificarne la qualità e identificare eventuali problemi.

## Domanda di ricerca:
{question}

## Contenuto da validare:
{content}

## Fonti citate:
{sources}

## Criteri di validazione:
1. **Accuratezza fattuale** - Le informazioni sono corrette e verificabili?
2. **Validità delle fonti** - Le fonti citate sono legittime e pertinenti?
3. **Rilevanza del contenuto** - Il contenuto risponde effettivamente alla domanda di ricerca?
4. **Coerenza interna** - Il contenuto è logicamente coerente e privo di contraddizioni?
5. **Validità delle citazioni** - Le citazioni nel testo corrispondono alle fonti elencate?

## Compiti:
1. Valuta il contenuto secondo ciascun criterio, assegnando un punteggio da 0.0 a 1.0
2. Identifica specifici problemi o potenziali allucinazioni
3. Valida ciascuna fonte citata per rilevanza e affidabilità
4. Suggerisci miglioramenti concreti
5. Determina se il contenuto supera complessivamente la validazione (true/false)
6. Se necessario, fornisci una versione corretta del contenuto

## Output:
Fornisci il risultato della validazione in formato JSON con la seguente struttura:
{{
  "task_id": "{task_id}",
  "content_id": "{content_id}",
  "validation_passed": true/false,
  "overall_score": 0.0-1.0,
  "criteria_scores": {{
    "factual_accuracy": 0.0-1.0,
    "source_validity": 0.0-1.0,
    "content_relevance": 0.0-1.0,
    "internal_consistency": 0.0-1.0,
    "citation_validity": 0.0-1.0
  }},
  "issues_found": [
    "Descrizione problema 1",
    "Descrizione problema 2",
    ...
  ],
  "sources_validation": [
    {{
      "source": "URL1",
      "is_valid": true/false,
      "relevance_score": 0.0-1.0,
      "comments": "Commento sulla fonte"
    }},
    ...
  ],
  "improvement_suggestions": [
    "Suggerimento 1",
    "Suggerimento 2",
    ...
  ],
  "new_content": "Versione corretta del contenuto, se necessario",
  "validation_date": "Data ISO della validazione"
}}

IMPORTANTE: Sii estremamente critico e rigoroso. È meglio segnalare un potenziale problema che ignorarlo.
Se identifichi allucinazioni o informazioni non verificabili, assegna punteggi bassi e suggerisci correzioni.
"""

class ContentValidator:
    """
    Validatore per i contenuti di ricerca.
    Utilizza un LLM per verificare l'accuratezza e la pertinenza dei contenuti generati.
    """
    
    def __init__(self):
        """Inizializza il validatore con l'adattatore del modello."""
        self.model = ModelAdapter()
        logger.info("ContentValidator inizializzato")
        
        # Verifica la disponibilità dei modelli
        status = self.model.check_ollama_installation()
        if status["ollama_available"]:
            logger.info("Utilizzo DeepSeek via Ollama per la validazione")
            if not status["deepseek_available"]:
                logger.warning("Modello DeepSeek non disponibile in Ollama")
        else:
            logger.info("Utilizzo Gemini per la validazione (fallback)")
    
    def validate_content(
        self, 
        task_id: str,
        content_id: str,
        question: str,
        content: str,
        sources: List[str],
        criteria: Optional[ValidationCriteria] = None
    ) -> ContentValidation:
        """
        Valida un contenuto di ricerca.
        
        Args:
            task_id: ID del task di ricerca
            content_id: ID del contenuto
            question: Domanda di ricerca
            content: Contenuto da validare
            sources: Fonti citate nel contenuto
            criteria: Criteri specifici di validazione
            
        Returns:
            Risultato della validazione
        """
        logger.info(f"Validazione contenuto: {content_id} per task: {task_id}")
        
        # Usa criteri predefiniti se non specificati
        if criteria is None:
            criteria = ValidationCriteria()
        
        # Preparazione del prompt
        sources_text = "\n".join([f"- {source}" for source in sources])
        prompt = VALIDATOR_PROMPT_TEMPLATE.format(
            question=question,
            content=content,
            sources=sources_text,
            task_id=task_id,
            content_id=content_id
        )
        
        # Chiamata al modello
        result = self.model.generate(
            prompt=prompt,
            task_type=ModelType.VALIDATOR,
            temperature=0.1,  # Temperatura molto bassa per output deterministici
            max_tokens=4000,
            format_output=True,
            output_format=ContentValidation.schema()
        )
        
        if "error" in result and result.get("error"):
            logger.error(f"Errore nella validazione del contenuto: {result['error']}")
            # Crea un risultato minimo in caso di errore
            from datetime import datetime
            return ContentValidation(
                task_id=task_id,
                content_id=content_id,
                validation_passed=False,
                overall_score=0.0,
                criteria_scores={
                    "error": 0.0
                },
                issues_found=["Errore durante la validazione"],
                validation_date=datetime.now().isoformat()
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
                validation_dict = json.loads(json_str)
                
                # Valida e crea il risultato
                validation = ContentValidation(**validation_dict)
                logger.info(f"Validazione completata: {validation.validation_passed}")
                return validation
            else:
                raise ValueError("Nessun JSON valido trovato nella risposta")
                
        except Exception as e:
            logger.error(f"Errore nella conversione del risultato: {str(e)}")
            logger.error(f"Risposta raw: {result.get('response', 'Nessuna risposta')}")
            
            # Crea un risultato di fallback
            from datetime import datetime
            return ContentValidation(
                task_id=task_id,
                content_id=content_id,
                validation_passed=False,
                overall_score=0.0,
                criteria_scores={
                    "error": 0.0
                },
                issues_found=["Errore durante l'analisi della validazione", str(e)],
                validation_date=datetime.now().isoformat()
            )
    
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
    
    def should_retry_task(self, validation: ContentValidation) -> Tuple[bool, str]:
        """
        Determina se un task dovrebbe essere rieseguito in base al risultato della validazione.
        
        Args:
            validation: Risultato della validazione
            
        Returns:
            Tupla (retry, motivo)
        """
        # Non superata la validazione
        if not validation.validation_passed:
            return True, "Validazione non superata"
        
        # Punteggio totale basso
        if validation.overall_score < 0.6:
            return True, f"Punteggio totale troppo basso: {validation.overall_score}"
        
        # Problemi critici di accuratezza fattuale
        if validation.criteria_scores.get("factual_accuracy", 1.0) < 0.5:
            return True, "Gravi problemi di accuratezza fattuale"
        
        # Troppe fonti non valide
        invalid_sources = [s for s in validation.sources_validation if not s.is_valid]
        if len(invalid_sources) > len(validation.sources_validation) / 2:
            return True, "Troppe fonti non valide"
        
        return False, "Validazione superata con successo"

# Test del modulo
if __name__ == "__main__":
    validator = ContentValidator()
    
    # Test di validazione
    test_content = """
# Evoluzione della Regolamentazione UE sulla Cybersecurity (2018-2023)

La regolamentazione UE sulla cybersecurity ha visto significativi sviluppi nel periodo 2018-2023. Il **Cybersecurity Act** del 2019 ha rafforzato l'ENISA e introdotto un framework di certificazione. La **Direttiva NIS2** del 2022 ha ampliato il campo di applicazione della precedente direttiva NIS, includendo più settori e imponendo misure di sicurezza più severe.

Nel 2023, è stata proposta la **Cyber Resilience Act** che introduce requisiti di sicurezza per i prodotti con elementi digitali.

## Fonti:
- [Sito ufficiale dell'Unione Europea](https://europa.eu/cybersecurity)
- [ENISA - Agenzia dell'Unione europea per la cibersicurezza](https://www.enisa.europa.eu/)
"""
    
    test_sources = [
        "https://europa.eu/cybersecurity",
        "https://www.enisa.europa.eu/",
        "https://digital-strategy.ec.europa.eu/en/policies/cybersecurity-act"
    ]
    
    validation = validator.validate_content(
        task_id="test_task",
        content_id="test_content",
        question="Come è cambiata la regolamentazione UE sulla cybersecurity dal 2018 al 2023?",
        content=test_content,
        sources=test_sources
    )
    
    print(f"Validazione passata: {validation.validation_passed}")
    print(f"Punteggio complessivo: {validation.overall_score}")
    
    print("\nPunteggi per criterio:")
    for criterion, score in validation.criteria_scores.items():
        print(f"- {criterion}: {score}")
    
    if validation.issues_found:
        print("\nProblemi trovati:")
        for issue in validation.issues_found:
            print(f"- {issue}")
    
    print("\nValidazione fonti:")
    for source_validation in validation.sources_validation:
        print(f"- {source_validation.source}: {'✓' if source_validation.is_valid else '✗'} (Score: {source_validation.relevance_score})")
        if source_validation.comments:
            print(f"  Commento: {source_validation.comments}")
    
    if validation.improvement_suggestions:
        print("\nSuggerimenti di miglioramento:")
        for suggestion in validation.improvement_suggestions:
            print(f"- {suggestion}")
    
    retry, reason = validator.should_retry_task(validation)
    print(f"\nRipetere il task? {'Sì' if retry else 'No'} - {reason}")