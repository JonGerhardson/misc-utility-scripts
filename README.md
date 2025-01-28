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
