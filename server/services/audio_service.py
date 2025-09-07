import os
import asyncio
from typing import Dict, List
from datetime import datetime
import signal
import edge_tts
import traceback
from .base_service import SingletonService
import logging

logger = logging.getLogger(__name__)


class AudioService(SingletonService):
    def _initialize(self):
        self.tasks: Dict[str, Dict] = {}  # Store ongoing tasks
        # Disable proxy
        os.environ['no_proxy'] = '*'
        # Set up signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle interrupt signals"""
        print("\nCleaning up audio generation tasks...")
        # Mark all tasks as cancelled
        for task_id in self.tasks:
            self.tasks[task_id]['cancelled'] = True
        print("Audio generation tasks cancelled")

    async def generate_audio(self, prompts: List[str], output_dirs: List[str],
                             voice: str = "vi-VN-HoaiMyNeural",
                             rate: str = "+0%") -> Dict:
        """Generate audio files"""
        if len(prompts) != len(output_dirs):
            raise ValueError("Length of prompts and output_dirs must be equal")

        logger.info(f"Using voice: {voice}")
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        task_id = f'audio_{timestamp}'

        # Initialize task information
        self.tasks[task_id] = {
            'total': len(prompts),
            'completed': 0,
            'errors': [],
            'cancelled': False,
            'status': 'running'
        }

        # Create async task
        asyncio.create_task(self._process_audio_batch(
            task_id, prompts, output_dirs, voice, rate
        ))

        return {
            'task_id': task_id,
            'total': len(prompts),
            'status': 'running'
        }

    async def _process_audio_batch(self, task_id: str, prompts: List[str],
                                   output_dirs: List[str], voice: str, rate: str):
        """Process batch audio generation task"""
        task = self.tasks[task_id]

        async def generate_single_audio(i: int, text: str, output_dir: str) -> bool:
            """Generate single audio file"""
            if task['cancelled']:
                return False

            output_path = os.path.join(output_dir, 'audio.mp3')

            try:
                os.makedirs(output_dir, exist_ok=True)
                if os.path.exists(output_path):
                    os.remove(output_path)

                communicate = edge_tts.Communicate(text, voice, rate=rate)
                async for chunk in communicate.stream():
                    if task['cancelled']:
                        if os.path.exists(output_path):
                            os.remove(output_path)
                        return False

                    if chunk["type"] == "audio":
                        with open(output_path, "ab") as f:
                            f.write(chunk["data"])

                if not task['cancelled']:
                    task['completed'] += 1
                return True

            except Exception as e:
                error_msg = f"Error generating audio at index {i}: {str(e)}"
                print(error_msg)
                traceback.print_exc()
                task['errors'].append(error_msg)
                if os.path.exists(output_path):
                    os.remove(output_path)
                return False

        try:
            # Generate all audio in parallel
            tasks = [
                generate_single_audio(i, text, output_dir)
                for i, (text, output_dir) in enumerate(zip(prompts, output_dirs))
            ]
            await asyncio.gather(*tasks)

            # Update final status
            if task['cancelled']:
                task['status'] = 'cancelled'
                # Clean up incomplete files
                for output_dir in output_dirs[task['completed']:]:
                    output_path = os.path.join(output_dir, 'audio.mp3')
                    if os.path.exists(output_path):
                        os.remove(output_path)
            elif task['errors']:
                task['status'] = 'error'
            else:
                task['status'] = 'completed'
        except asyncio.CancelledError:
            task['cancelled'] = True
            task['status'] = 'cancelled'
            # Clean up all files
            for output_dir in output_dirs:
                output_path = os.path.join(output_dir, 'audio.mp3')
                if os.path.exists(output_path):
                    os.remove(output_path)

    def get_generation_progress(self, task_id: str) -> Dict:
        """Get generation task progress"""
        if task_id not in self.tasks:
            return {
                'status': 'not_found',
                'current': 0,
                'total': 0,
                'errors': []
            }

        task = self.tasks[task_id]
        return {
            'status': task['status'],
            'current': task['completed'],
            'total': task['total'],
            'errors': task['errors']
        }

    def cancel_generation(self, task_id: str) -> bool:
        """Cancel generation task"""
        if task_id not in self.tasks:
            return False

        task = self.tasks[task_id]
        task['cancelled'] = True

        if task['status'] == 'running':
            task['status'] = 'cancelling'
        return True
