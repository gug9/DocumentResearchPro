#!/usr/bin/env python3
"""
Run script for the Advanced Research System Streamlit application.
"""
import os
import sys
import subprocess
import argparse

def main():
    """Run the Streamlit application."""
    parser = argparse.ArgumentParser(description="Run the Advanced Research System.")
    parser.add_argument("--port", type=int, default=8501, help="Port to run Streamlit on")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind to")
    args = parser.parse_args()
    
    print("Starting Advanced Research System with Streamlit...")
    print(f"Host: {args.host}, Port: {args.port}")
    
    # Check if required dependencies are available
    try:
        # Check Playwright
        subprocess.run(["playwright", "--version"], check=True, capture_output=True)
        print("✓ Playwright is installed")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("! Warning: Playwright might not be properly installed.")
        print("  Run 'python -m playwright install' to set up browsers.")
    
    # Check if Ollama is running
    try:
        import requests
        ollama_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        response = requests.get(f"{ollama_url}/api/version", timeout=2)
        if response.status_code == 200:
            print(f"✓ Ollama server is running at {ollama_url}")
        else:
            print(f"! Warning: Ollama server at {ollama_url} returned status code {response.status_code}")
    except Exception as e:
        print(f"! Warning: Could not connect to Ollama: {str(e)}")
        print("  Ensure Ollama is running with 'ollama serve' or set OLLAMA_BASE_URL")
    
    # Check for Gemini API key
    if "GEMINI_API_KEY" in os.environ:
        print("✓ GEMINI_API_KEY environment variable is set")
    else:
        print("! Warning: GEMINI_API_KEY environment variable is not set.")
        print("  You can enter it in the Streamlit interface.")
    
    # Run the Streamlit app
    cmd = [
        "streamlit", "run", "app_streamlit.py",
        "--server.port", str(args.port),
        "--server.address", args.host,
        "--server.headless", "true",
        "--browser.serverAddress", args.host
    ]
    
    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\nShutting down the Advanced Research System...")
    except Exception as e:
        print(f"Error running Streamlit: {str(e)}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())