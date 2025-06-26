"""
Document parsing utilities for MyAvatar
Handles .txt, .docx, and .pdf file parsing
"""
import io
import logging
from typing import Optional

logger = logging.getLogger(__name__)

def parse_document(file_content: bytes, filename: str) -> Optional[str]:
    """
    Parse document content from various file formats
    
    Args:
        file_content: Raw file bytes
        filename: Original filename with extension
        
    Returns:
        Extracted text content or None if parsing fails
    """
    try:
        file_extension = filename.lower().split('.')[-1] if '.' in filename else ''
        
        if file_extension == 'txt':
            return parse_txt(file_content)
        elif file_extension == 'docx':
            return parse_docx(file_content)
        elif file_extension == 'pdf':
            return parse_pdf(file_content)
        else:
            logger.warning(f"Unsupported file format: {file_extension}")
            return None
            
    except Exception as e:
        logger.error(f"Error parsing document {filename}: {str(e)}")
        return None

def parse_txt(file_content: bytes) -> str:
    """Parse plain text file"""
    try:
        # Try different encodings
        for encoding in ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']:
            try:
                text = file_content.decode(encoding)
                # Remove BOM if present
                text = text.replace('\ufeff', '')
                return text.strip()
            except UnicodeDecodeError:
                continue
        
        # If all encodings fail, use utf-8 with error handling
        return file_content.decode('utf-8', errors='replace').strip()
        
    except Exception as e:
        logger.error(f"Error parsing TXT file: {str(e)}")
        return None

def parse_docx(file_content: bytes) -> str:
    """Parse Word document (.docx)"""
    try:
        from docx import Document
        
        # Create document from bytes
        doc_stream = io.BytesIO(file_content)
        doc = Document(doc_stream)
        
        # Extract text from all paragraphs
        text_parts = []
        for paragraph in doc.paragraphs:
            if paragraph.text.strip():
                text_parts.append(paragraph.text.strip())
        
        return '\n'.join(text_parts)
        
    except ImportError:
        logger.error("python-docx not installed. Cannot parse .docx files")
        return None
    except Exception as e:
        logger.error(f"Error parsing DOCX file: {str(e)}")
        return None

def parse_pdf(file_content: bytes) -> str:
    """Parse PDF document"""
    try:
        import pdfplumber
        
        # Create PDF from bytes
        pdf_stream = io.BytesIO(file_content)
        text_parts = []
        
        with pdfplumber.open(pdf_stream) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text.strip())
        
        return '\n'.join(text_parts)
        
    except ImportError:
        logger.error("pdfplumber not installed. Cannot parse .pdf files")
        return None
    except Exception as e:
        logger.error(f"Error parsing PDF file: {str(e)}")
        return None

def clean_and_truncate_text(text: str, max_length: int = 1500) -> dict:
    """
    Clean and truncate text content
    
    Returns:
        dict with 'text', 'truncated', and 'original_length' keys
    """
    if not text:
        return {'text': '', 'truncated': False, 'original_length': 0}
    
    original_length = len(text)
    
    # Clean up text
    # Remove excessive whitespace but preserve paragraph breaks
    cleaned_text = '\n'.join(line.strip() for line in text.split('\n') if line.strip())
    
    # Remove multiple consecutive newlines
    import re
    cleaned_text = re.sub(r'\n\s*\n\s*\n+', '\n\n', cleaned_text)
    
    # Truncate if necessary
    truncated = False
    if len(cleaned_text) > max_length:
        cleaned_text = cleaned_text[:max_length].strip()
        truncated = True
    
    return {
        'text': cleaned_text,
        'truncated': truncated,
        'original_length': original_length
    }
