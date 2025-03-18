import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import yt_dlp
from deep_translator import GoogleTranslator
import arabic_reshaper
from bidi.algorithm import get_display
from gtts import gTTS
import subprocess
import srt
from datetime import timedelta
import requests
from PIL import Image, ImageTk
import io
import threading
from langdetect import detect
import time
import json
import numpy as np
import soundfile as sf
import shutil

class DubbingApp:
    def __init__(self, master):
        self.master = master
        self.master.title("YouTube Video Dubber")
        self.master.geometry("1000x800")
        self.master.configure(bg="#f0f0f0")
        
        # Variables
        self.video_url = tk.StringVar()
        self.output_path = tk.StringVar()
        self.target_language = tk.StringVar(value="ar")
        self.source_language = tk.StringVar()
        self.progress_var = tk.DoubleVar()
        self.status_var = tk.StringVar()
        self.is_paused = False
        self.current_thread = None
        self.is_processing = False
        self.use_voice_clone = tk.BooleanVar(value=False)
        self.speaker_wav_path = tk.StringVar()
        self.tts_model = None
        
        # Configure styles
        self.setup_styles()
        
        # Create main container
        self.main_container = ttk.Frame(self.master, padding="10")
        self.main_container.pack(fill=tk.BOTH, expand=True)
        
        self._create_widgets()
        
        # Bind cleanup to window close
        self.master.protocol("WM_DELETE_WINDOW", self.cleanup)

    def setup_styles(self):
        style = ttk.Style()
        style.configure("Header.TLabel", font=("Arial", 16, "bold"))
        style.configure("Info.TLabel", font=("Arial", 10))
        style.configure("URL.TEntry", font=("Arial", 12))
        style.configure("Action.TButton", 
                       font=("Arial", 11, "bold"),
                       padding=5)
        style.configure("Status.TLabel", 
                       font=("Arial", 10),
                       foreground="#555555")
    
    def _create_widgets(self):
        # URL Section
        url_frame = ttk.LabelFrame(self.main_container, text="Video URL", padding="10")
        url_frame.pack(fill=tk.X, padx=5, pady=5)
        
        url_entry = ttk.Entry(url_frame, textvariable=self.video_url, style="URL.TEntry")
        url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        load_btn = ttk.Button(url_frame, text="Load Video Info",
                             command=self.start_load_info,
                             style="Action.TButton")
        load_btn.pack(side=tk.RIGHT)
        
        # Video Info Display
        self.info_frame = ttk.LabelFrame(self.main_container, text="Video Information", padding="10")
        self.info_frame.pack(fill=tk.BOTH, padx=5, pady=5, expand=True)
        
        # Create two columns for thumbnail and info
        info_columns = ttk.Frame(self.info_frame)
        info_columns.pack(fill=tk.BOTH, expand=True)
        
        # Thumbnail column
        thumb_frame = ttk.Frame(info_columns)
        thumb_frame.pack(side=tk.LEFT, padx=(0, 10))
        
        self.thumbnail_label = ttk.Label(thumb_frame)
        self.thumbnail_label.pack()
        
        # Info column
        text_frame = ttk.Frame(info_columns)
        text_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.title_label = ttk.Label(text_frame, style="Header.TLabel", wraplength=500)
        self.title_label.pack(fill=tk.X, pady=(0, 5))
        
        self.channel_label = ttk.Label(text_frame, style="Info.TLabel")
        self.channel_label.pack(fill=tk.X)
        
        self.desc_text = tk.Text(text_frame, height=4, wrap=tk.WORD)
        self.desc_text.pack(fill=tk.BOTH, expand=True)
        
        # Subtitle Options Frame
        sub_frame = ttk.LabelFrame(self.main_container, text="Subtitle Options", padding="10")
        sub_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Add subtitle file button
        self.sub_file_btn = ttk.Button(sub_frame, text="Load Subtitle File",
                                      command=self.browse_subtitle,
                                      style="Action.TButton")
        self.sub_file_btn.pack(pady=5)
        
        # Manual subtitle entry
        ttk.Label(sub_frame, text="Or enter subtitles manually:").pack(pady=(5, 0))
        self.sub_text = tk.Text(sub_frame, height=4, wrap=tk.WORD)
        self.sub_text.pack(fill=tk.X, pady=5)
        
        # Language Options
        lang_frame = ttk.LabelFrame(self.main_container, text="Languages", padding="10")
        lang_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Source language (auto-detected)
        ttk.Label(lang_frame, text="Source Language:").pack(side=tk.LEFT, padx=5)
        self.source_lang_label = ttk.Label(lang_frame, text="(Auto-detect)")
        self.source_lang_label.pack(side=tk.LEFT, padx=5)
        
        # Target language
        ttk.Label(lang_frame, text="Target Language:").pack(side=tk.LEFT, padx=5)
        target_langs = [("Arabic", "ar"), ("English", "en"), ("French", "fr"), 
                       ("German", "de"), ("Spanish", "es")]
        self.target_lang_combo = ttk.Combobox(lang_frame, textvariable=self.target_language,
                                             values=[code for _, code in target_langs],
                                             state="readonly", width=10)
        self.target_lang_combo.pack(side=tk.LEFT, padx=5)
        
        # Output Path
        out_frame = ttk.LabelFrame(self.main_container, text="Output Location", padding="10")
        out_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.out_entry = ttk.Entry(out_frame, textvariable=self.output_path)
        self.out_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        browse_btn = ttk.Button(out_frame, text="Browse",
                               command=self.browse_output,
                               style="Action.TButton")
        browse_btn.pack(side=tk.RIGHT)
        
        # Progress Section
        progress_frame = ttk.Frame(self.main_container)
        progress_frame.pack(fill=tk.X, padx=5, pady=10)
        
        self.progress_bar = ttk.Progressbar(progress_frame, mode="determinate",
                                          variable=self.progress_var)
        self.progress_bar.pack(fill=tk.X, side=tk.LEFT, expand=True)
        
        self.progress_label = ttk.Label(progress_frame, text="0%")
        self.progress_label.pack(side=tk.RIGHT, padx=5)
        
        # Control Buttons
        btn_frame = ttk.Frame(self.main_container)
        btn_frame.pack(pady=10)
        
        self.start_button = ttk.Button(btn_frame, text="Start Dubbing",
                                     command=self.start_dubbing,
                                     style="Action.TButton")
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        self.pause_button = ttk.Button(btn_frame, text="Pause",
                                     command=self.toggle_pause,
                                     state="disabled",
                                     style="Action.TButton")
        self.pause_button.pack(side=tk.LEFT, padx=5)
        
        # Status Label
        self.status_label = ttk.Label(self.main_container, 
                                    textvariable=self.status_var,
                                    style="Status.TLabel")
        self.status_label.pack(pady=5)

        # Voice Cloning Options
        voice_frame = ttk.LabelFrame(self.main_container, text="Voice Cloning Options", padding="10")
        voice_frame.pack(fill=tk.X, padx=5, pady=5)

        self.use_clone_check = ttk.Checkbutton(voice_frame, text="Use Voice Cloning",
                                              variable=self.use_voice_clone,
                                              command=self.toggle_voice_clone)
        self.use_clone_check.pack(side=tk.LEFT, padx=5)

        self.speaker_btn = ttk.Button(voice_frame, text="Select Speaker Voice",
                                    command=self.browse_speaker_voice,
                                    state="disabled")
        self.speaker_btn.pack(side=tk.LEFT, padx=5)

        self.speaker_label = ttk.Label(voice_frame, text="No file selected")
        self.speaker_label.pack(side=tk.LEFT, padx=5)

    def start_load_info(self):
        """Start loading video info in a separate thread"""
        if not self.is_processing:
            self.is_processing = True
            self.update_ui_state(loading=True)
            thread = threading.Thread(target=self.load_video_info)
            thread.daemon = True
            thread.start()

    def update_ui_state(self, loading=False):
        """Update UI elements based on processing state"""
        state = "disabled" if loading else "normal"
        if hasattr(self, 'start_button'):
            self.start_button.configure(state=state)
        # Only disable pause button if we're not in dubbing process
        if hasattr(self, 'pause_button') and not self.current_thread:
            self.pause_button.configure(state="disabled")

    def update_progress(self, value):
        """Update progress bar and percentage label"""
        self.progress_var.set(value)
        if hasattr(self, 'progress_label'):
            self.progress_label.configure(text=f"{int(value)}%")
        self.master.update_idletasks()  # Update UI without blocking

    def load_video_info(self):
        """Load video information in a separate thread"""
        try:
            url = self.video_url.get().strip()
            if not url:
                self.handle_error("Please enter a video URL")
                return

            self.update_status("جاري تحميل معلومات الفيديو...")
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': True,
                'writesubtitles': True,
                'skip_download': True
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                # Use master.after to update UI from the main thread
                self.master.after(0, lambda: self.update_video_info(info))
                
        except Exception as e:
            self.master.after(0, lambda: self.handle_error(str(e)))
        finally:
            self.is_processing = False
            self.master.after(0, lambda: self.update_ui_state(loading=False))

    def update_video_info(self, info):
        """Update video information in the UI (called from main thread)"""
        self.title_label.config(text=info.get('title', 'N/A'))
        self.channel_label.config(text=f"Channel: {info.get('channel', 'N/A')}")
        self.desc_text.delete(1.0, tk.END)
        self.desc_text.insert(tk.END, info.get('description', 'N/A'))
        
        # Try to detect language from title and description
        text_for_detection = f"{info.get('title', '')} {info.get('description', '')}"
        detected_lang = self.detect_language(text_for_detection)
        if detected_lang:
            self.source_language.set(detected_lang)
            self.source_lang_label.config(text=f"({detected_lang})")
        
        # Load thumbnail
        thumbnail_url = info.get('thumbnail')
        if thumbnail_url:
            try:
                response = requests.get(thumbnail_url)
                img = Image.open(io.BytesIO(response.content))
                img = img.resize((200, 150), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                self.thumbnail_label.configure(image=photo)
                self.thumbnail_label.image = photo
            except Exception as e:
                print(f"Error loading thumbnail: {e}")
        
        self.update_status("تم تحميل معلومات الفيديو بنجاح")
        self.update_progress(10)

    def toggle_pause(self):
        """Toggle pause state of the dubbing process"""
        self.is_paused = not self.is_paused
        if self.is_paused:
            self.pause_button.configure(text="Resume")
            self.update_status("عملية الدبلجة متوقفة مؤقتاً")
        else:
            self.pause_button.configure(text="Pause")
            self.update_status("جاري استئناف عملية الدبلجة...")

    def detect_language(self, text):
        """Detect the language of the given text"""
        try:
            return detect(text)
        except:
            return None

    def browse_output(self):
        directory = filedialog.askdirectory()
        if directory:
            self.output_path.set(directory)

    def browse_subtitle(self):
        file_path = filedialog.askopenfilename(filetypes=[("Subtitle files", "*.srt")])
        if file_path:
            with open(file_path, 'r', encoding='utf-8') as f:
                subtitle_content = f.read()
            self.sub_text.delete(1.0, tk.END)
            self.sub_text.insert(tk.END, subtitle_content)

    def download_video_with_info(self, url, output_path, subtitle_lang=None):
        ydl_opts = {
            'outtmpl': os.path.join(output_path, '%(title)s-%(id)s.%(ext)s'),
            'format': 'bestvideo+bestaudio/best',
            'writesubtitles': True,
            'subtitleslangs': [subtitle_lang] if subtitle_lang else [],
            'subtitlesformat': 'srt',
            'merge_output_format': 'mp4',
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                video_path = ydl.prepare_filename(info)
                subtitle_path = None
                
                # Look for the subtitle file
                if subtitle_lang:
                    subtitle_name = f"{os.path.splitext(video_path)[0]}.{subtitle_lang}.srt"
                    if os.path.exists(subtitle_name):
                        subtitle_path = subtitle_name
                
                return {
                    'video_path': video_path,
                    'audio_path': video_path,  # Same as video path since we merge them
                    'subtitle_path': subtitle_path,
                    'video_info': info
                }
        except Exception as e:
            raise Exception(f"Error downloading video: {str(e)}")

    def parse_subtitle_text(self, subtitle_text):
        """Parse subtitle text to create SRT-like structure"""
        try:
            # Split text into lines
            lines = subtitle_text.strip().split('\n')
            subtitles = []
            current_time = 0
            
            for i, line in enumerate(lines, 1):
                if line.strip():  # Skip empty lines
                    # Create artificial timing (3 seconds per line)
                    start_time = timedelta(seconds=current_time)
                    end_time = timedelta(seconds=current_time + 3)
                    subtitles.append((start_time, end_time, line.strip()))
                    current_time += 3
            
            return subtitles
        except Exception as e:
            raise Exception(f"Error parsing manual subtitles: {str(e)}")

    def get_subtitles(self):
        """Get subtitles from either manual input or file"""
        # Check manual input first
        manual_subs = self.sub_text.get("1.0", tk.END).strip()
        if manual_subs:
            return self.parse_subtitle_text(manual_subs)
            
        # If no manual input, try to get from downloaded subtitles
        if hasattr(self, 'current_subtitle_path') and self.current_subtitle_path:
            return self.parse_subtitle_file(self.current_subtitle_path)
            
        raise Exception("No subtitles available. Please either enter subtitles manually or ensure the video has subtitles.")

    def parse_subtitle_file(self, subtitle_path):
        """Parse SRT file into list of (start, end, text) tuples"""
        try:
            with open(subtitle_path, 'r', encoding='utf-8') as f:
                subtitle_content = f.read()
                
            parsed = list(srt.parse(subtitle_content))
            return [(sub.start, sub.end, sub.content) for sub in parsed]
        except Exception as e:
            raise Exception(f"Error parsing subtitle file: {str(e)}")

    def synchronize_audio(self, original_audio_path, dubbed_segments, subtitle_info):
        """
        Modified version that uses ffmpeg directly for audio processing
        """
        try:
            # Create a temporary directory for audio segments
            temp_dir = "temp_audio_segments"
            os.makedirs(temp_dir, exist_ok=True)
            
            # Save each dubbed segment as a separate file
            segment_files = []
            for i, ((start_time, end_time, _), segment) in enumerate(zip(subtitle_info, dubbed_segments)):
                segment_path = os.path.join(temp_dir, f"segment_{i}.wav")
                segment.export(segment_path, format="wav")
                segment_files.append((segment_path, start_time, end_time))
            
            # Create a file list for ffmpeg
            concat_file = "concat.txt"
            with open(concat_file, "w") as f:
                for segment_path, _, _ in segment_files:
                    f.write(f"file '{segment_path}'\n")
            
            # Concatenate all segments using ffmpeg
            output_path = "final_audio.wav"
            subprocess.run([
                'ffmpeg', '-y', '-f', 'concat', '-safe', '0',
                '-i', concat_file, '-c', 'copy', output_path
            ], check=True)
            
            # Clean up temporary files
            os.remove(concat_file)
            for segment_path, _, _ in segment_files:
                os.remove(segment_path)
            os.rmdir(temp_dir)
            
            return output_path
            
        except Exception as e:
            raise Exception(f"Error synchronizing audio: {str(e)}")

    def start_dubbing(self):
        try:
            url = self.video_url.get().strip()
            output_dir = self.output_path.get().strip()
            target_lang = self.target_language.get().strip()
            
            if not all([url, output_dir]):
                self.handle_error("Please fill in all required fields")
                return
            
            # Enable pause button and disable start button
            self.pause_button.configure(state="normal")
            self.start_button.configure(state="disabled")
            
            # Reset pause state
            self.is_paused = False
            
            # Start the dubbing process in a separate thread
            self.current_thread = threading.Thread(target=self.dubbing_process)
            self.current_thread.start()
            
        except Exception as e:
            self.handle_error(str(e))

    def dubbing_process(self):
        """The main dubbing process."""
        try:
            video_url = self.video_url.get().strip()
            output_dir = self.output_path.get().strip()
            target_lang = self.target_language.get().strip()
            source_lang = self.source_language.get().strip()
            
            self.update_status("جاري تنزيل الفيديو...")
            download_result = self.download_video_with_info(video_url, output_dir, source_lang)
            self.current_subtitle_path = download_result['subtitle_path']
            
            self.update_progress(30)
            self.update_status("جاري تحليل الترجمة...")
            
            try:
                subtitle_info = self.get_subtitles()
            except Exception as e:
                self.handle_error(f"Error with subtitles: {str(e)}")
                return
            
            if not subtitle_info:
                self.handle_error("لم يتم العثور على ترجمة")
                return
            
            self.update_progress(40)
            self.update_status("جاري ترجمة النصوص...")
            translator = GoogleTranslator(source=source_lang, target=target_lang)
            translated_texts = [translator.translate(text) for _, _, text in subtitle_info]
            
            self.update_progress(50)
            self.update_status("جاري تحويل النص إلى كلام...")
            
            # Create temp directory for segments
            temp_dir = "temp_audio_segments"
            os.makedirs(temp_dir, exist_ok=True)
            
            wav_files = []
            total_segments = len(translated_texts)
            
            for i, text in enumerate(translated_texts, 1):
                while self.is_paused:
                    time.sleep(0.1)
                    continue

                try:
                    self.update_status(f"Converting text to speech ({i}/{total_segments})...")
                    temp_mp3 = os.path.join(temp_dir, f"segment_{i}.mp3")
                    temp_wav = os.path.join(temp_dir, f"segment_{i}.wav")
                    
                    # Generate speech using gTTS
                    tts = gTTS(text=text, lang=target_lang, slow=False)
                    tts.save(temp_mp3)
                    
                    # Convert MP3 to WAV using ffmpeg
                    subprocess.run([
                        'ffmpeg', '-y', '-i', temp_mp3,
                        '-acodec', 'pcm_s16le',
                        '-ar', '44100',
                        temp_wav
                    ], check=True)
                    
                    wav_files.append(temp_wav)
                    os.remove(temp_mp3)  # Clean up MP3 file
                    
                    self.update_progress(50 + (20 * i / total_segments))

                except Exception as e:
                    self.handle_error(f"Error in speech generation: {str(e)}")
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    return

            self.update_progress(70)
            self.update_status("جاري مزامنة الصوت...")

            try:
                final_audio_path = "temp_final_audio.wav"
                
                # Read the first file to get parameters
                data, samplerate = sf.read(wav_files[0])
                combined_data = data
                
                # Concatenate the rest of the files
                for wav_file in wav_files[1:]:
                    data, _ = sf.read(wav_file)
                    combined_data = np.concatenate([combined_data, data])
                
                # Write the combined audio
                sf.write(final_audio_path, combined_data, samplerate)

                self.update_progress(80)
                self.update_status("جاري إنشاء الفيديو النهائي...")

                # Merge video with dubbed audio
                output_video = os.path.join(output_dir, "dubbed_video.mp4")
                subprocess.run([
                    'ffmpeg', '-y',
                    '-i', download_result['video_path'],
                    '-i', final_audio_path,
                    '-c:v', 'copy',
                    '-c:a', 'aac',
                    output_video
                ], check=True)

                # Clean up
                os.remove(final_audio_path)
                shutil.rmtree(temp_dir, ignore_errors=True)

                self.update_progress(100)
                self.update_status("!تمت عملية الدبلجة بنجاح")
                messagebox.showinfo("نجاح", "!تمت عملية الدبلجة بنجاح")

            except Exception as e:
                self.handle_error(f"Error in audio processing: {str(e)}")
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
                if os.path.exists(final_audio_path):
                    os.remove(final_audio_path)

        except Exception as e:
            self.handle_error(str(e))
        finally:
            self.pause_button.configure(state="disabled")
            self.start_button.configure(state="normal")
            self.current_thread = None

    def update_status(self, message):
        """Update the status message in the UI."""
        if isinstance(message, str):
            message = arabic_reshaper.reshape(message)
            message = get_display(message)
        self.status_var.set(message)
        self.master.update()

    def handle_error(self, message):
        """Handle and display error messages."""
        self.update_status(f"Error: {message}")
        messagebox.showerror("Error", message)

    def toggle_voice_clone(self):
        """Enable/disable voice cloning related widgets and load/unload model"""
        if self.use_voice_clone.get():
            self.speaker_btn.configure(state="normal")
            self.load_tts_model()
        else:
            self.speaker_btn.configure(state="disabled")
            if self.tts_model is not None:
                del self.tts_model
                self.tts_model = None

    def load_tts_model(self):
        """Load the TTS model for voice cloning"""
        try:
            self.update_status("Loading TTS model...")
            from TTS.api import TTS
            
            # Get path to best model for voice cloning
            model_name = TTS.list_models()[0]  # Get first available model
            self.tts_model = TTS(model_name)
            
            self.update_status("TTS model loaded successfully")
        except Exception as e:
            self.handle_error(f"Error loading TTS model: {str(e)}")
            self.use_voice_clone.set(False)
            self.speaker_btn.configure(state="disabled")

    def browse_speaker_voice(self):
        """Browse for speaker voice WAV file"""
        file_path = filedialog.askopenfilename(
            filetypes=[("WAV files", "*.wav")]
        )
        if file_path:
            self.speaker_wav_path.set(file_path)
            self.speaker_label.configure(text=os.path.basename(file_path))

    def cleanup(self):
        """Clean up resources before closing"""
        if self.tts_model is not None:
            del self.tts_model
        self.master.destroy()

def main():
    root = tk.Tk()
    app = DubbingApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()