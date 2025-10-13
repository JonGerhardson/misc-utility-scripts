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
---
## batch_caps.sh 

Loops throuh a target directory and processes all video files to create a "montage" image from screen captures, creates an info frame showing video metadata as text and/or QR code. 

Use ```--single``` flag to process only one video. 

Tested on linux. Should work on macOS too. 

You need the following dependencies installed. 

MacOS
```
brew install ffmpeg imagemagick exiftool qrencode coreutils parallel
```

You can also install these via other package managers like apt on linux:
```
sudo apt install ffmpeg imagemagick exiftool qrencode parallel
```

The info frame by default will show the following information:
```
<YOUR CUSTOM TITLE HERE>
------------------------

Filename: [video_filename.mp4]
File Size: [file_size]
Modified: [modification_date]
Processed: [date and time of processing by this script]
Duration: [video_duration]
Dimensions: [video_resolution]
Frame Rate: [video_framerate]
Capture Interval: 1 frame per 90 seconds

SHA256: (This is split onto two lines to prevent cropping issues.)
[first_32_characters_of_hash]
[last_32_characters_of_hash] 
```
You can add a second frame showing the same info as a machine readable qr code with the ```--qr``` option. You can also display any metadata info available through exiftool as a command line argument, but may run into formatting problems. 

Files are processed in parallel. On linux this script will use /dev/shm as a temporary directory if available. This is probably not the best way to implement this but worked fine for me. Change ```TEMP_DIR_BASE="/dev/shm"```. If files are on a spinning hard disk rather than an SSD use ```--hdd``` to read files sequentially. 

Performance note: File hashes are calculated using the SHA256 algorithm on the full file. This is the slowest step, and if you don't need that information it is reccomended you skip it by including ```--no_hash``` in your command. This will let the script run significantly faster. 
```
OPTIONS:
  -s, --single <filepath>   Process a single video file instead of searching a directory.
                            This option overrides any [DIRECTORY] argument.
  --no_hash                 Skips sha256sum calculation and omits it from the info slide.
  --no_meta                 Skips all metadata gathering and creation of info/QR slides.
  --qr                      Includes a QR code slide with metadata. Default is off.
  --hdd                     Optimizes for HDDs by processing files sequentially.
                            Default is to process in parallel, optimized for SSDs.
  --dry-run                 Prints the list of video files that would be processed and exits.
  --test                    Processes only the first video found and quits.
                            (Ignored in --single file mode).
  --interval <seconds>      Set the interval in seconds for taking screenshots.
                            Accepts decimals (e.g., 0.5). Default: 90.
  --width <number>          Sets the number of tiles (images) per row in the montage.
                            Default: 4.
  --max_frames <number>     Sets the maximum number of screenshots to capture per video.
                            Default: no limit.
  --static_text "<text>"    Sets the custom title text on the info slide.
                            If not provided, the script will prompt you.
  --exiftool "<tags>"       Advanced: Specify custom exiftool tags to display.
                            Example: "-FileSize -MIMEType -ImageSize".
                            Warning: Changing the number of tags may break the script.
  -h, --help                Displays this help message and exits.
```
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

## leagal_splitter.py
Splits a long legal document into several smaller files based on the document's structure. Reads markdown files. Conver PDFs to .md first using marker-pdf or a similar tool. 

**Requirements:**
Uses ollama and your preferred LLM model. You don't need anything crazy for this, I've been using Phi4:14b (~10 GB) with good results. 
```
python legal_splitter.py input.md ./output_dir \
  --model llama3 \          # Use different model
  --chunk_size 10000 \      # Analysis window size (chars)
  --overlap 2000 \          # Chunk overlap (chars)
  --min_section 1500        # Minimum section length (chars)
```

Default prompt: 

"""ANALYZE THIS LEGAL DOCUMENT AND IDENTIFY STRUCTURAL BOUNDARIES. RETURN:
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
/# AGREEMENT AND PLAN OF MERGER
/## ARTICLE III: REPRESENTATIONS
/### Section 5.3. Governing Law
CLAUSE 4.2: Notices
SCHEDULE A
EXHIBIT B-1

TEXT TO ANALYZE:
{chunk}

RETURN ONLY THE EXACT SECTION HEADERS, ONE PER LINE:"""






