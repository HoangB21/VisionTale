import logging
import os
import time
import numpy as np
import subprocess
import threading
import asyncio
import gc
from typing import List, Dict, Optional, Tuple
from PIL import Image
from moviepy import ImageSequenceClip, AudioFileClip, CompositeAudioClip, AudioArrayClip
from server.utils.image_effect import ImageEffects

logger = logging.getLogger(__name__)


class VideoService:
    """Video Generation Service"""

    def __init__(self):
        self.default_settings = {
            'resolution': (1024, 1024),
            'fps': 20,
            'threads': max(2, os.cpu_count()//2),
            'use_cuda': True,
            'codec': 'h264_nvenc',
            'batch_size': max(2, os.cpu_count()//2),
            'fade_duration': 1,  # Fade in/out duration (seconds)
            'use_pan': True,
            # 50% of original image range for horizontal pan, 50% for vertical
            'pan_range': (0.5, 0.5),
        }
        self.stop_flag = threading.Event()
        self.cuda_available = self._check_hardware()
        # Progress tracking
        self.progress = 0
        self.total_segments = 0
        self.current_task = None
        self.task_lock = threading.Lock()

    def _check_hardware(self) -> bool:
        """Check hardware encoding support"""
        try:
            result = subprocess.run(
                ['ffmpeg', '-encoders'], capture_output=True, text=True)
            cuda_available = 'h264_nvenc' in result.stdout

            if not cuda_available:
                logger.warning("NVENC unavailable, switching to CPU mode")
                self.default_settings.update({
                    'use_cuda': False,
                })
            else:
                logger.info("NVENC available, using GPU mode")
            return cuda_available
        except Exception as e:
            logger.error("Hardware detection failed: %s", str(e))
            return False

    def _load_resources(self, subdir_path: str, resolution: Tuple[int, int]) -> tuple:
        """Load image and audio resources"""
        image_path = os.path.join(subdir_path, "image.png")
        audio_path = os.path.join(subdir_path, "audio.mp3")

        # Validate file existence
        for path in [image_path, audio_path]:
            if not os.path.exists(path):
                raise FileNotFoundError(f"File not found: {path}")
            if os.path.getsize(path) < 1024:
                raise ValueError(f"File too small: {path}")

        # Load image
        with Image.open(image_path) as img:
            if img.mode != 'RGB':
                img = img.convert('RGB')
            image = img.copy()
            # image = img.resize(resolution, Image.LANCZOS)

        # Load audio
        audio = AudioFileClip(audio_path)
        if audio.duration is None or audio.duration < 0.05:
            audio.close()  # Release file handle
            raise ValueError(
                f"Audio file duration too short or invalid: {audio_path}")

        return image, audio

    async def _process_segment(self, subdir: str, temp_dir: str, settings: Dict) -> Optional[Tuple[str, str]]:
        """Process a single video segment"""
        # Add subdir for uniqueness
        temp_file = os.path.join(temp_dir, f"vid_{subdir}_{os.getpid()}.mp4")
        temp_audio_path = os.path.join(
            os.path.dirname(temp_file),
            f"temp_audio_{subdir}_{os.getpid()}_{time.time_ns()}.m4a"
        )
        start_time = time.time()
        frames = []
        image = None
        audio = None

        try:
            # Load resources in thread
            loop = asyncio.get_running_loop()
            image, audio = await loop.run_in_executor(
                None,
                lambda: self._load_resources(os.path.join(
                    settings['chapter_path'], subdir), settings['resolution'])
            )

            duration = audio.duration
            total_frames = int(duration * settings['fps'])
            if total_frames == 0:
                raise ValueError(
                    f"Calculated total frames is 0, video duration too short. Subdir: {subdir}")

            # Generate frames in batch
            for i in range(total_frames):
                if self.stop_flag.is_set():
                    break
                # Process image in thread
                frame = await loop.run_in_executor(
                    None,
                    lambda: self._apply_effects(
                        image.copy(), i/settings['fps'], duration, settings, subdir)
                )
                frames.append(np.array(frame))
                frame.close()

            # Write video
            await loop.run_in_executor(
                None,
                lambda: self._write_temp_video(
                    frames, audio, temp_file, temp_audio_path, settings)
            )

            logger.info("Completed segment %s | Time taken: %.1fs | Size: %.1fMB",
                        subdir, time.time()-start_time, os.path.getsize(temp_file)/1024/1024)

            # Update progress
            with self.task_lock:
                self.progress += 1

            return temp_file, temp_audio_path

        finally:
            # Release memory resources only, no file deletion handling
            if image:
                image.close()
            if audio:
                audio.close()
            del frames
            gc.collect()

    def _write_temp_video(self, frames: list, audio: AudioFileClip, output_path: str, temp_audio_path: str, settings: Dict):
        """
        Safely write video segment
        Use temporary file to store, avoiding high memory usage
        """
        with ImageSequenceClip(frames, fps=settings['fps']) as video_clip:
            # Use .with_duration() to precisely and safely align audio-video duration
            # Elegantly handles duration mismatches by padding with silence or truncating
            final_audio = audio.with_duration(video_clip.duration)

            # Bind audio
            final_clip = video_clip.with_audio(final_audio)

            # Set encoding parameters
            ffmpeg_params = []
            if settings.get('use_cuda', False) and self.cuda_available:
                ffmpeg_params.extend(
                    ['-c:v', 'h264_nvenc', '-preset', 'medium'])
            else:
                ffmpeg_params.extend(
                    ['-c:v', 'libx264', '-preset', 'medium', '-crf', '23'])
            print("reach _write_temp_video ")
            # Write file
            final_clip.write_videofile(
                output_path,
                codec='h264_nvenc',
                audio_codec='aac',
                temp_audiofile=temp_audio_path,  # Explicitly specify temporary audio file path
                threads=settings.get('threads', 4),
                ffmpeg_params=ffmpeg_params,
                logger=None
            )

    async def generate_video(self, chapter_path: str, video_settings: Dict = None) -> str:
        """Main video generation process"""
        chapter_path = os.path.abspath(chapter_path)
        self.stop_flag.clear()
        final_settings = {**self.default_settings, **(video_settings or {})}

        final_settings['chapter_path'] = chapter_path
        output_path = os.path.join(chapter_path, "video.mp4")
        temp_video_files = []
        all_temp_files = []

        try:
            # Get list of segments to process
            subdirs = sorted([
                d for d in os.listdir(chapter_path)
                if os.path.isdir(os.path.join(chapter_path, d)) and d.isdigit()
            ], key=lambda x: int(x))

            if not subdirs:
                raise ValueError("No valid video segments")

            # Initialize progress information
            with self.task_lock:
                self.progress = 0
                self.total_segments = len(subdirs)
                self.current_task = f"{os.path.basename(chapter_path)}"

            logger.info("Found %d segments to process", len(subdirs))

            # Process segments in batches
            batch_size = final_settings.get('batch_size', 8)
            for i in range(0, len(subdirs), batch_size):
                batch = subdirs[i:i+batch_size]
                tasks = [self._process_segment(
                    subdir, chapter_path, final_settings) for subdir in batch]

                # Wait for current batch to complete, continue even if exceptions occur
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)

                # Collect results and handle exceptions
                for result in batch_results:
                    if isinstance(result, Exception):
                        logger.error(
                            "One video segment processing failed: %s", result)
                    elif result:
                        video_path, audio_path = result
                        temp_video_files.append(video_path)
                        all_temp_files.extend([video_path, audio_path])

                # Check for cancellation
                if self.stop_flag.is_set():
                    # Handle cleanup in finally block
                    logger.info("Video generation cancelled by user")
                    raise ValueError("Video generation cancelled by user")

            # Check if any segments failed
            if len(temp_video_files) != len(subdirs):
                raise ValueError(
                    "Some video segments failed to generate, cannot merge. Check logs.")

            # Merge temporary files
            if not temp_video_files:
                raise ValueError("No valid video segments generated")

            # Update progress status to merging phase
            with self.task_lock:
                self.current_task = "Merging videos"

            # Perform merging
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self._merge_videos(
                    temp_video_files, output_path, final_settings)
            )

            # Mark completion
            with self.task_lock:
                self.current_task = "Completed"
                self.progress = self.total_segments

            return result

        except Exception as e:
            logger.error("Video generation failed: %s", str(e))
            raise
        finally:
            # Clean up temporary files
            if all_temp_files:
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, self._cleanup_temp_files, all_temp_files)

    def _merge_videos(self, temp_files: List[str], output_path: str, settings: Dict) -> str:
        """Merge video segments"""
        concat_list = os.path.join(os.path.dirname(output_path), "concat.txt")
        # Write to a temporary file to avoid reading during merging
        # Create temporary filename by inserting marker before extension, preserving original extension
        root, ext = os.path.splitext(output_path)
        temp_output_path = f"{root}.tmp_{os.getpid()}{ext}"

        try:
            # Generate merge list
            with open(concat_list, 'w', encoding='utf-8') as f:
                for file in temp_files:
                    file_path = os.path.abspath(file).replace('\\', '/')
                    f.write(f"file '{file_path}'\n")

            # Build FFmpeg command
            cmd = [
                'ffmpeg',
                '-f', 'concat',
                '-safe', '0',
                '-i', concat_list,
                '-c', 'copy',
                '-movflags', '+faststart',
                '-y', temp_output_path
            ]
            if settings.get('use_cuda', False) and self.cuda_available:
                cmd[1:1] = ['-hwaccel', 'cuda', '-hwaccel_output_format', 'cuda']

            # Execute command
            subprocess.run(cmd, check=True, capture_output=True)

            # Atomically replace/rename file
            os.replace(temp_output_path, output_path)

            logger.info("Video merge successful: %s", output_path)
            return output_path

        except subprocess.CalledProcessError as e:
            # Decode error message
            import locale
            encoding = locale.getpreferredencoding()
            error_msg = e.stderr.decode(encoding, errors='replace')
            logger.error("Merge failed: %s", error_msg)
            raise
        finally:
            # Ensure all temporary files are cleaned up
            if os.path.exists(concat_list):
                os.remove(concat_list)
            if os.path.exists(temp_output_path):
                os.remove(temp_output_path)

    def _apply_effects(self, image: Image.Image, time_val: float,
                       duration: float, settings: Dict, subdir: str) -> Image.Image:
        """Apply video effects"""
        try:
            effect_params = {
                'output_size': settings.get('resolution', self.default_settings['resolution']),
                'fade_duration': settings.get('fade_duration', 1.0),
                'use_pan': settings.get('use_pan', True),
                'pan_range': settings.get('pan_range', (0.5, 0)),
                'segment_index': int(subdir) if subdir.isdigit() else 0
            }

            return ImageEffects.apply_effects(
                image, time_val, duration, effect_params
            )
        except Exception as e:
            logger.error("Effect processing failed: %s", str(e))
            raise

    def get_progress(self) -> Dict:
        """Get current video generation progress"""
        with self.task_lock:
            total = max(1, self.total_segments)
            percentage = int((self.progress / total) * 100)
            return {
                "progress": self.progress,
                "total": total,
                "percentage": percentage,
                "current_task": self.current_task
            }

    def cancel_generation(self) -> bool:
        """Cancel video generation"""
        self.stop_flag.set()
        return True

    def _cleanup_temp_files(self, files: List[str]):
        """Robustly cleans up temporary files, with retries for locked files."""
        for f_path in files:
            if not os.path.exists(f_path):
                continue

            attempts = 3
            for i in range(attempts):
                try:
                    os.remove(f_path)
                    logger.debug("Cleaned up: %s", f_path)
                    break  # Success
                except PermissionError as e:  # Specifically catch PermissionError for retries
                    if i < attempts - 1:
                        logger.warning(
                            "File locked, retrying in 0.5s: %s. Error: %s", f_path, e)
                        time.sleep(0.5)
                    else:
                        logger.error(
                            "Failed to delete file after multiple attempts: %s. Error: %s", f_path, e)
                except Exception as e:
                    logger.error(
                        "Unknown error while cleaning temporary file %s: %s", f_path, str(e))
                    break  # Don't retry on other errors
