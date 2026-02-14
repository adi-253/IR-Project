"""
Data Validation and Quality Checks
Validates collected papers and provides quality metrics.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List
from collections import Counter
import hashlib

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/validation.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Paths
PDF_BASE = Path("raw_data/arxiv/pdfs")
TEXT_DIR = Path("raw_data/arxiv/text")
METADATA_DIR = Path("raw_data/arxiv/metadata")


class DataValidator:
    """Validates data quality and generates statistics."""
    
    def __init__(self):
        self.stats = {
            'total_papers': 0,
            'valid_pdfs': 0,
            'valid_texts': 0,
            'valid_metadata': 0,
            'duplicates': 0,
            'corrupted_files': 0,
            'by_category': {},
            'by_year': {},
            'avg_paper_length': 0,
            'avg_file_size_mb': 0,
            'total_size_gb': 0
        }
        
        self.issues = []
        self.paper_hashes = {}
    
    def validate_single_paper(self, arxiv_id: str) -> Dict[str, bool]:
        """
        Validate a single paper's files.
        
        Args:
            arxiv_id: ArXiv paper ID
            
        Returns:
            Dictionary of validation results
        """
        results = {
            'has_pdf': False,
            'has_text': False,
            'has_metadata': False,
            'text_length_ok': False,
            'metadata_complete': False
        }
        
        # Check PDF exists
        pdf_path = None
        for category_dir in PDF_BASE.iterdir():
            if category_dir.is_dir():
                potential_pdf = category_dir / f"{arxiv_id}.pdf"
                if potential_pdf.exists():
                    results['has_pdf'] = True
                    pdf_path = potential_pdf
                    break
        
        # Check text file
        text_path = TEXT_DIR / f"{arxiv_id}.txt"
        if text_path.exists():
            results['has_text'] = True
            
            # Validate text length
            with open(text_path, 'r', encoding='utf-8') as f:
                text = f.read()
                if len(text) >= 1000:  # Minimum 1000 characters
                    results['text_length_ok'] = True
                else:
                    self.issues.append(f"{arxiv_id}: Text too short ({len(text)} chars)")
        
        # Check metadata
        metadata_path = METADATA_DIR / f"{arxiv_id}.json"
        if metadata_path.exists():
            results['has_metadata'] = True
            
            try:
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)
                
                # Check required fields
                required_fields = ['arxiv_id', 'title', 'authors', 'abstract', 'primary_category']
                if all(field in metadata for field in required_fields):
                    results['metadata_complete'] = True
                else:
                    missing = [f for f in required_fields if f not in metadata]
                    self.issues.append(f"{arxiv_id}: Missing metadata fields: {missing}")
            
            except json.JSONDecodeError:
                self.issues.append(f"{arxiv_id}: Corrupted metadata JSON")
        
        return results
    
    def check_duplicates(self):
        """Check for duplicate papers based on content hash."""
        logger.info("Checking for duplicates...")
        
        text_files = list(TEXT_DIR.glob("*.txt"))
        
        for text_file in text_files:
            try:
                with open(text_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Create hash of content
                content_hash = hashlib.md5(content.encode()).hexdigest()
                
                if content_hash in self.paper_hashes:
                    self.stats['duplicates'] += 1
                    self.issues.append(
                        f"Duplicate found: {text_file.stem} matches {self.paper_hashes[content_hash]}"
                    )
                else:
                    self.paper_hashes[content_hash] = text_file.stem
            
            except Exception as e:
                logger.error(f"Error checking {text_file}: {e}")
    
    def gather_statistics(self):
        """Gather comprehensive statistics about the collection."""
        logger.info("Gathering statistics...")
        
        metadata_files = list(METADATA_DIR.glob("*.json"))
        self.stats['total_papers'] = len(metadata_files)
        
        total_text_length = 0
        total_file_size = 0
        
        for metadata_file in metadata_files:
            try:
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
                
                # Category distribution
                category = metadata.get('primary_category', 'unknown')
                self.stats['by_category'][category] = self.stats['by_category'].get(category, 0) + 1
                
                # Year distribution
                published = metadata.get('published', '')
                year = published.split('-')[0] if published else 'unknown'
                self.stats['by_year'][year] = self.stats['by_year'].get(year, 0) + 1
                
                # Text length
                if 'text_length' in metadata:
                    total_text_length += metadata['text_length']
                
                # File size
                if 'file_size_bytes' in metadata:
                    total_file_size += metadata['file_size_bytes']
            
            except Exception as e:
                logger.error(f"Error reading {metadata_file}: {e}")
        
        # Calculate averages
        if self.stats['total_papers'] > 0:
            self.stats['avg_paper_length'] = total_text_length // self.stats['total_papers']
            self.stats['avg_file_size_mb'] = (total_file_size / self.stats['total_papers']) / (1024 * 1024)
            self.stats['total_size_gb'] = total_file_size / (1024 * 1024 * 1024)
    
    def validate_all(self):
        """Run comprehensive validation."""
        logger.info("="*80)
        logger.info("Starting Data Validation")
        logger.info("="*80)
        
        # Get all metadata files
        metadata_files = list(METADATA_DIR.glob("*.json"))
        logger.info(f"Found {len(metadata_files)} papers to validate")
        
        # Validate each paper
        for metadata_file in metadata_files:
            arxiv_id = metadata_file.stem
            results = self.validate_single_paper(arxiv_id)
            
            if results['has_pdf']:
                self.stats['valid_pdfs'] += 1
            if results['has_text'] and results['text_length_ok']:
                self.stats['valid_texts'] += 1
            if results['has_metadata'] and results['metadata_complete']:
                self.stats['valid_metadata'] += 1
            
            # Check if paper is complete
            if not all(results.values()):
                issues = [k for k, v in results.items() if not v]
                self.issues.append(f"{arxiv_id}: Incomplete - {', '.join(issues)}")
        
        # Check for duplicates
        self.check_duplicates()
        
        # Gather statistics
        self.gather_statistics()
        
        # Print results
        self._print_report()
    
    def _print_report(self):
        """Print validation report."""
        logger.info("\n" + "="*80)
        logger.info("VALIDATION REPORT")
        logger.info("="*80)
        
        logger.info(f"\n📊 Overall Statistics:")
        logger.info(f"  Total papers: {self.stats['total_papers']}")
        logger.info(f"  Valid PDFs: {self.stats['valid_pdfs']}")
        logger.info(f"  Valid texts: {self.stats['valid_texts']}")
        logger.info(f"  Valid metadata: {self.stats['valid_metadata']}")
        
        logger.info(f"\n✅ Quality Metrics:")
        if self.stats['total_papers'] > 0:
            completeness = (self.stats['valid_texts'] / self.stats['total_papers']) * 100
            logger.info(f"  Completeness rate: {completeness:.1f}%")
        logger.info(f"  Duplicates found: {self.stats['duplicates']}")
        logger.info(f"  Average paper length: {self.stats['avg_paper_length']:,} characters")
        logger.info(f"  Average file size: {self.stats['avg_file_size_mb']:.2f} MB")
        logger.info(f"  Total collection size: {self.stats['total_size_gb']:.2f} GB")
        
        logger.info(f"\n📁 Category Distribution:")
        for category, count in sorted(self.stats['by_category'].items()):
            logger.info(f"  {category}: {count} papers")
        
        logger.info(f"\n📅 Year Distribution:")
        for year, count in sorted(self.stats['by_year'].items(), reverse=True):
            logger.info(f"  {year}: {count} papers")
        
        if self.issues:
            logger.info(f"\n⚠️  Issues Found ({len(self.issues)}):")
            for issue in self.issues[:10]:  # Show first 10 issues
                logger.info(f"  - {issue}")
            if len(self.issues) > 10:
                logger.info(f"  ... and {len(self.issues) - 10} more")
        else:
            logger.info("\n✅ No issues found!")
        
        logger.info("="*80)
        
        # Save report
        report_path = Path("logs/validation_report.json")
        with open(report_path, 'w') as f:
            json.dump({
                'stats': self.stats,
                'issues': self.issues
            }, f, indent=2)
        
        logger.info(f"\nDetailed report saved to: {report_path}")


def main():
    """Main entry point."""
    validator = DataValidator()
    validator.validate_all()
    
    logger.info("\n✅ Validation complete! Check logs/validation_report.json for details.")


if __name__ == "__main__":
    main()
