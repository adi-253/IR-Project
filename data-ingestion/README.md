# Data Ingestion

![LangChain Document Flow](images/langchain-document.svg)

## Overview

This repository provides a modular framework for ingesting, parsing, and chunking data from various sources (text, CSV, Excel, PDF, Word, JSON, SQL databases) for downstream AI and retrieval-augmented generation (RAG) tasks.

**NEW:** Automated ArXiv paper collection system for 100 technical research papers. See [ArXiv Collection](#arxiv-collection-project) below.

## Folder Structure

- `src/`
  - `core.ipynb`: Core text splitting and document loading examples
  - `csv_excel_parsing.ipynb`: CSV/Excel parsing and metadata enrichment
  - `data_parsing_doc.ipynb`: Word document parsing (docx/txt)
  - `data_parsing_pdf.ipynb`: PDF parsing and chunking
  - `database_parsing.ipynb`: SQL database parsing
  - `json_parsing.ipynb`: JSON/JSONL parsing
  - `data/`: Sample data files for each format

- `collections/scripts/` **NEW**
  - `collect_arxiv.py`: Automated ArXiv paper collection
  - `parse_papers.py`: PDF text extraction
  - `chunk_papers.py`: Multi-strategy chunking
  - `validate_data.py`: Data quality validation
  - `run_pipeline.py`: Master pipeline orchestrator

- `raw_data/` **NEW** - Collected papers and metadata
- `processed/` **NEW** - Chunked data ready for RAG
- `images/` - Documentation images

## Setup

1. Create and activate a virtual environment:
   ```sh
   uv init
   uv venv
   source .venv/bin/activate  # Linux/Mac
   # OR
   .venv\Scripts\activate  # Windows
   uv pip install -r requirements.txt
   ```
