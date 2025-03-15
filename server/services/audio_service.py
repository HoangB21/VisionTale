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
        self.tasks: Dict[str, Dict] = {}  # 存储正在进行的任务
        # 禁用代理
        os.environ['no_proxy'] = '*'
        # 设置信号处理
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """处理中断信号"""
        print("\n正在清理音频生成任务...")
        # 标记所有任务为取消状态
        for task_id in self.tasks:
            self.tasks[task_id]['cancelled'] = True
        print("音频生成任务已取消")

 

    async def generate_audio(self, prompts: List[str], output_dirs: List[str],
                           voice: str = "zh-CN-XiaoxiaoNeural",
                           rate: str = "+0%") -> Dict:
        """生成音频文件"""
        if len(prompts) != len(output_dirs):
            raise ValueError("prompts和output_dirs的长度必须相同")
            
        logger.info(f"使用语音：{voice}")
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        task_id = f'audio_{timestamp}'
        
        # 初始化任务信息
        self.tasks[task_id] = {
            'total': len(prompts),
            'completed': 0,
            'errors': [],
            'cancelled': False,
            'status': 'running'
        }
        
        # 创建异步任务
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
        """处理音频批量生成任务"""
        task = self.tasks[task_id]
        
        async def generate_single_audio(i: int, text: str, output_dir: str) -> bool:
            """生成单个音频文件"""
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
            # 并行生成所有音频
            tasks = [
                generate_single_audio(i, text, output_dir)
                for i, (text, output_dir) in enumerate(zip(prompts, output_dirs))
            ]
            await asyncio.gather(*tasks)
                
            # 更新最终状态
            if task['cancelled']:
                task['status'] = 'cancelled'
                # 清理未完成的文件
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
            # 清理所有文件
            for output_dir in output_dirs:
                output_path = os.path.join(output_dir, 'audio.mp3')
                if os.path.exists(output_path):
                    os.remove(output_path)

    def get_generation_progress(self, task_id: str) -> Dict:
        """获取生成任务的进度"""
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
        """取消生成任务"""
        if task_id not in self.tasks:
            return False
            
        task = self.tasks[task_id]
        task['cancelled'] = True
        
        if task['status'] == 'running':
            task['status'] = 'cancelling'
        return True
