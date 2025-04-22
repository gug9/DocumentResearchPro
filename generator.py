"""
Modulo Generator per il Sistema AI di Ricerca Documentale.
Responsabile della generazione del documento finale, unendo tutti i contenuti
di ricerca in un unico documento strutturato e coerente.

Utilizza DeepSeek via Ollama (con fallback a Gemini) per:
1. Organizzare i contenuti in sezioni logiche
2. Creare introduzione ed executive summary
3. Uniformare stile e tono
4. Generare indice e riferimenti
"""

import json
import logging
import os
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
import uuid
import re

from model_adapter import ModelAdapter, ModelType
from pydantic import BaseModel, Field

# Configurazione del logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Schema per i documenti
class DocumentSection(BaseModel):
    """Sezione di un documento."""
    title: str
    content: str
    level: int = 1
    section_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    subsections: List["DocumentSection"] = Field(default_factory=list)

# Risolviamo la reference circolare
DocumentSection.update_forward_refs()

class DocumentMetadata(BaseModel):
    """Metadati di un documento."""
    title: str
    description: str
    authors: List[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    tags: List[str] = Field(default_factory=list)
    language: str = "it"
    word_count: Optional[int] = None
    source_count: Optional[int] = None

class DocumentFormat(str):
    """Formati di output supportati."""
    MARKDOWN = "markdown"
    HTML = "html"
    PDF = "pdf"
    DOCX = "docx"

class Document(BaseModel):
    """Documento completo."""
    document_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    metadata: DocumentMetadata
    sections: List[DocumentSection] = Field(default_factory=list)
    sources: List[str] = Field(default_factory=list)
    plan_id: Optional[str] = None
    task_ids: List[str] = Field(default_factory=list)
    generated_at: str = Field(default_factory=lambda: datetime.now().isoformat())

# Prompt template per il Generator
GENERATOR_PROMPT_TEMPLATE = """
# Istruzioni per la Generazione di Documento di Ricerca

Sei un esperto nella creazione di documenti di ricerca coerenti e ben strutturati. 
Il tuo compito è unificare diverse sezioni di contenuto in un unico documento organico.

## Obiettivo della ricerca:
{objective}

## Contenuti da unificare:
{contents}

## Struttura richiesta:
- Titolo principale
- Abstract/Sommario (max 300 parole)
- Indice
- Introduzione
- Corpo del documento (organizziato in sezioni e sottosezioni)
- Conclusioni
- Riferimenti/Bibliografia

## Compiti:
1. Organizza i contenuti in sezioni logiche e coerenti
2. Crea un flusso naturale tra le diverse sezioni
3. Elimina ridondanze e ripetizioni
4. Uniforma stile, tono e terminologia
5. Aggiungi transizioni tra le sezioni quando necessario
6. Assicura coerenza nelle citazioni e riferimenti
7. Crea una struttura gerarchica chiara con intestazioni di vari livelli
8. Genera un indice basato sulla struttura

## Output:
Fornisci un documento completo in formato Markdown con:
- Un titolo chiaro e descrittivo
- Un abstract/sommario conciso
- Indice automatico con link alle sezioni
- Struttura con intestazioni H1, H2, H3, etc.
- Riferimenti e citazioni unificate alla fine

IMPORTANTE: Il documento deve essere completo, professionale e pronto per la pubblicazione. 
Non aggiungere contenuti non presenti nei materiali forniti, ma organizza e struttura le informazioni esistenti nel modo più efficace.
"""

class DocumentGenerator:
    """
    Generatore di documenti finali.
    Unisce i risultati delle ricerche in un documento strutturato.
    """
    
    def __init__(self):
        """Inizializza il generatore con l'adattatore del modello."""
        self.model = ModelAdapter()
        logger.info("DocumentGenerator inizializzato")
        
        # Verifica la disponibilità dei modelli
        status = self.model.check_ollama_installation()
        if status["ollama_available"]:
            logger.info("Utilizzo DeepSeek via Ollama per la generazione")
            if not status["deepseek_available"]:
                logger.warning("Modello DeepSeek non disponibile in Ollama")
        else:
            logger.info("Utilizzo Gemini per la generazione (fallback)")
    
    def generate_document(
        self, 
        objective: str, 
        research_results: List[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Document:
        """
        Genera un documento completo a partire dai risultati di ricerca.
        
        Args:
            objective: Obiettivo generale della ricerca
            research_results: Lista di risultati di ricerca
            metadata: Metadati opzionali per il documento
            
        Returns:
            Documento completo
        """
        logger.info(f"Generazione documento per obiettivo: {objective}")
        
        # Prepara i contenuti
        contents = ""
        task_ids = []
        sources = []
        
        for i, result in enumerate(research_results):
            task_ids.append(result.get("task_id", f"task_{i}"))
            contents += f"\n\n## Sezione: {result.get('section', f'Sezione {i+1}')}\n"
            contents += f"Domanda: {result.get('question', 'N/A')}\n\n"
            contents += result.get("content", "Nessun contenuto disponibile")
            
            # Aggiungiamo le fonti
            result_sources = result.get("sources_used", [])
            if result_sources:
                sources.extend(result_sources)
        
        # Rimuovi duplicati dalle fonti
        sources = list(set(sources))
        
        # Usa i metadati forniti o crea default
        if metadata is None:
            metadata = {
                "title": f"Ricerca: {objective}",
                "description": f"Documento di ricerca su: {objective}",
                "authors": ["Sistema AI di Ricerca Documentale"],
                "tags": [],
                "language": "it"
            }
        
        # Crea il prompt
        prompt = GENERATOR_PROMPT_TEMPLATE.format(
            objective=objective,
            contents=contents
        )
        
        # Genera il documento
        result = self.model.generate(
            prompt=prompt,
            task_type=ModelType.GENERATOR,
            temperature=0.3,
            max_tokens=8000
        )
        
        if "error" in result and result.get("error"):
            logger.error(f"Errore nella generazione del documento: {result['error']}")
            # Crea un documento minimo in caso di errore
            document_content = f"# Errore nella generazione del documento\n\nNon è stato possibile generare il documento completo a causa del seguente errore:\n\n{result['error']}\n\n## Contenuti grezzi\n\n{contents}"
        else:
            document_content = result.get("response", "Nessun contenuto generato")
        
        # Conta le parole
        word_count = len(document_content.split())
        
        # Crea il documento
        document = self._parse_markdown_to_document(
            document_content,
            DocumentMetadata(
                title=metadata["title"],
                description=metadata["description"],
                authors=metadata["authors"],
                tags=metadata.get("tags", []),
                language=metadata.get("language", "it"),
                word_count=word_count,
                source_count=len(sources)
            ),
            task_ids,
            sources
        )
        
        # Salva il documento su file
        self._save_document(document)
        
        logger.info(f"Documento generato con ID: {document.document_id}")
        return document
    
    def _parse_markdown_to_document(
        self, 
        markdown_content: str,
        metadata: DocumentMetadata,
        task_ids: List[str],
        sources: List[str]
    ) -> Document:
        """
        Converte un contenuto markdown in un documento strutturato.
        
        Args:
            markdown_content: Contenuto markdown
            metadata: Metadati del documento
            task_ids: Lista di ID dei task di ricerca
            sources: Lista di fonti utilizzate
            
        Returns:
            Documento strutturato
        """
        # Identifica le sezioni nel markdown
        sections = []
        current_level = 0
        current_section = None
        parent_sections = {0: None}
        
        # Dividi il contenuto in linee
        lines = markdown_content.split("\n")
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # Cerca intestazioni markdown (# Header)
            header_match = re.match(r'^(#{1,6})\s+(.+)$', line)
            if header_match:
                level = len(header_match.group(1))
                title = header_match.group(2).strip()
                
                # Trova il contenuto di questa sezione
                content_lines = []
                j = i + 1
                while j < len(lines):
                    next_line = lines[j].strip()
                    next_header_match = re.match(r'^(#{1,6})\s+(.+)$', next_line)
                    if next_header_match and len(next_header_match.group(1)) <= level:
                        break
                    content_lines.append(lines[j])
                    j += 1
                
                content = "\n".join(content_lines)
                
                # Crea una nuova sezione
                new_section = DocumentSection(
                    title=title,
                    content=content,
                    level=level
                )
                
                # Gestisci la gerarchia
                if level == 1:
                    sections.append(new_section)
                    parent_sections[1] = new_section
                else:
                    parent_level = level - 1
                    while parent_level > 0 and parent_level not in parent_sections:
                        parent_level -= 1
                    
                    if parent_level in parent_sections and parent_sections[parent_level]:
                        parent_sections[parent_level].subsections.append(new_section)
                    else:
                        # Fallback: aggiungi alla root
                        sections.append(new_section)
                    
                    parent_sections[level] = new_section
                
                i = j
                continue
            
            i += 1
        
        # Se non ci sono sezioni, crea una sezione default
        if not sections:
            sections = [DocumentSection(
                title=metadata.title,
                content=markdown_content
            )]
        
        # Crea il documento
        return Document(
            metadata=metadata,
            sections=sections,
            task_ids=task_ids,
            sources=sources
        )
    
    def _save_document(self, document: Document) -> None:
        """
        Salva il documento su file.
        
        Args:
            document: Documento da salvare
        """
        document_id = document.document_id
        
        # Crea la directory per i documenti se non esiste
        os.makedirs("documents", exist_ok=True)
        
        # Salva il JSON del documento
        with open(f"documents/{document_id}.json", "w") as f:
            # Usa json.dumps invece di document.json() direttamente con indent
            import json
            f.write(json.dumps(document.model_dump(), indent=2))
        
        # Salva il markdown
        markdown = self._document_to_markdown(document)
        with open(f"documents/{document_id}.md", "w") as f:
            f.write(markdown)
        
        logger.info(f"Documento salvato in documents/{document_id}.md e documents/{document_id}.json")
    
    def _document_to_markdown(self, document: Document) -> str:
        """
        Converte un documento in markdown.
        
        Args:
            document: Documento da convertire
            
        Returns:
            Contenuto markdown
        """
        markdown = f"# {document.metadata.title}\n\n"
        
        # Aggiungi metadati
        markdown += f"*{document.metadata.description}*\n\n"
        if document.metadata.authors:
            markdown += f"Autori: {', '.join(document.metadata.authors)}\n\n"
        markdown += f"Data: {document.metadata.created_at.split('T')[0]}\n\n"
        
        # Aggiungi tag se presenti
        if document.metadata.tags:
            markdown += f"Tag: {', '.join(document.metadata.tags)}\n\n"
        
        # Aggiungi indice
        markdown += "## Indice\n\n"
        
        # Genera TOC con una funzione più semplice
        toc = ""
        
        def generate_toc(sections, level=0):
            result = ""
            for section in sections:
                indent = "  " * level
                link_title = section.title.lower().replace(" ", "-").replace(":", "")
                result += f"{indent}- [{section.title}](#{link_title})\n"
                
                # Gestione ricorsiva delle sottosezioni
                if section.subsections:
                    result += generate_toc(section.subsections, level + 1)
            return result
        
        toc = generate_toc(document.sections)
        markdown += toc + "\n"
        
        # Aggiungi contenuto
        def add_section(section: DocumentSection, level: int = 1):
            nonlocal markdown
            header = "#" * level
            markdown += f"{header} {section.title}\n\n"
            markdown += f"{section.content.strip()}\n\n"
            for subsection in section.subsections:
                add_section(subsection, level + 1)
        
        for section in document.sections:
            add_section(section)
        
        # Aggiungi fonti
        if document.sources:
            markdown += "## Fonti\n\n"
            for i, source in enumerate(document.sources):
                markdown += f"{i+1}. [{source}]({source})\n"
        
        return markdown
    
    def export_document(self, document: Document, format: str = DocumentFormat.MARKDOWN) -> str:
        """
        Esporta un documento in vari formati.
        
        Args:
            document: Documento da esportare
            format: Formato di esportazione
            
        Returns:
            Percorso del file esportato
        """
        document_id = document.document_id
        
        if format == DocumentFormat.MARKDOWN:
            # Già salvato in _save_document
            return f"documents/{document_id}.md"
        
        elif format == DocumentFormat.HTML:
            markdown = self._document_to_markdown(document)
            
            # Usa il titolo del documento
            title = document.metadata.title
            
            # Template HTML semplice
            html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            line-height: 1.6;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
        }}
        h1, h2, h3, h4, h5, h6 {{
            margin-top: 2rem;
        }}
        a {{
            color: #0366d6;
        }}
        blockquote {{
            border-left: 4px solid #ddd;
            padding-left: 1rem;
            margin-left: 0;
            color: #777;
        }}
        code {{
            background-color: #f6f8fa;
            border-radius: 3px;
            padding: 0.2em 0.4em;
        }}
        pre {{
            background-color: #f6f8fa;
            border-radius: 3px;
            padding: 16px;
            overflow: auto;
        }}
        img {{
            max-width: 100%;
        }}
        table {{
            border-collapse: collapse;
            width: 100%;
        }}
        th, td {{
            border: 1px solid #ddd;
            padding: 8px;
        }}
    </style>
</head>
<body>
"""
            
            # Conversione markdown -> HTML (molto semplificata)
            # Per una conversione reale, usare una libreria come markdown2
            lines = markdown.split("\n")
            for line in lines:
                # Intestazioni
                header_match = re.match(r'^(#{1,6})\s+(.+)$', line)
                if header_match:
                    level = len(header_match.group(1))
                    title = header_match.group(2).strip()
                    html += f"<h{level}>{title}</h{level}>\n"
                    continue
                
                # Link
                line = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', line)
                
                # Paragrafi
                if line.strip():
                    html += f"<p>{line}</p>\n"
                else:
                    html += "<br>\n"
            
            html += "</body></html>"
            
            # Salva HTML
            os.makedirs("documents", exist_ok=True)
            html_path = f"documents/{document_id}.html"
            with open(html_path, "w") as f:
                f.write(html)
            
            return html_path
        
        elif format in [DocumentFormat.PDF, DocumentFormat.DOCX]:
            logger.warning(f"Esportazione in formato {format} non implementata. Tornando al markdown.")
            return f"documents/{document_id}.md"
        
        else:
            logger.error(f"Formato non supportato: {format}")
            return f"documents/{document_id}.md"

# Test del modulo
if __name__ == "__main__":
    generator = DocumentGenerator()
    
    # Test di generazione documento
    objective = "Evoluzione della regolamentazione UE sulla cybersecurity dal 2018 al 2023"
    
    # Esempio di risultati di ricerca
    research_results = [
        {
            "task_id": "task1",
            "section": "Contesto normativo",
            "question": "Quali erano le principali normative UE sulla cybersecurity prima del 2018?",
            "content": """
# Normative UE sulla cybersecurity prima del 2018

La cybersecurity è diventata una priorità per l'UE già nei primi anni 2000, ma è solo nel 2016 che viene adottata la **Direttiva NIS** (Network and Information Security), primo tentativo di creare un quadro normativo comune per tutti gli Stati membri.

La **Direttiva NIS** (2016/1148) prevedeva:
- Obbligo per gli Stati membri di dotarsi di una strategia nazionale
- Creazione di una rete di CSIRT (Computer Security Incident Response Team)
- Requisiti di sicurezza per operatori di servizi essenziali

Prima di questa direttiva, il quadro era frammentario e basato principalmente su normative nazionali.

Fonte: [Sito ufficiale UE](https://europa.eu/cybersecurity)
""",
            "sources_used": ["https://europa.eu/cybersecurity"]
        },
        {
            "task_id": "task2",
            "section": "Evoluzione normativa",
            "question": "Quali sono stati i principali sviluppi normativi tra il 2018 e il 2023?",
            "content": """
# Evoluzione normativa UE sulla cybersecurity (2018-2023)

Tra il 2018 e il 2023, l'UE ha significativamente rafforzato il proprio quadro normativo sulla cybersecurity:

## Cybersecurity Act (2019)
Regolamento (UE) 2019/881, ha rafforzato l'ENISA (Agenzia dell'Unione europea per la cibersicurezza) e introdotto un quadro di certificazione della cybersecurity a livello europeo.

## Direttiva NIS2 (2022)
La Direttiva NIS2 (2022/2555) ha sostituito la precedente Direttiva NIS ampliando significativamente:
- Il numero di settori e soggetti coperti
- Gli obblighi di sicurezza
- I requisiti di notifica di incidenti
- Le sanzioni

## Cyber Resilience Act (proposta 2022)
Proposta di regolamento che introduce requisiti di cybersecurity per prodotti con elementi digitali, dall'ideazione al supporto post-vendita.

Fonte: [ENISA](https://www.enisa.europa.eu/)
""",
            "sources_used": ["https://www.enisa.europa.eu/"]
        },
        {
            "task_id": "task3",
            "section": "Impatti pratici",
            "question": "Come hanno influito questi cambiamenti normativi sulle organizzazioni e sul mercato?",
            "content": """
# Impatti pratici delle normative UE sulla cybersecurity

L'evoluzione del quadro normativo UE ha avuto diversi impatti significativi:

## Aumento degli investimenti
Le organizzazioni hanno dovuto aumentare gli investimenti in cybersecurity per conformarsi ai nuovi requisiti.
Secondo uno studio della Commissione Europea, gli investimenti in cybersecurity sono cresciuti del 41% tra il 2018 e il 2022.

## Standardizzazione delle pratiche
Il framework di certificazione ha portato a una maggiore standardizzazione delle pratiche di sicurezza in tutta l'UE.

## Incremento della domanda di professionisti
La necessità di conformarsi alle nuove normative ha creato una forte domanda di professionisti della cybersecurity, con un gap di competenze significativo.

## Mercato unico digitale
Le normative armonizzate hanno contribuito allo sviluppo del mercato unico digitale, riducendo le barriere normative tra Stati membri.

Fonte: [Commissione Europea](https://ec.europa.eu/commission/presscorner/detail/en/ip_22_2985)
""",
            "sources_used": ["https://ec.europa.eu/commission/presscorner/detail/en/ip_22_2985"]
        }
    ]
    
    document = generator.generate_document(
        objective=objective,
        research_results=research_results,
        metadata={
            "title": "L'evoluzione della regolamentazione UE sulla cybersecurity",
            "description": "Analisi dei cambiamenti normativi dal 2018 al 2023",
            "authors": ["Sistema AI di Ricerca Documentale"],
            "tags": ["cybersecurity", "UE", "normative", "NIS2", "Cybersecurity Act"]
        }
    )
    
    print(f"Documento generato con ID: {document.document_id}")
    print(f"Titolo: {document.metadata.title}")
    print(f"Numero di sezioni: {len(document.sections)}")
    print(f"Numero di parole: {document.metadata.word_count}")
    
    # Esportazione in HTML
    html_path = generator.export_document(document, DocumentFormat.HTML)
    print(f"Documento esportato in HTML: {html_path}")