"""
Master Pipeline Script
Orchestrates the entire data collection and processing pipeline.
"""

import sys
import logging
from pathlib import Path
import subprocess

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/pipeline.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def run_script(script_name: str, description: str) -> bool:
    """
    Run a Python script and return success status.
    
    Args:
        script_name: Name of the script file
        description: Human-readable description
        
    Returns:
        True if successful, False otherwise
    """
    logger.info("="*80)
    logger.info(f"Step: {description}")
    logger.info("="*80)
    
    script_path = Path("collections/scripts") / script_name
    
    if not script_path.exists():
        logger.error(f"Script not found: {script_path}")
        return False
    
    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            logger.info(f"✅ {description} completed successfully")
            return True
        else:
            logger.error(f"❌ {description} failed")
            logger.error(f"Error output: {result.stderr}")
            return False
    
    except Exception as e:
        logger.error(f"❌ Error running {script_name}: {e}")
        return False


def main():
    """Main pipeline execution."""
    logger.info("\n" + "="*80)
    logger.info("AGENTIC RAG DATA COLLECTION PIPELINE")
    logger.info("Target: 100 ArXiv Research Papers")
    logger.info("="*80 + "\n")
    
    # Pipeline steps
    steps = [
        ("collect_arxiv.py", "1. Collecting ArXiv Papers"),
        ("parse_papers.py", "2. Extracting Text from PDFs"),
        ("chunk_papers.py", "3. Creating Chunks with Multiple Strategies"),
        ("validate_data.py", "4. Validating Data Quality"),
    ]
    
    # Execute pipeline
    for script, description in steps:
        success = run_script(script, description)
        
        if not success:
            logger.error(f"\n❌ Pipeline failed at: {description}")
            logger.error("Please check the logs and fix issues before continuing.")
            return 1
        
        logger.info("")  # Blank line between steps
    
    # Pipeline complete
    logger.info("\n" + "="*80)
    logger.info("✅ PIPELINE COMPLETED SUCCESSFULLY!")
    logger.info("="*80)
    logger.info("\nNext Steps:")
    logger.info("1. Review validation report: logs/validation_report.json")
    logger.info("2. Check chunking results in: processed/chunked/")
    logger.info("3. Generate embeddings (run generate_embeddings.py)")
    logger.info("4. Load into vector database")
    logger.info("5. Build RAG retrieval system")
    logger.info("\n" + "="*80)
    
    return 0


if __name__ == "__main__":
    # Create logs directory if it doesn't exist
    Path("logs").mkdir(exist_ok=True)
    
    sys.exit(main())
