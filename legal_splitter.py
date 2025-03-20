import re
import argparse
import os
import requests
from tqdm import tqdm

def read_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        return file.read()

def split_text(text, chunk_size=5000, overlap=1000):
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks

def get_legal_boundaries(chunk, model_name):
    """Identify legal document structural boundaries"""
    prompt = f"""ANALYZE THIS LEGAL DOCUMENT AND IDENTIFY STRUCTURAL BOUNDARIES. RETURN:
1. Exact headings, article numbers, or clause markers where new sections begin
2. Include hierarchical markers (e.g., '##', '###') if present
3. One marker per line
4. Focus on these patterns:
   - Document headings (e.g., '# Scope', '## Article 1: Definitions')
   - Numbered clauses (e.g., '3.2 Confidentiality Obligations')
   - Roman numeral sections (e.g., 'IV. INDEMNIFICATION')
   - Section breaks (e.g., horizontal rules)
   - Clause titles in bold or ALL CAPS

EXAMPLES OF VALID RESPONSES:
# AGREEMENT AND PLAN OF MERGER
## ARTICLE III: REPRESENTATIONS
### Section 5.3. Governing Law
CLAUSE 4.2: Notices
SCHEDULE A
EXHIBIT B-1

TEXT TO ANALYZE:
{chunk}

RETURN ONLY THE EXACT SECTION HEADERS, ONE PER LINE:"""

    try:
        response = requests.post(
            'http://localhost:11434/api/generate',
            json={
                'model': model_name,
                'prompt': prompt,
                'stream': False,
                'options': {'temperature': 0.3}
            }
        )
        response.raise_for_status()
        return [line.strip() for line in response.json()['response'].split('\n') 
                if line.strip() and len(line.strip()) > 2]
    except Exception as e:
        print(f"Error processing chunk: {e}")
        return []

def find_legal_boundaries(full_text, candidates, min_section_length):
    """Boundary detection optimized for legal documents"""
    boundaries = [0]
    
    # First process exact candidate matches
    for candidate in sorted(set(candidates), key=len, reverse=True):
        if not candidate:
            continue
        for match in re.finditer(re.escape(candidate), full_text):
            pos = match.start()
            if pos > boundaries[-1] + min_section_length:
                boundaries.append(pos)
    
    # Then look for markdown headings
    heading_patterns = [
        r'^\s*#+\s+.+$',  # Markdown headings
        r'\n[A-Z]{3,}[^a-z\n]{15,}',  # All-caps section headers
        r'\n(?:ARTICLE|SECTION|CLAUSE|SCHEDULE|EXHIBIT)\s+[IVXLCDM0-9.:]+',  # Legal headers
        r'\n\d+\.\d+\.',  # Numbered clauses
    ]
    
    for pattern in heading_patterns:
        for match in re.finditer(pattern, full_text, re.MULTILINE):
            pos = match.start()
            if pos > boundaries[-1] + min_section_length:
                boundaries.append(pos)
    
    # Final cleanup
    boundaries = sorted(list(set(boundaries)))
    boundaries.append(len(full_text))
    
    # Merge adjacent boundaries that are too close
    final_boundaries = [boundaries[0]]
    for b in boundaries[1:]:
        if b - final_boundaries[-1] >= min_section_length:
            final_boundaries.append(b)
        elif b > final_boundaries[-1]:
            final_boundaries[-1] = b  # Take later boundary
    
    return final_boundaries

def extract_heading(section_text):
    """Extract meaningful heading from section text"""
    for line in section_text.split('\n'):
        line = line.strip()
        if line.startswith('#'):
            # Clean markdown heading
            clean_line = re.sub(r'^#+\s*', '', line)
            clean_line = re.sub(r'[^a-zA-Z0-9 \-_]', '', clean_line)
            return clean_line.strip()[:50]
        if re.match(r'^(ARTICLE|SECTION|CLAUSE)', line, re.IGNORECASE):
            return re.sub(r'[^a-zA-Z0-9 \-_]', '', line)[:50]
    return "section"

def save_legal_sections(full_text, boundaries, output_dir):
    """Save sections with legal-appropriate filenames"""
    os.makedirs(output_dir, exist_ok=True)
    
    for i in range(len(boundaries)-1):
        start = boundaries[i]
        end = boundaries[i+1]
        section = full_text[start:end].strip()
        
        if section:
            heading = extract_heading(section)
            filename = f"{i+1:03d}_{heading.replace(' ', '_')}.md"
            filepath = os.path.join(output_dir, filename.lower())
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(section)

def main():
    parser = argparse.ArgumentParser(description='Legal document semantic splitter')
    parser.add_argument('input_file', help='Input Markdown file')
    parser.add_argument('output_dir', help='Output directory')
    parser.add_argument('--model', default='phi4', help='Ollama model')
    parser.add_argument('--chunk_size', type=int, default=5000,
                      help='Analysis chunk size (default: 5000 chars)')
    parser.add_argument('--overlap', type=int, default=1000,
                      help='Chunk overlap (default: 1000 chars)')
    parser.add_argument('--min_section', type=int, default=1000,
                      help='Minimum section length (default: 1000 chars)')
    
    args = parser.parse_args()
    
    full_text = read_file(args.input_file)
    chunks = split_text(full_text, args.chunk_size, args.overlap)
    
    all_candidates = []
    for chunk in tqdm(chunks, desc='Analyzing document'):
        candidates = get_legal_boundaries(chunk, args.model)
        all_candidates.extend(candidates)
    
    boundaries = find_legal_boundaries(full_text, all_candidates, args.min_section)
    save_legal_sections(full_text, boundaries, args.output_dir)
    
    print(f"Created {len(boundaries)-1} legal sections in {args.output_dir}")

if __name__ == '__main__':
    main()
