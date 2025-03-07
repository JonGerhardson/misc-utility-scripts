# misc-utility-scripts
odds and ends 

mp4tosrt.sh -- for any mp4 videos in a directory makes a .wav copy using ffmpeg and then transcribes the .wav using whisper --large and saves the transcript as an srt file (closed captions). Deletes wav file upon completion to save space. 

Requirements: 
ffmpeg
open-ai whisper

usage:
copy script to directory with vids you want captions for
open terminal and cd in
bash mp4tosrt.sh

To use a different size model or change the output format, adjust line 27. 
>  whisper "$WAV_FILE" --model large --output_format srt

run $ whisper -h to see available options

---
## ollama-summarize-markdown.py
summarize all markdown files in a directory using ollama, save summary as new file named [original]-summary.md 

Uses a 32k context window by default. Edit line 61 for a different size. 

Usage:

```python ollama-summarize-markdown.py --folder 'path/to/folder' --model <modelname>```

System prompt and user prompt are on lines 58 and 59. 

Default prompt: 

{"role": "system", "content": "Provide a concise technical summary of this markdown document."},
 
 {"role": "user", "content": f"Summarize this document:\n\n{content}"}



