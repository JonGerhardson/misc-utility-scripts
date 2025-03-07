import os
import argparse
import requests
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description='Summarize markdown files using Ollama.')
    parser.add_argument('--folder', required=True, help='Path to the folder containing markdown files')
    parser.add_argument('--model', default='mistral', help='Ollama model to use (default: mistral)')
    args = parser.parse_args()

    # Convert to Path object for better handling
    folder = Path(args.folder).expanduser()
    model = args.model

    # Debug: Show initial parameters
    print(f"📂 Target folder: {folder}")
    print(f"🤖 Selected model: {model}")
    
    if not folder.exists():
        print(f"❌ Error: Folder {folder} does not exist")
        return
    if not folder.is_dir():
        print(f"❌ Error: {folder} is not a directory")
        return

    # Check Ollama availability
    ollama_url = 'http://localhost:11434/api/chat'
    try:
        ping = requests.get('http://localhost:11434', timeout=5)
        print(f"🟢 Ollama connection status: {ping.status_code}")
    except requests.ConnectionError:
        print("❌ Could not connect to Ollama - Is it running? (http://localhost:11434)")
        return

    # Get list of markdown files
    md_files = list(folder.glob('*.md'))
    print(f"🔍 Found {len(md_files)} markdown files in directory")
    
    for filepath in md_files:
        if '-summary.md' in filepath.name:
            print(f"⏭️ Skipping summary file: {filepath.name}")
            continue
            
        print(f"\n📄 Processing: {filepath.name}")
        
        try:
            content = filepath.read_text(encoding='utf-8')
            print(f"📝 Read {len(content)} characters from {filepath.name}")
        except Exception as e:
            print(f"❌ Read error: {str(e)}")
            continue

        # Prepare the API request
        data = {
            "model": model,
            "messages": [
                {"role": "system", "content": "Provide a concise technical summary of this markdown document."},
                {"role": "user", "content": f"Summarize this document:\n\n{content}"}
            ],
            "options": {"num_ctx": 32768},
            "stream": False
        }

        try:
            print("🚀 Sending request to Ollama...")
            response = requests.post(ollama_url, json=data)
            response.raise_for_status()
            print(f"✅ API response: {response.status_code}")
            
            # Debug: Show full response if needed
            # print("Raw response:", response.json())
            
            summary = response.json()['message']['content']
            print(f"📃 Received summary ({len(summary)} characters)")
        except Exception as e:
            print(f"❌ API error: {str(e)}")
            continue

        # Create summary filename
        summary_path = filepath.with_stem(f"{filepath.stem}-summary")
        print(f"💾 Saving summary to: {summary_path.name}")

        try:
            summary_path.write_text(summary, encoding='utf-8')
            print("✅ Summary saved successfully")
        except Exception as e:
            print(f"❌ Save error: {str(e)}")

if __name__ == "__main__":
    main()
