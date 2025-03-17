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


---
## meeting_splitter.py

Splits a long meeting transcript into several smaller files based on topics discussed. 

**Requirements:**
Uses ollama and your preferred LLM model. You don't need anything crazy for this, I've been using Phi4:14b (~10 GB) with good results. 

```
pip install requests tqdm
```


**Usage** ```python meeting_splitter.py [input file] [output directory] [options] ```

Example:
```
$ python meeting_splitter.py "transcript.txt" Documents/output_folder   --model phi4:latest   --chunk_size 8000   --overlap 1200   --min_section 2000
```

You should see something like:
```
Identifying topics: 100%|███████████████████████| 11/11 [02:16<00:00, 12.40s/it]
Created 3 discussion sections in output_folder
```






