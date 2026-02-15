"""
Chunking Strategies for Research Papers
Implements multiple chunking approaches for optimal RAG performance.
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Tuple
import re

from langchain.text_splitter import (
    RecursiveCharacterTextSplitter,
    TokenTextSplitter
)
from langchain_core.documents import Document

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/chunking.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Paths
TEXT_DIR = Path("raw_data/arxiv/text")
METADATA_DIR = Path("raw_data/arxiv/metadata")
CHUNKED_BASE = Path("processed/chunked")

# Section patterns
SECTION_HEADERS = [
    r'\bAbstract\b',
    r'\b(?:1\.?\s+)?Introduction\b',
    r'\b(?:\d+\.?\s+)?Related\s+Work\b',
    r'\b(?:\d+\.?\s+)?(?:Methodology|Methods|Approach)\b',
    r'\b(?:\d+\.?\s+)?(?:Experiments|Experimental\s+Results)\b',
    r'\b(?:\d+\.?\s+)?Results\b',
    r'\b(?:\d+\.?\s+)?Discussion\b',
    r'\b(?:\d+\.?\s+)?Conclusion\b',
    r'\b(?:References|Bibliography)\b'
]


class PaperChunker:
    """Implements multiple chunking strategies for research papers."""
    
    def __init__(self):
        self.stats = {
            'papers_processed': 0,
            'recursive_chunks': 0,
            'semantic_chunks': 0,
            'token_chunks': 0,
            'section_chunks': 0,
            'hybrid_chunks': 0
        }
    
    def chunk_recursive(self, text: str, metadata: Dict) -> List[Document]:
        """
        Recursive character-based chunking.
        
        Args:
            text: Full paper text
            metadata: Paper metadata
            
        Returns:
            List of Document objects
        """
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        
        chunks = splitter.split_text(text)
        
        documents = []
        for i, chunk in enumerate(chunks):
            doc = Document(
                page_content=chunk,
                metadata={
                    **metadata,
                    'chunk_id': i,
                    'chunk_type': 'recursive',
                    'total_chunks': len(chunks)
                }
            )
            documents.append(doc)
        
        self.stats['recursive_chunks'] += len(documents)
        return documents
    
    def chunk_token_based(self, text: str, metadata: Dict) -> List[Document]:
        """
        Token-based chunking for direct LLM consumption.
        
        Args:
            text: Full paper text
            metadata: Paper metadata
            
        Returns:
            List of Document objects
        """
        splitter = TokenTextSplitter(
            chunk_size=512,
            chunk_overlap=50
        )
        
        chunks = splitter.split_text(text)
        
        documents = []
        for i, chunk in enumerate(chunks):
            doc = Document(
                page_content=chunk,
                metadata={
                    **metadata,
                    'chunk_id': i,
                    'chunk_type': 'token_based',
                    'total_chunks': len(chunks),
                    'max_tokens': 512
                }
            )
            documents.append(doc)
        
        self.stats['token_chunks'] += len(documents)
        return documents
    
    def chunk_by_sections(self, text: str, metadata: Dict) -> List[Document]:
        """
        Section-based chunking for structured papers.
        
        Args:
            text: Full paper text
            metadata: Paper metadata
            
        Returns:
            List of Document objects
        """
        sections = self._extract_sections(text)
        
        documents = []
        for i, (section_name, section_text) in enumerate(sections):
            # Further split large sections
            if len(section_text) > 2000:
                subsplitter = RecursiveCharacterTextSplitter(
                    chunk_size=1000,
                    chunk_overlap=200
                )
                subchunks = subsplitter.split_text(section_text)
                
                for j, subchunk in enumerate(subchunks):
                    doc = Document(
                        page_content=subchunk,
                        metadata={
                            **metadata,
                            'section': section_name,
                            'chunk_id': f"{i}_{j}",
                            'chunk_type': 'section_based',
                            'is_subsection': True
                        }
                    )
                    documents.append(doc)
            else:
                doc = Document(
                    page_content=section_text,
                    metadata={
                        **metadata,
                        'section': section_name,
                        'chunk_id': i,
                        'chunk_type': 'section_based',
                        'is_subsection': False
                    }
                )
                documents.append(doc)
        
        self.stats['section_chunks'] += len(documents)
        return documents
    
    def chunk_hybrid(self, text: str, metadata: Dict) -> List[Document]:
        """
        Hybrid approach: section-aware + semantic splits.
        
        Args:
            text: Full paper text
            metadata: Paper metadata
            
        Returns:
            List of Document objects
        """
        sections = self._extract_sections(text)
        
        documents = []
        chunk_id = 0
        
        for section_name, section_text in sections:
            # Skip very short sections
            if len(section_text) < 100:
                continue
            
            # Use different strategies for different sections
            if section_name.lower() in ['abstract', 'conclusion']:
                # Keep as single chunks
                doc = Document(
                    page_content=section_text,
                    metadata={
                        **metadata,
                        'section': section_name,
                        'chunk_id': chunk_id,
                        'chunk_type': 'hybrid',
                        'strategy': 'whole_section'
                    }
                )
                documents.append(doc)
                chunk_id += 1
            else:
                # Smart splitting for larger sections
                splitter = RecursiveCharacterTextSplitter(
                    chunk_size=800,
                    chunk_overlap=150,
                    separators=["\n\n", "\n", ". ", " ", ""]
                )
                
                chunks = splitter.split_text(section_text)
                
                for chunk in chunks:
                    doc = Document(
                        page_content=chunk,
                        metadata={
                            **metadata,
                            'section': section_name,
                            'chunk_id': chunk_id,
                            'chunk_type': 'hybrid',
                            'strategy': 'smart_split'
                        }
                    )
                    documents.append(doc)
                    chunk_id += 1
        
        self.stats['hybrid_chunks'] += len(documents)
        return documents
    
    def _extract_sections(self, text: str) -> List[Tuple[str, str]]:
        """
        Extract sections from paper text.
        
        Args:
            text: Full paper text
            
        Returns:
            List of (section_name, section_text) tuples
        """
        sections = []
        section_positions = []
        
        # Find all section headers
        for pattern in SECTION_HEADERS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                section_name = match.group(0).strip()
                section_positions.append((match.start(), section_name))
        
        # Sort by position
        section_positions.sort()
        
        # Extract text between sections
        for i, (start_pos, section_name) in enumerate(section_positions):
            if i + 1 < len(section_positions):
                end_pos = section_positions[i + 1][0]
            else:
                end_pos = len(text)
            
            section_text = text[start_pos:end_pos].strip()
            
            # Remove the header from text
            section_text = re.sub(section_name, '', section_text, count=1).strip()
            
            if section_text:
                sections.append((section_name, section_text))
        
        # If no sections found, treat entire text as one section
        if not sections:
            sections.append(("Full Text", text))
        
        return sections
    
    def process_paper(self, arxiv_id: str):
        """Process a single paper with all chunking strategies."""
        try:
            # Load text and metadata
            text_path = TEXT_DIR / f"{arxiv_id}.txt"
            metadata_path = METADATA_DIR / f"{arxiv_id}.json"
            
            if not text_path.exists() or not metadata_path.exists():
                logger.warning(f"Missing files for {arxiv_id}")
                return
            
            with open(text_path, 'r', encoding='utf-8') as f:
                text = f.read()
            
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
            
            logger.info(f"Chunking paper: {arxiv_id}")
            
            # Apply all chunking strategies
            base_metadata = {
                'arxiv_id': metadata['arxiv_id'],
                'title': metadata['title'],
                'primary_category': metadata.get('primary_category', 'unknown')
            }
            
            # 1. Recursive chunking
            recursive_docs = self.chunk_recursive(text, base_metadata)
            self._save_chunks(recursive_docs, 'recursive', arxiv_id)
            
            # 2. Token-based chunking
            token_docs = self.chunk_token_based(text, base_metadata)
            self._save_chunks(token_docs, 'token_based', arxiv_id)
            
            # 3. Section-based chunking
            section_docs = self.chunk_by_sections(text, base_metadata)
            self._save_chunks(section_docs, 'section_based', arxiv_id)
            
            # 4. Hybrid chunking
            hybrid_docs = self.chunk_hybrid(text, base_metadata)
            self._save_chunks(hybrid_docs, 'hybrid', arxiv_id)
            
            self.stats['papers_processed'] += 1
            
        except Exception as e:
            logger.error(f"Error processing {arxiv_id}: {e}")
    
    def _save_chunks(self, documents: List[Document], strategy: str, arxiv_id: str):
        """Save chunks to JSON file."""
        output_dir = CHUNKED_BASE / strategy
        output_dir.mkdir(parents=True, exist_ok=True)
        
        output_file = output_dir / f"{arxiv_id}.json"
        
        chunks_data = [
            {
                'content': doc.page_content,
                'metadata': doc.metadata
            }
            for doc in documents
        ]
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(chunks_data, f, indent=2)
    
    def process_all_papers(self):
        """Process all papers with all chunking strategies."""
        logger.info("="*80)
        logger.info("Starting Paper Chunking")
        logger.info("="*80)
        
        # Get all text files
        text_files = list(TEXT_DIR.glob("*.txt"))
        logger.info(f"Found {len(text_files)} papers to chunk")
        
        for text_file in text_files:
            arxiv_id = text_file.stem
            self.process_paper(arxiv_id)
        
        self._print_summary()
    
    def _print_summary(self):
        """Print chunking summary."""
        logger.info("\n" + "="*80)
        logger.info("CHUNKING SUMMARY")
        logger.info("="*80)
        logger.info(f"Papers processed: {self.stats['papers_processed']}")
        logger.info(f"Recursive chunks: {self.stats['recursive_chunks']}")
        logger.info(f"Token-based chunks: {self.stats['token_chunks']}")
        logger.info(f"Section-based chunks: {self.stats['section_chunks']}")
        logger.info(f"Hybrid chunks: {self.stats['hybrid_chunks']}")
        logger.info("="*80)
        
        # Save summary
        summary_path = Path("logs/chunking_summary.json")
        with open(summary_path, 'w') as f:
            json.dump(self.stats, f, indent=2)


def main():
    """Main entry point."""
    chunker = PaperChunker()
    chunker.process_all_papers()
    
    logger.info("\n✅ Chunking complete! Check logs/chunking_summary.json for details.")


if __name__ == "__main__":
    main()
