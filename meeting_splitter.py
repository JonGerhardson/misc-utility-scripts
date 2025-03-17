import argparse
import os
import re
import requests
from tqdm import tqdm

def read_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        return file.read()

def split_text(text, chunk_size=4000, overlap=800):
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks

def get_topic_transitions(chunk, model_name):
    """Identify meeting agenda items and topic transitions"""
    prompt = f"""ANALYZE THIS MEETING TRANSCRIPT AND IDENTIFY TOPIC TRANSITIONS. RETURN:
1. Exact phrases where new agenda items or presentations begin
2. Focus on these patterns:
   - Agenda item announcements ("Now moving to item 3...")
   - Presentation titles ("Quarterly Financial Report Overview")
   - Moderation transitions ("Let's open the floor for discussion")
   - Topic shift markers ("Next, we'll discuss...")
3. Include timestamps if available
4. Return ONLY the exact transition phrases, one per line

EXAMPLES OF VALID RESPONSES:
[00:15:00] Chair: Moving to agenda item 5
Presentation: Community Outreach Strategy
Moderator: Let's hear from department heads
[00:30:45] Topic: Budget Allocation Discussion

TRANSCRIPT CHUNK:
{chunk}

TOPIC TRANSITIONS:"""

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
                if line.strip() and len(line.strip()) > 5]
    except Exception as e:
        print(f"Error processing chunk: {e}")
        return []

def find_topic_boundaries(full_text, candidates, min_section=1000):
    """Find boundaries that capture complete discussions"""
    boundaries = [0]
    
    # First find structural markers
    priority_patterns = [
        r'\n\d+\.\s[A-Z]+',  # Agenda items like "1. INTRODUCTION"
        r'\n[A-Z]{2,}:\s',   # All caps speaker labels
        r'\[?\d+:\d+:\d+\]?',# Timestamps
        r'\nPresentation:\s',
        r'\nTopic:\s'
    ]
    
    for pattern in priority_patterns:
        for match in re.finditer(pattern, full_text):
            pos = match.start()
            if pos > boundaries[-1] + min_section:
                boundaries.append(pos)
    
    # Add AI-identified candidates
    for candidate in candidates:
        idx = full_text.find(candidate)
        if idx != -1 and idx > boundaries[-1] + min_section//2:
            boundaries.append(idx)
    
    # Final processing
    boundaries = sorted(list(set(boundaries)))
    boundaries.append(len(full_text))
    
    # Merge adjacent boundaries
    final_boundaries = [boundaries[0]]
    for b in boundaries[1:]:
        if b - final_boundaries[-1] >= min_section:
            final_boundaries.append(b)
        else:
            # Merge small sections with previous
            final_boundaries[-1] = b
    
    return final_boundaries

def save_discussions(full_text, boundaries, output_dir):
    """Save complete discussions with meaningful filenames"""
    os.makedirs(output_dir, exist_ok=True)
    
    for i in range(len(boundaries)-1):
        start = boundaries[i]
        end = boundaries[i+1]
        section = full_text[start:end].strip()
        
        if section:
            # Extract potential title
            title_match = re.search(r'(Presentation|Topic|Agenda Item)[:\s]+(.+?)\n', section)
            filename = f"discussion_{i+1:03d}.txt"
            if title_match:
                clean_title = re.sub(r'[^\w\s-]', '', title_match.group(2))[:40].strip()
                filename = f"{i+1:03d}_{clean_title}.txt"
            
            with open(os.path.join(output_dir, filename), 'w', encoding='utf-8') as f:
                f.write(section)

def main():
    parser = argparse.ArgumentParser(description='Meeting Transcript Splitter')
    parser.add_argument('input_file', help='Input transcript file')
    parser.add_argument('output_dir', help='Output directory')
    parser.add_argument('--model', default='mistral')
    parser.add_argument('--chunk_size', type=int, default=6000)
    parser.add_argument('--overlap', type=int, default=1000)
    parser.add_argument('--min_section', type=int, default=1500,
                      help='Minimum discussion length (characters)')
    
    args = parser.parse_args()
    
    full_text = read_file(args.input_file)
    chunks = split_text(full_text, args.chunk_size, args.overlap)
    
    all_candidates = []
    for chunk in tqdm(chunks, desc='Identifying topics'):
        candidates = get_topic_transitions(chunk, args.model)
        all_candidates.extend(candidates)
    
    boundaries = find_topic_boundaries(full_text, all_candidates, args.min_section)
    save_discussions(full_text, boundaries, args.output_dir)
    
    print(f"Created {len(boundaries)-1} discussion sections in {args.output_dir}")

if __name__ == '__main__':
    main()
