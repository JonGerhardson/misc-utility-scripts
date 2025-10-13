#!/bin/bash

# This script finds video files, creates a montage of screenshots,
# and prepends metadata slides. 

# --- OS Detection & Configuration ---
OS_TYPE=$(uname)
if [[ "$OS_TYPE" == "Linux" ]]; then
    SHA_CMD="sha256sum"
    TEMP_DIR_BASE="/dev/shm"
    # Ensure /dev/shm exists and is writable, otherwise fall back to /tmp
    if [ ! -d "$TEMP_DIR_BASE" ] || [ ! -w "$TEMP_DIR_BASE" ]; then
        TEMP_DIR_BASE="/tmp"
    fi
elif [[ "$OS_TYPE" == "Darwin" ]]; then # Darwin is the kernel name for macOS
    # On macOS, coreutils must be installed via Homebrew for gsha256sum
    if ! command -v gsha256sum &> /dev/null; then
        echo "Error: 'gsha256sum' not found. Please install coreutils with Homebrew:" >&2
        echo "brew install coreutils" >&2
        exit 1
    fi
    SHA_CMD="gsha256sum"
    TEMP_DIR_BASE="/tmp"
else
    echo "Unsupported OS: $OS_TYPE" >&2
    exit 1
fi

# --- Default Flag Settings ---
NO_HASH=false
NO_META=false
INCLUDE_QR=false
HDD_MODE=false
DRY_RUN=false
TEST_MODE=false
SEARCH_DIR="."
INTERVAL=90
WIDTH=4
MAX_FRAMES=0 # 0 means no limit
STATIC_TEXT="YOUR CUSTOM TITLE HERE"
EXIFTOOL_TAGS="-FileSize -FileModifyDate -Duration -ImageSize -VideoFrameRate"
EXIFTOOL_FLAG_SET=false
SINGLE_FILE_PATH=""

# --- Help Function ---
show_help() {
cat << EOF
Usage: $(basename "$0") batch_caps.sh [OPTIONS] [DIRECTORY]

Finds all video files in [DIRECTORY] and creates a .jpg montage file of screen captures. Use --test or --single options before running on a full directory. 

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
EOF
}

# --- Argument Parsing ---
while [[ $# -gt 0 ]]; do
  key="$1"
  case $key in
    --no_hash|--no_meta|--qr|--hdd|--dry-run|--test)
      flag_name=$(echo "$key" | tr -d '-' | tr '[:lower:]' '[:upper:]')
      declare "$flag_name"=true
      shift # past argument
      ;;
    -s|--single|--interval|--static_text|--exiftool|--width|--max_frames)
      if [[ -z "$2" || "$2" == --* ]]; then
        echo "Error: Argument for $1 is missing." >&2; exit 1
      fi
      flag_name=$(echo "$key" | tr -d '-' | tr '[:lower:]' '[:upper:]')
      if [ "$flag_name" == "S" ] || [ "$flag_name" == "SINGLE" ]; then
        SINGLE_FILE_PATH="$2"
      elif [ "$flag_name" == "EXIFTOOL" ]; then
        EXIFTOOL_TAGS="$2"
        EXIFTOOL_FLAG_SET=true
      else
        if [[ "$key" == "--width" || "$key" == "--max_frames" ]] && ! [[ "$2" =~ ^[0-9]+$ ]]; then
            echo "Error: Argument for $1 must be a positive integer." >&2; exit 1
        fi
        declare "$flag_name"="$2"
      fi
      shift 2 # past argument and value
      ;;
    -h|--help)
      show_help
      exit 0
      ;;
    *)
      if [[ -d "$1" ]]; then
        SEARCH_DIR="$1"
        shift
      else
        echo "Error: Unrecognized option or invalid directory '$1'" >&2
        show_help
        exit 1
      fi
      ;;
  esac
done

# --- Pre-run Prompts and Warnings ---
if [ "$DRY_RUN" = false ]; then
    if [ "$STATIC_TEXT" == "YOUR CUSTOM TITLE HERE" ] && [ "$NO_META" = false ]; then
        echo "The static title for the info slide is set to the default."
        read -p "Enter new title or press Enter to keep default: " user_text
        if [ -n "$user_text" ]; then STATIC_TEXT="$user_text"; fi
    fi
    if [ "$EXIFTOOL_FLAG_SET" = true ]; then
        echo -e "\n⚠️  WARNING: You are using the --exiftool flag." >&2
        echo "This is an advanced feature. The script expects 5 metadata fields." >&2
        echo "Changing the number of tags will likely cause errors." >&2
        read -p "Do you want to continue? (y/N) " confirm
        if [[ ! "$confirm" =~ ^[Yy]$ ]]; then echo "Aborting."; exit 1; fi
    fi
fi

# --- Dependency Check ---
# Note: OS-specific sha256sum is checked in the OS detection block
for cmd in ffmpeg montage convert exiftool qrencode parallel file; do
  if ! command -v "$cmd" &> /dev/null; then
    echo "Error: Required command '$cmd' is not installed. Please install it to continue."
    exit 1
  fi
done

# --- Video Processing Function ---
process_video() {
  video="$1"
  videodir=$(dirname -- "$video")
  filename=$(basename -- "$video")
  filename_noext="${filename%.*}"
  montage_file="${videodir}/${filename_noext}_montage.jpg"

  if [ -f "$montage_file" ]; then
    echo "Montage for '$filename' already exists. Skipping."
    return
  fi

  ( # Subshell for safe processing
    cd "$videodir" || exit 1
    # Use the OS-specific temp directory base
    temp_dir=$(mktemp -d -p "$TEMP_DIR_BASE")
    trap 'rm -rf "$temp_dir"' EXIT
    echo "Processing '$filename'..."

    # 1. Extract Frames
    duration_seconds=$(exiftool -api LargeFileSupport=1 -n -s3 -Duration "$filename")
    if [ -z "$duration_seconds" ]; then echo "Warning: Could not get duration for '$filename'. Skipping."; exit 0; fi
    duration_integer=${duration_seconds%.*}
    echo "Extracting frames from '$filename' (Duration: ${duration_integer}s)..."

    frame_count=0
    for i in $(seq 0 "$INTERVAL" "$duration_integer"); do
        if [ "$MAX_FRAMES" -gt 0 ] && [ "$frame_count" -ge "$MAX_FRAMES" ]; then
            echo "Max frame limit of ${MAX_FRAMES} reached. Stopping capture."
            break
        fi
        frame_count=$((frame_count + 1))
        output_filename=$(printf "shot_%04d.png" "$frame_count")
        ffmpeg -nostdin -loglevel error -ss "$i" -i "$filename" -vframes 1 "$temp_dir/$output_filename"
    done

    montage_files=()
    # 2. Metadata and Slides (if not skipped)
    if [ "$NO_META" = false ]; then
        echo "Gathering metadata for '$filename'..."
        processing_date=$(date +"%Y-%m-%d %H:%M:%S %Z")
        IFS=$'\t' read -r file_size mod_date duration dimensions framerate < <(exiftool -api LargeFileSupport=1 -s3 -T $EXIFTOOL_TAGS "$filename")
        if [ -z "$dimensions" ]; then echo "ERROR: Failed to get dimensions for '$filename'. Skipping."; exit 1; fi

        screencap_interval="1 frame per ${INTERVAL} seconds"
        info_string="${STATIC_TEXT}\n---------------------------------\n"
        info_string+="Filename: ${filename}\nFile Size: ${file_size}\nModified: ${mod_date}\nProcessed: ${processing_date}\n"
        info_string+="Duration: ${duration}\nDimensions: ${dimensions}\nFrame Rate: ${framerate}\nCapture Interval: ${screencap_interval}"

        if [ "$NO_HASH" = false ]; then
            echo "Calculating SHA256 for '$filename'..."
            # Use the OS-specific SHA command
            sha_sum=$("$SHA_CMD" "$filename" | cut -d' ' -f1)
            info_string+="\n\nSHA256:\n${sha_sum:0:32}\n${sha_sum:32:32}"
        fi

        if [ "$INCLUDE_QR" = true ]; then
            qrencode -o "$temp_dir/qr_code_temp.png" "${info_string}"
            convert -size "${dimensions}" xc:black "$temp_dir/qr_code_temp.png" -gravity center -composite "$temp_dir/info_qr_slide.png"
            montage_files+=("$temp_dir/info_qr_slide.png")
        fi
        convert -background black -fill white -gravity center -pointsize 32 -size "${dimensions}" caption:"${info_string}" "$temp_dir/info_text_slide.png"
        montage_files+=("$temp_dir/info_text_slide.png")
    fi

    montage_files+=("$temp_dir"/shot_*.png)
    if [ "$TEST_MODE" = true ] && [ -z "$SINGLE_FILE_PATH" ]; then
        test_info="--TEST MODE--\n\nThis montage was created for a single file\nto test script functionality."
        convert -background darkred -fill white -gravity center -pointsize 48 -size "${dimensions}" caption:"${test_info}" "$temp_dir/test_slide.png"
        montage_files+=("$temp_dir/test_slide.png")
    fi

    # 3. Create Final Montage
    echo "Creating final montage for '$filename'..."
    montage "${montage_files[@]}" -tile "${WIDTH}x" -geometry +5+5 "${filename_noext}_montage.jpg"
  )
}
export -f process_video
export NO_HASH NO_META INCLUDE_QR TEST_MODE INTERVAL STATIC_TEXT EXIFTOOL_TAGS SINGLE_FILE_PATH WIDTH MAX_FRAMES SHA_CMD TEMP_DIR_BASE

# --- Main Execution ---
if [ -n "$SINGLE_FILE_PATH" ]; then
    # --- Single File Mode ---
    if [ ! -f "$SINGLE_FILE_PATH" ]; then echo "Error: File not found at '$SINGLE_FILE_PATH'" >&2; exit 1; fi
    echo "--- Single File Mode ---"
    if [ "$DRY_RUN" = true ]; then
        echo -e "-- Dry Run: Video to be processed --\n$SINGLE_FILE_PATH"
    else
        process_video "$SINGLE_FILE_PATH"
        echo "Montage created successfully!"
    fi
else
    # --- Directory Search Mode (using Bash v3 compatible loop) ---
    echo "Finding video files in '${SEARCH_DIR}'... (This may take a moment)"
    video_files=()
    while IFS= read -r -d '' file; do
      if [[ $(file --mime-type -b -- "$file") == video/* ]]; then
        video_files+=("$file")
      fi
    done < <(find "${SEARCH_DIR}" -type f -print0)

    if [ ${#video_files[@]} -eq 0 ]; then echo "No video files found."; exit 0; fi

    if [ "$DRY_RUN" = true ]; then
        echo "--- Dry Run: Videos to be processed ---"
        printf "%s\n" "${video_files[@]}"
        exit 0
    fi

    if [ "$TEST_MODE" = true ]; then
        echo "--- Test Mode: Processing only the first video ---"
        process_video "${video_files[0]}"
        echo "Test montage created successfully!"
        exit 0
    fi
    
    parallel_jobs=$([ "$HDD_MODE" = true ] && echo 1 || echo 0)
    echo "Starting $([ "$HDD_MODE" = true ] && echo "sequential (HDD)" || echo "parallel (SSD)") processing for ${#video_files[@]} videos..."
    printf "%s\0" "${video_files[@]}" | parallel -0 --eta -j "$parallel_jobs" process_video
    echo "All montages created successfully!"
fi
