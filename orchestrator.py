"""
Modulo Orchestrator per il Sistema AI di Ricerca Documentale.
Responsabile della gestione e coordinamento di tutti i componenti del sistema,
pianificando e eseguendo i task di ricerca in modo efficiente.

Usa Prefect per:
1. Definire flussi di lavoro (workflow)
2. Parallelizzare task indipendenti
3. Gestire ritentativo e fallback
4. Monitorare lo stato di avanzamento
"""

import json
import logging
import asyncio
import os
from typing import Dict, Any, List, Optional, Union, Callable
from datetime import datetime
import uuid
import time
import traceback

from planner import ResearchPlanner, ResearchPlan
from executor import ResearchExecutor, ResearchTask, ResearchResult
from validator import ContentValidator
from generator import DocumentGenerator, Document

# Decoratori semplificati senza Prefect
def task(func):
    """Decoratore semplice per sostituire Prefect task."""
    async def wrapper(*args, **kwargs):
        return await func(*args, **kwargs)
    return wrapper

def flow(name=None):
    """Decoratore semplice per sostituire Prefect flow."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                logger.error(f"Error in flow {name or func.__name__}: {str(e)}")
                traceback.print_exc()
                raise
        return wrapper
    return decorator

# Configurazione del logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ResearchOrchestrator:
    """
    Orchestratore del sistema di ricerca documentale.
    Coordina tutti i componenti e gestisce il flusso di lavoro.
    """
    
    def __init__(self):
        """Inizializza l'orchestratore con i componenti del sistema."""
        self.planner = ResearchPlanner()
        self.executor = ResearchExecutor()
        self.validator = ContentValidator()
        self.generator = DocumentGenerator()
        
        # Stato delle ricerche
        self.active_research = {}  # {research_id: stato}
        self.results_cache = {}    # {task_id: risultato}
        
        logger.info("ResearchOrchestrator inizializzato")
    
    @task
    async def create_research_plan(self, query: str) -> ResearchPlan:
        """
        Crea un piano di ricerca strutturato.
        
        Args:
            query: Query di ricerca dell'utente
            
        Returns:
            Piano di ricerca strutturato
        """
        logger.info(f"Creazione piano di ricerca per: {query}")
        return self.planner.create_research_plan(query)
    
    @task
    async def generate_tasks(self, plan: ResearchPlan) -> List[ResearchTask]:
        """
        Genera task di ricerca dal piano.
        
        Args:
            plan: Piano di ricerca
            
        Returns:
            Lista di task di ricerca
        """
        logger.info(f"Generazione task per il piano: {plan.task_id}")
        
        tasks = []
        tasks_dict = self.planner.convert_plan_to_tasks(plan)
        
        for task_dict in tasks_dict:
            task = ResearchTask(**task_dict)
            tasks.append(task)
        
        logger.info(f"Generati {len(tasks)} task di ricerca")
        return tasks
    
    @task
    async def execute_research_task(self, task: ResearchTask) -> ResearchResult:
        """
        Esegue un task di ricerca.
        
        Args:
            task: Task di ricerca da eseguire
            
        Returns:
            Risultato della ricerca
        """
        logger.info(f"Esecuzione task: {task.task_id} - {task.question}")
        
        result = await self.executor.execute_task(task)
        
        # Memorizza il risultato nella cache
        self.results_cache[task.task_id] = result
        
        return result
    
    @task
    async def validate_research_result(self, task: ResearchTask, result: ResearchResult) -> ResearchResult:
        """
        Valida un risultato di ricerca.
        
        Args:
            task: Task di ricerca
            result: Risultato da validare
            
        Returns:
            Risultato validato o rigenerato
        """
        logger.info(f"Validazione risultato per task: {task.task_id}")
        
        # Esegue la validazione
        validation = self.validator.validate_content(
            task_id=task.task_id,
            content_id=f"result_{task.task_id}",
            question=task.question,
            content=result.content,
            sources=result.sources_used
        )
        
        # Determina se è necessario rigenerare
        retry, reason = self.validator.should_retry_task(validation)
        
        if retry:
            logger.warning(f"Rigenerazione necessaria per task {task.task_id}: {reason}")
            
            # Useremo il contenuto corretto se fornito
            if validation.new_content:
                # Aggiorna il risultato con il contenuto corretto
                result.content = validation.new_content
                result.confidence = validation.overall_score
                logger.info(f"Utilizzato contenuto corretto dal validatore per task {task.task_id}")
            else:
                # Rigenera completamente
                logger.info(f"Rigenerazione completa per task {task.task_id}")
                
                # Crea un prompt migliorato con i problemi rilevati
                improved_task = ResearchTask(
                    task_id=f"{task.task_id}_retry",
                    plan_id=task.plan_id,
                    section=task.section,
                    objective=task.objective,
                    question=task.question,
                    sources=task.sources,
                    depth=task.depth,
                    importance=task.importance,
                    status="pending"
                )
                
                # Riesegui il task
                new_result = await self.executor.execute_task(improved_task)
                
                # Aggiorna la cache
                self.results_cache[task.task_id] = new_result
                
                return new_result
        
        # Aggiorna il confidence score
        result.confidence = validation.overall_score
        
        return result
    
    @task
    async def generate_document(
        self, 
        plan: ResearchPlan, 
        results: List[ResearchResult]
    ) -> Document:
        """
        Genera il documento finale.
        
        Args:
            plan: Piano di ricerca
            results: Risultati della ricerca
            
        Returns:
            Documento finale
        """
        logger.info(f"Generazione documento per piano: {plan.task_id}")
        
        # Converte i risultati in formato per il generatore
        research_results = []
        for result in results:
            research_results.append({
                "task_id": result.task_id,
                "section": result.section,
                "question": result.question,
                "content": result.content,
                "sources_used": result.sources_used,
                "confidence": result.confidence
            })
        
        # Genera il documento
        document = self.generator.generate_document(
            objective=plan.objective,
            research_results=research_results,
            metadata={
                "title": f"Ricerca: {plan.objective}",
                "description": plan.description,
                "authors": ["Sistema AI di Ricerca Documentale"],
                "tags": []
            }
        )
        
        return document
    
    @flow(name="research_workflow")
    async def execute_research_workflow(self, query: str) -> Document:
        """
        Esegue un flusso di ricerca completo.
        
        Args:
            query: Query di ricerca
            
        Returns:
            Documento finale
        """
        # ID univoco per questa ricerca
        research_id = str(uuid.uuid4())
        
        # Registra la ricerca attiva
        self.active_research[research_id] = {
            "query": query,
            "status": "planning",
            "start_time": datetime.now().isoformat(),
            "steps_completed": []
        }
        
        try:
            # Step 1: Crea il piano di ricerca
            plan = await self.create_research_plan(query)
            
            # Aggiorna lo stato
            self.active_research[research_id]["status"] = "task_generation"
            self.active_research[research_id]["steps_completed"].append("planning")
            self.active_research[research_id]["plan_id"] = plan.task_id
            
            # Step 2: Genera i task di ricerca
            tasks = await self.generate_tasks(plan)
            
            # Aggiorna lo stato
            self.active_research[research_id]["status"] = "research"
            self.active_research[research_id]["steps_completed"].append("task_generation")
            self.active_research[research_id]["task_count"] = len(tasks)
            
            # Step 3: Esegui i task in sequenza con pausa per evitare rate limits
            results = []
            for i, task in enumerate(tasks):
                self.active_research[research_id]["current_task"] = task.task_id
                
                # Aggiungi pausa per evitare rate limits, escluso il primo task
                if i > 0:
                    logger.info(f"Pausa di 5 secondi prima del task {i+1}/{len(tasks)} per evitare rate limits...")
                    await asyncio.sleep(5)
                
                try:
                    result = await self.execute_research_task(task)
                    results.append(result)
                except Exception as e:
                    logger.error(f"Errore nell'esecuzione del task {task.task_id}: {str(e)}")
                    # Crea un risultato minimo in caso di errore
                    results.append({
                        "task_id": task.task_id,
                        "section": task.section,
                        "question": task.question,
                        "content": f"Non è stato possibile completare questa ricerca a causa di un errore: {str(e)}",
                        "sources_used": [],
                        "confidence": 0.0
                    })
            
            # Aggiorna lo stato
            self.active_research[research_id]["status"] = "validation"
            self.active_research[research_id]["steps_completed"].append("research")
            
            # Step 4: Valida i risultati con pausa per evitare rate limits
            validated_results = []
            for i, (task, result) in enumerate(zip(tasks, results)):
                self.active_research[research_id]["current_validation"] = f"{i+1}/{len(results)}"
                
                # Aggiungi pausa per evitare rate limits, escluso il primo risultato
                if i > 0:
                    logger.info(f"Pausa di 5 secondi prima della validazione {i+1}/{len(results)} per evitare rate limits...")
                    await asyncio.sleep(5)
                
                try:
                    validated_result = await self.validate_research_result(task, result)
                    validated_results.append(validated_result)
                except Exception as e:
                    logger.error(f"Errore nella validazione del risultato per il task {task.task_id}: {str(e)}")
                    # In caso di errore, mantieni il risultato originale
                    validated_results.append(result)
            
            # Aggiorna lo stato
            self.active_research[research_id]["status"] = "document_generation"
            self.active_research[research_id]["steps_completed"].append("validation")
            
            # Step 5: Genera il documento finale
            document = await self.generate_document(plan, validated_results)
            
            # Aggiorna lo stato
            self.active_research[research_id]["status"] = "completed"
            self.active_research[research_id]["steps_completed"].append("document_generation")
            self.active_research[research_id]["document_id"] = document.document_id
            self.active_research[research_id]["end_time"] = datetime.now().isoformat()
            
            return document
            
        except Exception as e:
            logger.error(f"Errore nel workflow di ricerca: {str(e)}")
            self.active_research[research_id]["status"] = "failed"
            self.active_research[research_id]["error"] = str(e)
            self.active_research[research_id]["end_time"] = datetime.now().isoformat()
            raise
    
    def get_research_status(self, research_id: str) -> Dict[str, Any]:
        """
        Ottiene lo stato di una ricerca.
        
        Args:
            research_id: ID della ricerca
            
        Returns:
            Stato della ricerca
        """
        if research_id in self.active_research:
            return self.active_research[research_id]
        return {"error": "Ricerca non trovata"}
    
    def list_active_research(self) -> List[Dict[str, Any]]:
        """
        Elenca tutte le ricerche attive o completate.
        
        Returns:
            Lista di ricerche
        """
        return [
            {
                "research_id": research_id,
                "query": info["query"],
                "status": info["status"],
                "start_time": info["start_time"],
                "end_time": info.get("end_time")
            } 
            for research_id, info in self.active_research.items()
        ]
    
    def get_task_result(self, task_id: str) -> Optional[ResearchResult]:
        """
        Ottiene il risultato di un task specifico.
        
        Args:
            task_id: ID del task
            
        Returns:
            Risultato del task, se disponibile
        """
        return self.results_cache.get(task_id)
    
    async def close(self):
        """Chiude l'orchestratore e libera le risorse."""
        await self.executor.close_browser()
        logger.info("ResearchOrchestrator chiuso")

# Test del modulo
async def test_orchestrator():
    orchestrator = ResearchOrchestrator()
    
    try:
        query = "Come è cambiata la regolamentazione UE sulla cybersecurity dal 2018 al 2023?"
        print(f"Avvio ricerca su: {query}")
        
        document = await orchestrator.execute_research_workflow(query)
        
        print(f"Ricerca completata. Documento generato con ID: {document.document_id}")
        print(f"Titolo: {document.metadata.title}")
        print(f"Numero di sezioni: {len(document.sections)}")
        
    finally:
        await orchestrator.close()

if __name__ == "__main__":
    asyncio.run(test_orchestrator())