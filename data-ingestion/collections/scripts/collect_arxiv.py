"""
ArXiv Paper Collection Script
Collects 100 technical research papers from ArXiv across multiple CS/ML categories.
"""

import arxiv
import os
import json
import time
from datetime import datetime
from pathlib import Path
import logging
from typing import List, Dict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/collection.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration
CATEGORIES = {
    'cs.AI': 30,       # Artificial Intelligence
    'cs.LG': 30,       # Machine Learning
    'cs.CV': 15,       # Computer Vision
    'cs.CL': 15,       # Computational Linguistics (NLP)
    'cs.NE': 5,        # Neural and Evolutionary Computing
    'stat.ML': 5       # Statistics - Machine Learning
}

BASE_DIR = Path("raw_data/arxiv")
PDF_DIR = BASE_DIR / "pdfs"
METADATA_DIR = BASE_DIR / "metadata"

# Quality filters
START_DATE = "2023-01-01"
MIN_PAGES = 5

class ArXivCollector:
    """Collects papers from ArXiv with rate limiting and error handling."""
    
    def __init__(self):
        self.client = arxiv.Client()
        self.collected_ids = set()
        self.stats = {
            'total_collected': 0,
            'failed': 0,
            'duplicates': 0,
            'by_category': {cat: 0 for cat in CATEGORIES.keys()}
        }
        
        # Load existing collection if any
        self._load_existing_collection()
    
    def _load_existing_collection(self):
        """Load already collected paper IDs to avoid duplicates."""
        if METADATA_DIR.exists():
            for metadata_file in METADATA_DIR.glob("*.json"):
                try:
                    with open(metadata_file, 'r') as f:
                        data = json.load(f)
                        self.collected_ids.add(data['arxiv_id'])
                except Exception as e:
                    logger.error(f"Error loading {metadata_file}: {e}")
        
        logger.info(f"Loaded {len(self.collected_ids)} existing papers")
    
    def collect_papers_by_category(self, category: str, max_results: int) -> List[Dict]:
        """
        Collect papers for a specific ArXiv category.
        
        Args:
            category: ArXiv category code (e.g., 'cs.AI')
            max_results: Maximum number of papers to collect
            
        Returns:
            List of paper metadata dictionaries
        """
        logger.info(f"Collecting {max_results} papers from category: {category}")
        
        search = arxiv.Search(
            query=f"cat:{category}",
            max_results=max_results * 2,  # Request more to account for filtering
            sort_by=arxiv.SortCriterion.SubmittedDate,
            sort_order=arxiv.SortOrder.Descending
        )
        
        papers = []
        collected_count = 0
        
        for result in self.client.results(search):
            # Check if already collected
            arxiv_id = result.entry_id.split('/abs/')[-1]
            
            if arxiv_id in self.collected_ids:
                self.stats['duplicates'] += 1
                continue
            
            # Quality filters
            if result.published.strftime('%Y-%m-%d') < START_DATE:
                continue
            
            try:
                # Download PDF
                pdf_filename = f"{arxiv_id.replace('/', '_')}.pdf"
                pdf_path = PDF_DIR / category / pdf_filename
                pdf_path.parent.mkdir(parents=True, exist_ok=True)
                
                logger.info(f"Downloading: {result.title[:50]}...")
                result.download_pdf(dirpath=str(pdf_path.parent), filename=pdf_filename)
                
                # Create metadata
                metadata = {
                    'arxiv_id': arxiv_id,
                    'title': result.title,
                    'authors': [author.name for author in result.authors],
                    'abstract': result.summary,
                    'categories': result.categories,
                    'primary_category': result.primary_category,
                    'published': result.published.strftime('%Y-%m-%d'),
                    'updated': result.updated.strftime('%Y-%m-%d'),
                    'doi': result.doi,
                    'pdf_url': result.pdf_url,
                    'comment': result.comment,
                    'journal_ref': result.journal_ref,
                    'file_path': str(pdf_path),
                    'download_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                
                # Save metadata
                metadata_path = METADATA_DIR / f"{arxiv_id.replace('/', '_')}.json"
                metadata_path.parent.mkdir(parents=True, exist_ok=True)
                
                with open(metadata_path, 'w') as f:
                    json.dump(metadata, f, indent=2)
                
                papers.append(metadata)
                self.collected_ids.add(arxiv_id)
                collected_count += 1
                
                self.stats['total_collected'] += 1
                self.stats['by_category'][category] += 1
                
                logger.info(f"✓ Collected {collected_count}/{max_results} from {category}")
                
                # Rate limiting: 1 request per 3 seconds
                time.sleep(3)
                
                if collected_count >= max_results:
                    break
                    
            except Exception as e:
                logger.error(f"Failed to download {arxiv_id}: {e}")
                self.stats['failed'] += 1
                continue
        
        logger.info(f"Completed {category}: collected {collected_count} papers")
        return papers
    
    def collect_all(self):
        """Collect papers from all configured categories."""
        logger.info("="*80)
        logger.info("Starting ArXiv Paper Collection")
        logger.info(f"Target: {sum(CATEGORIES.values())} papers across {len(CATEGORIES)} categories")
        logger.info("="*80)
        
        for category, count in CATEGORIES.items():
            try:
                self.collect_papers_by_category(category, count)
            except Exception as e:
                logger.error(f"Error collecting category {category}: {e}")
                continue
        
        self._print_summary()
    
    def _print_summary(self):
        """Print collection summary statistics."""
        logger.info("\n" + "="*80)
        logger.info("COLLECTION SUMMARY")
        logger.info("="*80)
        logger.info(f"Total papers collected: {self.stats['total_collected']}")
        logger.info(f"Failed downloads: {self.stats['failed']}")
        logger.info(f"Duplicates skipped: {self.stats['duplicates']}")
        logger.info("\nBy Category:")
        for category, count in self.stats['by_category'].items():
            logger.info(f"  {category}: {count} papers")
        logger.info("="*80)
        
        # Save summary
        summary_path = Path("logs/collection_summary.json")
        with open(summary_path, 'w') as f:
            json.dump(self.stats, f, indent=2)


def main():
    """Main entry point for the collection script."""
    # Create directories
    for category in CATEGORIES.keys():
        (PDF_DIR / category).mkdir(parents=True, exist_ok=True)
    METADATA_DIR.mkdir(parents=True, exist_ok=True)
    Path("logs").mkdir(exist_ok=True)
    
    # Start collection
    collector = ArXivCollector()
    collector.collect_all()
    
    logger.info("\n✅ Collection complete! Check logs/collection_summary.json for details.")


if __name__ == "__main__":
    main()
