import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import yt_dlp
from deep_translator import GoogleTranslator
import arabic_reshaper
from bidi.algorithm import get_display
from gtts import gTTS
import wave
import subprocess
import srt
from datetime import timedelta
import requests
from PIL import Image, ImageTk
import io
import threading
from langdetect import detect
import time

class DubbingApp:
    def __init__(self, master):
        self.master = master
        self.master.title("YouTube Video Dubber")
        self.master.geometry("800x600")
        
        # Variables
        self.video_url = tk.StringVar()
        self.output_path = tk.StringVar()
        self.target_language = tk.StringVar(value="ar")  # Default to Arabic
        self.source_language = tk.StringVar()  # Will be detected automatically
        self.progress_var = tk.DoubleVar()
        self.status_var = tk.StringVar()
        self.is_paused = False
        self.current_thread = None
        self.is_processing = False
        
        self._create_widgets()
        
    def _create_widgets(self):
        # Main container to hold all frames
        main_container = ttk.Frame(self.master)
        main_container.pack(fill="both", expand=True, padx=5, pady=5)
        
        # URL Input
        url_frame = ttk.LabelFrame(main_container, text="Video URL", padding="5")
        url_frame.pack(fill="x", padx=5, pady=5)
        
        ttk.Entry(url_frame, textvariable=self.video_url).pack(fill="x", expand=True, side="left", padx=5)
        ttk.Button(url_frame, text="Load Info", command=self.start_load_info).pack(side="right", padx=5)

        # Output Path
        path_frame = ttk.LabelFrame(main_container, text="Output Location", padding="5")
        path_frame.pack(fill="x", padx=5, pady=5)
        
        ttk.Entry(path_frame, textvariable=self.output_path).pack(fill="x", expand=True, side="left", padx=5)
        ttk.Button(path_frame, text="Browse", command=self.browse_output).pack(side="right", padx=5)

        # Language Selection
        lang_frame = ttk.LabelFrame(main_container, text="Languages", padding="5")
        lang_frame.pack(fill="x", padx=5, pady=5)
        
        ttk.Label(lang_frame, text="From:").pack(side="left", padx=5)
        self.source_lang_label = ttk.Label(lang_frame, text="(Auto-detect)")
        self.source_lang_label.pack(side="left", padx=5)
        ttk.Label(lang_frame, text="To:").pack(side="left", padx=5)
        ttk.Entry(lang_frame, textvariable=self.target_language, width=5).pack(side="left", padx=5)

        # Video Info Display
        self.info_frame = ttk.LabelFrame(main_container, text="Video Information", padding="5")
        self.info_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Add scrollbar to info text
        info_text_frame = ttk.Frame(self.info_frame)
        info_text_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        info_scrollbar = ttk.Scrollbar(info_text_frame)
        info_scrollbar.pack(side="right", fill="y")
        
        self.info_text = tk.Text(info_text_frame, height=5, wrap="word", yscrollcommand=info_scrollbar.set)
        self.info_text.pack(fill="both", expand=True)
        info_scrollbar.config(command=self.info_text.yview)
        
        self.thumbnail_label = ttk.Label(self.info_frame)
        self.thumbnail_label.pack(padx=5, pady=5)

        # Progress and Status Frame
        progress_frame = ttk.Frame(main_container)
        progress_frame.pack(fill="x", padx=5, pady=5)
        
        # Progress bar with percentage label
        progress_bar_frame = ttk.Frame(progress_frame)
        progress_bar_frame.pack(fill="x")
        
        self.progress_bar = ttk.Progressbar(
            progress_bar_frame, 
            variable=self.progress_var,
            maximum=100,
            length=300
        )
        self.progress_bar.pack(side="left", fill="x", expand=True, padx=(5, 2))
        
        self.progress_label = ttk.Label(progress_bar_frame, text="0%")
        self.progress_label.pack(side="left", padx=(2, 5))
        
        # Status label
        self.status_label = ttk.Label(
            progress_frame, 
            textvariable=self.status_var,
            wraplength=780  # Allow text to wrap
        )
        self.status_label.pack(fill="x", padx=5, pady=2)

        # Control Buttons Frame
        control_frame = ttk.Frame(main_container)
        control_frame.pack(pady=10)
        
        # Start Button
        self.start_button = ttk.Button(
            control_frame,
            text="Start Dubbing",
            command=self.start_dubbing,
            style='Action.TButton'
        )
        self.start_button.pack(side="left", padx=5)

        # Pause Button
        self.pause_button = ttk.Button(
            control_frame,
            text="Pause",
            command=self.toggle_pause,
            state="disabled"
        )
        self.pause_button.pack(side="left", padx=5)
        
        # Configure style for buttons
        style = ttk.Style()
        style.configure('Action.TButton', font=('Arial', 10, 'bold'))

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
        self.info_text.delete(1.0, tk.END)
        self.info_text.insert(tk.END, f"Title: {info.get('title', 'N/A')}\n")
        self.info_text.insert(tk.END, f"Channel: {info.get('channel', 'N/A')}\n")
        self.info_text.insert(tk.END, f"Duration: {info.get('duration_string', 'N/A')}\n")
        
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

    def parse_subtitle_file(self, subtitle_path):
        try:
            with open(subtitle_path, 'r', encoding='utf-8') as f:
                subtitle_content = f.read()
                
            parsed = list(srt.parse(subtitle_content))
            return [(sub.start, sub.end, sub.content) for sub in parsed]
        except Exception as e:
            raise Exception(f"Error parsing subtitles: {str(e)}")

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
        try:
            url = self.video_url.get().strip()
            output_dir = self.output_path.get().strip()
            target_lang = self.target_language.get().strip()
            source_lang = self.source_language.get().strip()
            
            self.update_status("جاري تنزيل الفيديو والصوت والترجمة...")
            download_result = self.download_video_with_info(url, output_dir, source_lang)
            
            if not download_result['subtitle_path']:
                self.handle_error("لم يتم العثور على ملف ترجمة")
                return
            
            self.update_progress(30)
            self.update_status("جاري تحليل ملف الترجمة...")
            subtitle_info = self.parse_subtitle_file(download_result['subtitle_path'])
            
            self.update_progress(40)
            self.update_status("جاري ترجمة النصوص...")
            translator = GoogleTranslator(source=source_lang, target=target_lang)
            translated_texts = [translator.translate(text) for _, _, text in subtitle_info]
            
            self.update_progress(50)
            self.update_status("جاري تحويل النص إلى كلام...")
            
            dubbed_segments = []
            total_segments = len(translated_texts)
            
            for i, text in enumerate(translated_texts, 1):
                # Generate speech for each translated segment using gTTS
                temp_wav = f"temp_speech_{i}.mp3"
                tts = gTTS(text=text, lang=target_lang, slow=False)
                tts.save(temp_wav)
                
                # Convert MP3 to WAV using ffmpeg
                output_wav = f"temp_speech_{i}.wav"
                subprocess.run([
                    'ffmpeg', '-y', '-i', temp_wav,
                    '-acodec', 'pcm_s16le',
                    '-ar', '44100',
                    output_wav
                ], check=True)
                
                # Read the WAV file
                with wave.open(output_wav, 'rb') as wf:
                    frames = wf.readframes(wf.getnframes())
                    dubbed_segments.append({
                        'audio': frames,
                        'params': wf.getparams()
                    })
                
                # Clean up temporary files
                os.remove(temp_wav)
                os.remove(output_wav)
                
                self.update_progress(50 + (20 * i / total_segments))
                
                while self.is_paused:
                    time.sleep(0.1)  # Small delay to prevent CPU hogging
                    continue
            
            self.update_progress(70)
            self.update_status("جاري مزامنة الصوت...")
            final_audio_path = self.synchronize_audio(
                download_result['video_path'],
                dubbed_segments,
                subtitle_info
            )
            
            self.update_progress(80)
            self.update_status("جاري إنشاء الفيديو النهائي...")
            
            # Merge video with dubbed audio using ffmpeg directly
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
            
            self.update_progress(100)
            self.update_status("!تمت عملية الدبلجة بنجاح")
            messagebox.showinfo("نجاح", "!تمت عملية الدبلجة بنجاح")
            
            self.pause_button.configure(state="disabled")
            self.start_button.configure(state="normal")
            
        except Exception as e:
            self.handle_error(str(e))
            self.pause_button.configure(state="disabled")
            self.start_button.configure(state="normal")

    def update_status(self, message):
        if isinstance(message, str):
            message = arabic_reshaper.reshape(message)
            message = get_display(message)
        self.status_var.set(message)
        self.master.update()

    def handle_error(self, message):
        self.update_status(f"Error: {message}")
        messagebox.showerror("Error", message)

def main():
    root = tk.Tk()
    app = DubbingApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()