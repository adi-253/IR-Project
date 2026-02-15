"""
PDF Parser Script
Extracts text from ArXiv PDFs and identifies paper structure.
"""

import fitz  # PyMuPDF
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
import re
from multiprocessing import Pool, cpu_count

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/processing.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Paths
PDF_BASE = Path("raw_data/arxiv/pdfs")
TEXT_DIR = Path("raw_data/arxiv/text")
METADATA_DIR = Path("raw_data/arxiv/metadata")

# Section headers to identify (case-insensitive)
SECTION_PATTERNS = {
    'abstract': r'\bAbstract\b',
    'introduction': r'\b(?:1\.?\s+)?Introduction\b',
    'related_work': r'\b(?:\d+\.?\s+)?Related\s+Work\b',
    'methodology': r'\b(?:\d+\.?\s+)?(?:Methodology|Methods|Approach)\b',
    'experiments': r'\b(?:\d+\.?\s+)?(?:Experiments|Experimental\s+Results)\b',
    'results': r'\b(?:\d+\.?\s+)?Results\b',
    'discussion': r'\b(?:\d+\.?\s+)?Discussion\b',
    'conclusion': r'\b(?:\d+\.?\s+)?Conclusion\b',
    'references': r'\b(?:References|Bibliography)\b'
}


class PDFParser:
    """Extract text and structure from research papers."""
    
    def __init__(self):
        self.stats = {
            'total_processed': 0,
            'successful': 0,
            'failed': 0,
            'avg_pages': 0,
            'avg_text_length': 0
        }
    
    def extract_text_from_pdf(self, pdf_path: Path) -> Optional[Dict]:
        """
        Extract text and metadata from a single PDF file.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            Dictionary containing extracted text and metadata, or None if failed
        """
        try:
            doc = fitz.open(pdf_path)
            
            # Extract text from all pages
            full_text = ""
            page_texts = []
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text()
                page_texts.append(text)
                full_text += text + "\n\n"
            
            # Identify sections
            sections = self._identify_sections(full_text)
            
            # Extract metadata
            num_pages = len(doc)
            file_size = pdf_path.stat().st_size
            
            doc.close()
            
            return {
                'file_path': str(pdf_path),
                'num_pages': num_pages,
                'file_size_bytes': file_size,
                'text_length': len(full_text),
                'full_text': full_text,
                'page_texts': page_texts,
                'sections': sections,
                'extraction_success': True
            }
            
        except Exception as e:
            logger.error(f"Failed to extract from {pdf_path}: {e}")
            return None
    
    def _identify_sections(self, text: str) -> Dict[str, int]:
        """
        Identify approximate positions of paper sections.
        
        Args:
            text: Full paper text
            
        Returns:
            Dictionary mapping section names to character positions
        """
        sections = {}
        
        for section_name, pattern in SECTION_PATTERNS.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                sections[section_name] = match.start()
        
        return sections
    
    def extract_section_text(self, full_text: str, sections: Dict[str, int]) -> Dict[str, str]:
        """
        Extract text for each identified section.
        
        Args:
            full_text: Full paper text
            sections: Dictionary of section positions
            
        Returns:
            Dictionary mapping section names to their text content
        """
        section_texts = {}
        sorted_sections = sorted(sections.items(), key=lambda x: x[1])
        
        for i, (section_name, start_pos) in enumerate(sorted_sections):
            # Determine end position (start of next section or end of text)
            if i + 1 < len(sorted_sections):
                end_pos = sorted_sections[i + 1][1]
            else:
                end_pos = len(full_text)
            
            section_texts[section_name] = full_text[start_pos:end_pos].strip()
        
        return section_texts
    
    def process_single_paper(self, pdf_path: Path) -> bool:
        """Process a single paper PDF."""
        try:
            arxiv_id = pdf_path.stem
            
            # Check if already processed
            text_path = TEXT_DIR / f"{arxiv_id}.txt"
            if text_path.exists():
                logger.debug(f"Already processed: {arxiv_id}")
                return True
            
            logger.info(f"Processing: {arxiv_id}")
            
            # Extract text
            result = self.extract_text_from_pdf(pdf_path)
            
            if result is None:
                self.stats['failed'] += 1
                return False
            
            # Save full text
            text_path.parent.mkdir(parents=True, exist_ok=True)
            with open(text_path, 'w', encoding='utf-8') as f:
                f.write(result['full_text'])
            
            # Update metadata
            metadata_path = METADATA_DIR / f"{arxiv_id}.json"
            if metadata_path.exists():
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)
                
                metadata.update({
                    'text_path': str(text_path),
                    'num_pages': result['num_pages'],
                    'file_size_bytes': result['file_size_bytes'],
                    'text_length': result['text_length'],
                    'sections_found': list(result['sections'].keys()),
                    'extraction_success': True
                })
                
                with open(metadata_path, 'w') as f:
                    json.dump(metadata, f, indent=2)
            
            self.stats['successful'] += 1
            self.stats['total_processed'] += 1
            
            return True
            
        except Exception as e:
            logger.error(f"Error processing {pdf_path}: {e}")
            self.stats['failed'] += 1
            return False
    
    def process_all_papers(self, parallel: bool = True):
        """Process all collected papers."""
        logger.info("="*80)
        logger.info("Starting PDF Text Extraction")
        logger.info("="*80)
        
        # Collect all PDF files
        pdf_files = []
        for category_dir in PDF_BASE.iterdir():
            if category_dir.is_dir():
                pdf_files.extend(category_dir.glob("*.pdf"))
        
        logger.info(f"Found {len(pdf_files)} PDF files to process")
        
        if parallel and len(pdf_files) > 10:
            # Parallel processing
            num_workers = min(cpu_count(), 8)
            logger.info(f"Using {num_workers} parallel workers")
            
            with Pool(num_workers) as pool:
                results = pool.map(self.process_single_paper, pdf_files)
            
            self.stats['successful'] = sum(results)
            self.stats['failed'] = len(results) - sum(results)
            self.stats['total_processed'] = len(results)
        else:
            # Sequential processing
            for pdf_path in pdf_files:
                self.process_single_paper(pdf_path)
        
        self._print_summary()
    
    def _print_summary(self):
        """Print processing summary."""
        logger.info("\n" + "="*80)
        logger.info("PROCESSING SUMMARY")
        logger.info("="*80)
        logger.info(f"Total papers processed: {self.stats['total_processed']}")
        logger.info(f"Successful extractions: {self.stats['successful']}")
        logger.info(f"Failed extractions: {self.stats['failed']}")
        
        if self.stats['successful'] > 0:
            success_rate = (self.stats['successful'] / self.stats['total_processed']) * 100
            logger.info(f"Success rate: {success_rate:.2f}%")
        
        logger.info("="*80)
        
        # Save summary
        summary_path = Path("logs/processing_summary.json")
        with open(summary_path, 'w') as f:
            json.dump(self.stats, f, indent=2)


def main():
    """Main entry point."""
    TEXT_DIR.mkdir(parents=True, exist_ok=True)
    
    parser = PDFParser()
    parser.process_all_papers(parallel=True)
    
    logger.info("\n✅ PDF processing complete! Check logs/processing_summary.json for details.")


if __name__ == "__main__":
    main()
