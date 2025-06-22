import os
import json
import sys
from mutagen.mp3 import MP3
from mutagen.id3 import ID3

if sys.platform == 'win32':
    import ctypes

CACHE_FILE = 'song_cache.json'

def parse_osu_file(filepath):
    metadata = {}
    in_events_section = False
    in_timing_section = False
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()

                if line == '[Events]':
                    in_events_section = True
                    in_timing_section = False
                    continue
                if line == '[TimingPoints]':
                    in_timing_section = True
                    in_events_section = False
                    continue
                if line.startswith('['):
                    in_events_section = False
                    in_timing_section = False
                    continue

                if line.startswith('AudioFilename:'):
                    metadata['AudioFilename'] = line.split(':', 1)[1].strip()
                elif line.startswith('Title:'):
                    metadata['Title'] = line.split(':', 1)[1].strip()
                elif line.startswith('Artist:'):
                    metadata['Artist'] = line.split(':', 1)[1].strip()
                elif in_events_section and (line.startswith('0,0,') or line.startswith('Video,') or line.startswith('1,0,')):
                    try:
                        parts = line.split(',')
                        filename = parts[2].strip('"')
                        if filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                             metadata['Background'] = filename
                    except IndexError:
                        continue
                elif in_timing_section and 'BPM' not in metadata:
                    try:
                        parts = line.split(',')
                        if len(parts) >= 8:
                            beat_length_str = parts[1]
                            uninherited = parts[6]
                            if uninherited == '1' and float(beat_length_str) > 0:
                                bpm = 60000 / float(beat_length_str)
                                metadata['BPM'] = round(bpm)
                    except (ValueError, IndexError, ZeroDivisionError):
                        continue
                
                if 'AudioFilename' in metadata and 'Title' in metadata and 'Artist' in metadata and 'Background' in metadata and 'BPM' in metadata:
                    break
    except Exception as e:
        print(f"Error parsing file {filepath}: {e}")
        return None
    return metadata

def scan_songs(songs_dir):
    cache_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', CACHE_FILE)
    
    # --- Проверка кэша ---
    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            cached_mtime = cache_data.get('mtime')
            current_mtime = os.path.getmtime(songs_dir)
            if cached_mtime == current_mtime:
                library = cache_data.get('library', [])
                if library:
                    print("Loading songs from cache.")
                    return library
        except (json.JSONDecodeError, KeyError, TypeError, FileNotFoundError) as e:
            print(f"Cache is invalid or not found, performing a full scan. Error: {e}")

    # --- Полное сканирование ---
    print("Performing a full scan of the songs directory...")
    song_library = []
    if not songs_dir:
        return song_library

    for root, dirs, files in os.walk(songs_dir):
        osu_files = [f for f in files if f.endswith('.osu')]
        if not osu_files:
            continue
            
        for file in osu_files:
            osu_filepath = os.path.join(root, file)
            metadata = parse_osu_file(osu_filepath)
            if metadata and 'AudioFilename' in metadata:
                audio_path = os.path.join(root, metadata['AudioFilename'])
                background_path = None
                if 'Background' in metadata:
                    bg_file = os.path.join(root, metadata['Background'])
                    if os.path.exists(bg_file):
                        background_path = bg_file

                if os.path.exists(audio_path):
                    song_info = {
                        'artist': metadata.get('Artist', 'Unknown Artist'),
                        'title': metadata.get('Title', 'Unknown Title'),
                        'audio_path': audio_path,
                        'background_path': background_path,
                        'bpm': metadata.get('BPM'),
                        'display_text': f"{metadata.get('Artist', 'Unknown Artist')} - {metadata.get('Title', 'Unknown Title')}"
                    }
                    song_library.append(song_info)
                # Только один .osu на папку
                break 

    song_library = sorted(song_library, key=lambda x: x['display_text'])

    # --- Сохранение в кэш ---
    try:
        current_mtime = os.path.getmtime(songs_dir)
        cache_data = {'mtime': current_mtime, 'library': song_library}
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=4)

        # --- Сделать файл кэша скрытым в Windows ---
        if sys.platform == 'win32':
            FILE_ATTRIBUTE_HIDDEN = 0x02
            ctypes.windll.kernel32.SetFileAttributesW(cache_path, FILE_ATTRIBUTE_HIDDEN)

    except Exception as e:
        print(f"Error saving or hiding cache file: {e}")

    print(f"Scan complete. Found {len(song_library)} songs.")
    return song_library

def format_time(ms):
    if ms is None:
        return "00:00"
    seconds = int((ms / 1000) % 60)
    minutes = int((ms / (1000 * 60)) % 60)
    return f'{minutes:02d}:{seconds:02d}'
