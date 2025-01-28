#!/bin/bash

# Loop through all MP4 files in the current directory
for INPUT_MP4 in *.mp4; do
  # Check if there are any MP4 files
  if [ ! -f "$INPUT_MP4" ]; then
    echo "No MP4 files found in the current directory."
    exit 1
  fi

  # Get the base name of the file (without extension)
  BASENAME=$(basename "$INPUT_MP4" .mp4)

  # Convert MP4 to WAV
  WAV_FILE="${BASENAME}.wav"
  echo "Converting $INPUT_MP4 to $WAV_FILE..."
  ffmpeg -i "$INPUT_MP4" -vn -acodec pcm_s16le -ar 16000 -ac 1 "$WAV_FILE"

  # Check if conversion was successful
  if [ $? -ne 0 ]; then
    echo "Error: Failed to convert $INPUT_MP4 to WAV."
    continue
  fi

  # Transcribe WAV using Whisper (large model)
  echo "Transcribing $WAV_FILE using Whisper (large model)..."
  whisper "$WAV_FILE" --model large --output_format srt

  # Check if transcription was successful
  if [ $? -ne 0 ]; then
    echo "Error: Failed to transcribe $WAV_FILE."
    continue
  fi

  # Clean up WAV file (optional)
  echo "Cleaning up temporary WAV file..."
  rm "$WAV_FILE"

  echo "Transcription complete. SRT file saved for $INPUT_MP4."
done
