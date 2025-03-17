import argparse
import os
import requests
from tqdm import tqdm

def read_file(file_path):
    """Read the content of a text file."""
    with open(file_path, 'r', encoding='utf-8') as file:
        return file.read()

def split_text(text, chunk_size=3000, overlap=500):
    """Split text into overlapping chunks."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks

def get_split_points(chunk, model_name):
    """Get potential split points using Ollama."""
    prompt = f"""Analyze this text and identify natural section breaks. Return ONLY the exact phrases that 
should precede each break, one per line. Focus on topic changes and semantic boundaries:

{chunk}"""

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
        return response.json()['response'].strip().split('\n')
    except Exception as e:
        print(f"Error processing chunk: {e}")
        return []

def find_valid_splits(full_text, candidates):
    """Find valid split positions in the original text."""
    splits = []
    for candidate in candidates:
        idx = full_text.find(candidate)
        if idx != -1:
            # Split after the candidate phrase
            split_pos = idx + len(candidate)
            splits.append(split_pos)
    # Deduplicate and sort splits
    return sorted(list(set(splits)))

def save_sections(full_text, split_points, output_dir):
    """Save sections to files."""
    os.makedirs(output_dir, exist_ok=True)
    split_points = sorted(split_points)
    prev = 0
    
    for i, pos in enumerate(split_points):
        # Skip overlapping splits
        if pos <= prev:
            continue
            
        section = full_text[prev:pos].strip()
        if section:
            with open(os.path.join(output_dir, f'section_{i+1:03d}.txt'), 'w', encoding='utf-8') as f:
                f.write(section)
        prev = pos
    
    # Save remaining text
    final_section = full_text[prev:].strip()
    if final_section:
        with open(os.path.join(output_dir, f'section_{len(split_points)+1:03d}.txt'), 'w', encoding='utf-8') as f:
            f.write(final_section)

def main():
    parser = argparse.ArgumentParser(description='Semantically split a text file using Ollama.')
    parser.add_argument('input_file', help='Path to input text file')
    parser.add_argument('output_dir', help='Output directory for sections')
    parser.add_argument('--model', default='mistral', help='Ollama model to use (default: mistral)')
    parser.add_argument('--chunk_size', type=int, default=3000, help='Processing chunk size (default: 3000)')
    parser.add_argument('--overlap', type=int, default=500, help='Chunk overlap (default: 500)')
    
    args = parser.parse_args()
    
    full_text = read_file(args.input_file)
    chunks = split_text(full_text, args.chunk_size, args.overlap)
    
    all_candidates = []
    for chunk in tqdm(chunks, desc='Processing text chunks'):
        candidates = get_split_points(chunk, args.model)
        all_candidates.extend(candidates)
    
    split_points = find_valid_splits(full_text, all_candidates)
    save_sections(full_text, split_points, args.output_dir)
    
    print(f"Created {len(split_points)+1} sections in {args.output_dir}")

if __name__ == '__main__':
    main()
