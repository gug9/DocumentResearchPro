"""
Model Adapter per integrare DeepSeek via Ollama con fallback a Gemini.
Questo modulo gestisce:
1. Connessione a Ollama per DeepSeek
2. Fallback automatico a Gemini se Ollama non è disponibile
3. Interfaccia unificata per entrambi i modelli
"""

import os
import logging
import json
import subprocess
import requests
from typing import Dict, Any, List, Optional, Union, Callable
import time

# Per Gemini
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

# Per logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configurazione Ollama
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_DEEPSEEK_MODEL = os.environ.get("OLLAMA_DEEPSEEK_MODEL", "deepseek-coder:instruct")
OLLAMA_TIMEOUT = int(os.environ.get("OLLAMA_TIMEOUT", "5"))  # 5 secondi di timeout predefinito

# Configurazione LLM
LLM_PROVIDERS = {
    "google": {
        "models": {
            "gemini-pro": "gemini-pro",
            "gemma-it": "gemma-3-27b-it"
        },
        "api_key": os.environ.get("GEMINI_API_KEY")
    },
    "openai": {
        "models": {
            "gpt-4": "gpt-4",
            "gpt-3.5-turbo": "gpt-3.5-turbo"
        },
        "api_key": os.environ.get("OPENAI_API_KEY")
    }
}

DEFAULT_PROVIDER = "google"
DEFAULT_MODEL = "gemma-it"

class ModelType:
    """Enum per i tipi di modelli supportati."""
    PLANNER = "planner"  # Per la pianificazione dei task
    VALIDATOR = "validator"  # Per la validazione/anti-allucinazione
    GENERATOR = "generator"  # Per la generazione finale del documento
    EXECUTOR = "executor"  # Per l'esecuzione delle ricerche (sempre Gemini)

class OllamaClient:
    """Client per interagire con Ollama API."""
    
    @staticmethod
    def is_available() -> bool:
        """Verifica se Ollama è disponibile e in esecuzione."""
        try:
            response = requests.get(f"{OLLAMA_BASE_URL}/api/version", timeout=OLLAMA_TIMEOUT)
            return response.status_code == 200
        except Exception as e:
            logger.info(f"Ollama non è disponibile: {str(e)}")
            return False
    
    @staticmethod
    def list_models() -> List[str]:
        """Elenca i modelli disponibili in Ollama."""
        try:
            response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=OLLAMA_TIMEOUT)
            if response.status_code == 200:
                models = response.json().get("models", [])
                return [model.get("name") for model in models]
            return []
        except Exception as e:
            logger.warning(f"Impossibile ottenere la lista dei modelli Ollama: {str(e)}")
            return []
    
    @staticmethod
    def is_model_available(model_name: str) -> bool:
        """Verifica se un modello specifico è disponibile in Ollama."""
        return model_name in OllamaClient.list_models()
    
    @staticmethod
    def generate(
        prompt: str, 
        model: str = OLLAMA_DEEPSEEK_MODEL, 
        temperature: float = 0.7, 
        max_tokens: int = 2048
    ) -> Dict[str, Any]:
        """
        Genera una risposta usando Ollama.
        
        Args:
            prompt: Il prompt da inviare al modello
            model: Il nome del modello Ollama da usare
            temperature: Temperatura per la generazione
            max_tokens: Numero massimo di token da generare
            
        Returns:
            Dizionario con la risposta
        """
        try:
            data = {
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens
                }
            }
            
            response = requests.post(
                f"{OLLAMA_BASE_URL}/api/generate", 
                json=data,
                timeout=60  # Timeout più lungo per la generazione
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Errore Ollama API: {response.status_code} - {response.text}")
                return {"error": f"Errore API: {response.status_code}", "response": None}
                
        except Exception as e:
            logger.error(f"Errore nella generazione con Ollama: {str(e)}")
            return {"error": str(e), "response": None}

class GeminiClient:
    """Client per interagire con Google Gemini API."""
    
    @staticmethod
    def is_configured() -> bool:
        """Verifica se l'API key di Gemini è configurata."""
        return bool(GEMINI_API_KEY)
    
    @staticmethod
    def initialize():
        """Inizializza il client Gemini."""
        if GeminiClient.is_configured():
            genai.configure(api_key=GEMINI_API_KEY)
        else:
            logger.warning("API key di Gemini non configurata.")
    
    # Aggiunta di un semplice rate limiter per Gemini
    _last_request_time = 0
    _min_request_interval = 3  # Minimo 3 secondi tra le richieste per evitare rate limiting
    
    @classmethod
    def generate(
        cls,
        prompt: str, 
        temperature: float = 0.7, 
        max_tokens: int = 2048
    ) -> Dict[str, Any]:
        """
        Genera una risposta usando Gemini.
        
        Args:
            prompt: Il prompt da inviare al modello
            temperature: Temperatura per la generazione
            max_tokens: Numero massimo di token da generare
            
        Returns:
            Dizionario con la risposta
        """
        try:
            GeminiClient.initialize()
            
            if not GeminiClient.is_configured():
                return {"error": "API key di Gemini non configurata", "response": None}
            
            # Rate limiting semplice
            current_time = time.time()
            time_since_last_request = current_time - cls._last_request_time
            
            if time_since_last_request < cls._min_request_interval:
                sleep_time = cls._min_request_interval - time_since_last_request
                logger.info(f"Rate limiting: attesa di {sleep_time:.2f} secondi prima della prossima richiesta a Gemini")
                time.sleep(sleep_time)
            
            model = genai.GenerativeModel(
                model_name=GEMINI_MODEL,
                generation_config={
                    "temperature": temperature,
                    "max_output_tokens": max_tokens,
                    "top_p": 0.95,
                    "top_k": 40,
                },
                safety_settings={
                    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
                    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_ONLY_HIGH,
                    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
                    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
                }
            )
            
            # Tentativo di generazione con retry in caso di rate limiting
            try:
                response = model.generate_content(prompt)
                cls._last_request_time = time.time()  # Aggiorna il timestamp
                
                return {
                    "response": response.text,
                    "model": GEMINI_MODEL,
                    "prompt": prompt
                }
            except Exception as api_error:
                # Se è un errore di rate limiting, aspetta e riprova
                if "quota" in str(api_error) or "429" in str(api_error):
                    logger.warning(f"Rate limit raggiunto, attesa di 10 secondi: {str(api_error)}")
                    time.sleep(10)  # Attendi 10 secondi
                    cls._min_request_interval += 1  # Aumenta l'intervallo minimo
                    
                    # Genera una risposta semplificata basata sul prompt
                    return {
                        "response": f"Mi dispiace, ma ho raggiunto il limite di richieste API consentite. Ecco comunque una risposta semplificata:\n\nStavo per fornire informazioni su: {prompt[:100]}...\n\nTi suggerisco di aspettare qualche minuto prima di fare una nuova richiesta.",
                        "model": f"{GEMINI_MODEL} (rate limited)",
                        "prompt": prompt
                    }
                else:
                    # Se è un altro tipo di errore, rilancia
                    raise
            
        except Exception as e:
            logger.error(f"Errore nella generazione con Gemini: {str(e)}")
            return {"error": str(e), "response": None}

class ModelAdapter:
    """
    Adapter per l'utilizzo di DeepSeek via Ollama con fallback a Gemini.
    Fornisce un'interfaccia unificata indipendentemente dal modello sottostante in uso.
    """
    
    def __init__(self):
        """Inizializza l'adapter e verifica la disponibilità di Ollama."""
        self.ollama_available = OllamaClient.is_available()
        self.gemini_available = GeminiClient.is_configured()
        
        # Logging dello stato
        if self.ollama_available:
            logger.info("Ollama è disponibile. Utilizzo DeepSeek via Ollama.")
            logger.info(f"Modelli disponibili: {OllamaClient.list_models()}")
        else:
            logger.info("Ollama non è disponibile. Verrà utilizzato Gemini come fallback.")
        
        if self.gemini_available:
            logger.info("Gemini API è configurata.")
        else:
            logger.warning("Gemini API non è configurata. Alcune funzionalità potrebbero non essere disponibili.")
    
    def get_model_for_task(self, task_type: str) -> str:
        """
        Determina quale modello utilizzare per un tipo specifico di task.
        
        Args:
            task_type: Tipo di task (planner, validator, generator, executor)
        
        Returns:
            Nome del modello da utilizzare
        """
        # Executor sempre usa Gemini
        if task_type == ModelType.EXECUTOR:
            return "gemini"
        
        # Per gli altri task, usa Ollama se disponibile, altrimenti Gemini
        if self.ollama_available:
            return "ollama"
        else:
            return "gemini"
    
    def generate(
        self, 
        prompt: str, 
        task_type: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        format_output: bool = False,
        output_format: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Genera una risposta usando il modello appropriato.
        
        Args:
            prompt: Il prompt da inviare al modello
            task_type: Tipo di task (planner, validator, generator, executor)
            temperature: Temperatura per la generazione
            max_tokens: Numero massimo di token da generare
            format_output: Se True, formatta l'output secondo output_format
            output_format: Schema per la formattazione dell'output
            
        Returns:
            Dizionario con la risposta
        """
        model = self.get_model_for_task(task_type)
        
        # Aggiungi informazioni sul formato di output al prompt se richiesto
        if format_output and output_format:
            format_instructions = f"\n\nIl tuo output deve essere in formato JSON secondo il seguente schema:\n{json.dumps(output_format, indent=2)}"
            prompt += format_instructions
        
        if model == "ollama":
            # Formatta il prompt per Ollama
            ollama_prompt = f"[INSTRUCTION]\n{prompt}\n[/INSTRUCTION]"
            
            result = OllamaClient.generate(
                prompt=ollama_prompt,
                model=OLLAMA_DEEPSEEK_MODEL,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            # Se c'è stato un errore con Ollama, prova con Gemini
            if "error" in result and result.get("error"):
                logger.warning(f"Errore con Ollama: {result['error']}. Provo con Gemini.")
                if self.gemini_available:
                    # Riformatta il prompt per Gemini
                    gemini_prompt = prompt.replace("[INSTRUCTION]", "").replace("[/INSTRUCTION]", "").strip()
                    result = GeminiClient.generate(
                        prompt=gemini_prompt,
                        temperature=temperature,
                        max_tokens=max_tokens
                    )
                    result["model"] = "gemini (fallback)"
                else:
                    result["model"] = "ollama (failed)"
                
            return result
        else:
            # Usa Gemini
            result = GeminiClient.generate(
                prompt=prompt,
                temperature=temperature,
                max_tokens=max_tokens
            )
            return result
    
    def check_ollama_installation(self) -> Dict[str, Any]:
        """
        Verifica lo stato dell'installazione di Ollama.
        
        Returns:
            Dizionario con informazioni sullo stato di Ollama
        """
        result = {
            "ollama_available": self.ollama_available,
            "deepseek_available": False,
            "models_available": [],
            "gemini_available": self.gemini_available
        }
        
        if self.ollama_available:
            models = OllamaClient.list_models()
            result["models_available"] = models
            result["deepseek_available"] = any("deepseek" in model.lower() for model in models)
        
        return result
    
    @staticmethod
    def install_ollama() -> Dict[str, Any]:
        """
        Installa Ollama se possibile.
        
        Returns:
            Dizionario con il risultato dell'installazione
        """
        # Questo non funzionerà in Replit, ma lo includiamo per completezza
        logger.info("Tentativo di installare Ollama (potrebbe non funzionare in Replit)...")
        
        try:
            # Controlla se siamo su Linux
            process = subprocess.run(
                ["curl", "-fsSL", "https://ollama.com/install.sh"],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if process.returncode != 0:
                return {
                    "success": False,
                    "message": "Impossibile scaricare lo script di installazione di Ollama."
                }
            
            # Installa Ollama
            install_process = subprocess.run(
                ["curl", "-fsSL", "https://ollama.com/install.sh", "|", "sh"],
                shell=True,
                capture_output=True,
                text=True,
                timeout=180
            )
            
            if install_process.returncode != 0:
                return {
                    "success": False,
                    "message": f"Errore durante l'installazione di Ollama: {install_process.stderr}"
                }
            
            return {
                "success": True,
                "message": "Ollama installato con successo."
            }
            
        except Exception as e:
            logger.error(f"Errore nell'installazione di Ollama: {str(e)}")
            return {
                "success": False,
                "message": f"Errore durante l'installazione: {str(e)}"
            }
    
    @staticmethod
    def install_deepseek_model() -> Dict[str, Any]:
        """
        Scarica il modello DeepSeek tramite Ollama.
        
        Returns:
            Dizionario con il risultato dell'installazione
        """
        # Questo non funzionerà in Replit, ma lo includiamo per completezza
        logger.info("Tentativo di scaricare il modello DeepSeek (potrebbe non funzionare in Replit)...")
        
        try:
            process = subprocess.run(
                ["ollama", "pull", OLLAMA_DEEPSEEK_MODEL],
                capture_output=True,
                text=True,
                timeout=600  # 10 minuti di timeout
            )
            
            if process.returncode != 0:
                return {
                    "success": False,
                    "message": f"Errore durante il download del modello: {process.stderr}"
                }
            
            return {
                "success": True,
                "message": f"Modello {OLLAMA_DEEPSEEK_MODEL} scaricato con successo."
            }
            
        except Exception as e:
            logger.error(f"Errore nel download del modello DeepSeek: {str(e)}")
            return {
                "success": False,
                "message": f"Errore durante il download: {str(e)}"
            }
    
    @staticmethod
    def start_ollama_server() -> Dict[str, Any]:
        """
        Avvia il server Ollama in background.
        
        Returns:
            Dizionario con il risultato dell'avvio
        """
        # Questo non funzionerà in Replit, ma lo includiamo per completezza
        logger.info("Tentativo di avviare il server Ollama (potrebbe non funzionare in Replit)...")
        
        try:
            # Controlla se Ollama è già in esecuzione
            if OllamaClient.is_available():
                return {
                    "success": True,
                    "message": "Il server Ollama è già in esecuzione."
                }
            
            # Avvia Ollama in background
            process = subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Aspetta un po' per permettere l'avvio
            time.sleep(5)
            
            # Verifica se il server è partito
            if OllamaClient.is_available():
                return {
                    "success": True,
                    "message": "Server Ollama avviato con successo.",
                    "pid": process.pid
                }
            else:
                return {
                    "success": False,
                    "message": "Il server Ollama è stato avviato ma non risponde."
                }
            
        except Exception as e:
            logger.error(f"Errore nell'avvio del server Ollama: {str(e)}")
            return {
                "success": False,
                "message": f"Errore durante l'avvio: {str(e)}"
            }


# Esempio di utilizzo:
if __name__ == "__main__":
    adapter = ModelAdapter()
    
    # Verifica lo stato di Ollama
    status = adapter.check_ollama_installation()
    print(f"Stato Ollama: {json.dumps(status, indent=2)}")
    
    # Esempio di generazione
    if status["gemini_available"] or status["ollama_available"]:
        result = adapter.generate(
            prompt="Spiega in breve come funziona un LLM",
            task_type=ModelType.PLANNER,
            temperature=0.7,
            max_tokens=500
        )
        
        if "error" in result and result.get("error"):
            print(f"Errore: {result['error']}")
        else:
            print(f"Generato con {result.get('model', 'unknown')}:")
            print(result.get("response", "Nessuna risposta"))
    else:
        print("Nessun modello disponibile. Configura GEMINI_API_KEY o avvia Ollama.")