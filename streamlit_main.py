import os
import subprocess
import logging
import sys

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """Run the Streamlit application."""
    logger.info("Starting Streamlit application...")
    
    # Get port from environment (for Gunicorn)
    port = os.environ.get("PORT", "8501")
    
    # Build the command to run Streamlit
    cmd = [
        "streamlit", "run", "app_streamlit.py",
        "--server.port", port,
        "--server.address", "0.0.0.0",
        "--server.headless", "true",
        "--browser.serverAddress", "0.0.0.0"
    ]
    
    # Execute the command
    try:
        logger.info(f"Running command: {' '.join(cmd)}")
        result = subprocess.run(cmd, check=True)
        return result.returncode
    except KeyboardInterrupt:
        logger.info("Shutting down Streamlit application...")
    except subprocess.CalledProcessError as e:
        logger.error(f"Error running Streamlit: {e}")
        return e.returncode
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())