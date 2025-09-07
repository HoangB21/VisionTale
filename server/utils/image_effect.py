from __future__ import annotations
import numpy as np
from PIL import Image, ImageEnhance, ImageChops
import random
import math
from typing import Dict, Tuple


class ImageEffects:
    @staticmethod
    def fade_effect(image: Image.Image, time_val: float, duration: float, params: Dict) -> Image.Image:
        """Hiệu ứng mờ dần vào/ra
        Sử dụng điều chỉnh độ sáng thay vì độ trong suốt để đảm bảo tương thích với MoviePy
        """
        if params.get('fade_duration', 0) <= 0:
            return image

        fade_duration = params['fade_duration']
        brightness = 1.0

        # Giai đoạn mờ dần vào
        if time_val < fade_duration:
            brightness = time_val / fade_duration
        # Giai đoạn mờ dần ra
        elif duration - time_val < fade_duration:
            brightness = (duration - time_val) / fade_duration

        # Sử dụng điều chỉnh độ sáng để thực hiện mờ dần vào/ra, thay vì độ trong suốt
        if brightness < 1.0:
            enhancer = ImageEnhance.Brightness(image)
            image = enhancer.enhance(brightness)

        return image

    @staticmethod
    def pan_effect(image: Image.Image, time_val: float, duration: float, params: Dict) -> Image.Image:
        """
        Hiệu ứng di chuyển và thu phóng mượt mà, ngăn ngừa kéo giãn hình ảnh.
        Tính toán tỷ lệ thu phóng chính xác để đảm bảo hình ảnh giữ tỷ lệ khung hình gốc trong phạm vi di chuyển.
        """
        output_w, output_h = params['output_size']
        pan_range = params.get('pan_range', (0.3, 0))
        segment_index = params.get('segment_index', 0)
        h_range, v_range = pan_range

        # Xác định hướng di chuyển
        use_horizontal = True
        if h_range > 0 and v_range > 0:
            use_horizontal = segment_index % 2 == 0
        elif v_range > 0:
            use_horizontal = False

        # Nếu không có di chuyển, cắt hình ảnh vào giữa
        if h_range <= 0 and v_range <= 0:
            img_aspect = image.width / image.height
            out_aspect = output_w / output_h

            if img_aspect > out_aspect:
                new_height = output_h
                new_width = int(new_height * img_aspect)
                scaled_img = image.resize(
                    (new_width, new_height), Image.LANCZOS)
                left = (new_width - output_w) // 2
                return scaled_img.crop((left, 0, left + output_w, output_h))
            else:
                new_width = output_w
                new_height = int(new_width / img_aspect)
                scaled_img = image.resize(
                    (new_width, new_height), Image.LANCZOS)
                top = (new_height - output_h) // 2
                return scaled_img.crop((0, top, output_w, top + output_h))

        # Tính toán tỷ lệ thu phóng, giữ tỷ lệ khung hình
        img_w, img_h = image.width, image.height

        if use_horizontal:
            # Tính tỷ lệ thu phóng cho di chuyển ngang
            required_width = output_w * (1 + h_range)
            ratio_w = required_width / img_w
            ratio_h = output_h / img_h
            scale_ratio = max(ratio_w, ratio_h)
        else:  # Di chuyển dọc
            required_height = output_h * (1 + v_range)
            ratio_h = required_height / img_h
            ratio_w = output_w / img_w
            scale_ratio = max(ratio_w, ratio_h)

        new_width = int(img_w * scale_ratio)
        new_height = int(img_h * scale_ratio)

        scaled_img = image.resize((new_width, new_height), Image.LANCZOS)

        # Sử dụng hàm chuyển động mượt để tính tiến độ di chuyển
        progress = ImageEffects._ease_in_out_progress(time_val / duration)

        # Tính vị trí khung cắt
        if use_horizontal:
            max_x_offset = scaled_img.width - output_w
            x_offset = int(max_x_offset * progress)
            y_offset = (scaled_img.height - output_h) // 2
        else:  # Di chuyển dọc
            max_y_offset = scaled_img.height - output_h
            y_offset = int(max_y_offset * progress)
            x_offset = (scaled_img.width - output_w) // 2

        return scaled_img.crop((
            x_offset, y_offset,
            x_offset + output_w, y_offset + output_h
        ))

    @staticmethod
    def _ease_in_out_progress(progress: float) -> float:
        """Hàm chuyển động mượt mà, tạo cảm giác tự nhiên hơn"""
        # Sử dụng hàm sin cho chuyển động mượt
        return 0.5 * (1 - math.cos(math.pi * progress))

    @classmethod
    def apply_effects(cls, image: Image.Image, time_val: float, duration: float, params: Dict) -> Image.Image:
        """Áp dụng tất cả các hiệu ứng"""
        # Thứ tự thực hiện hiệu ứng
        effect_chain = []

        # Áp dụng hiệu ứng di chuyển trước để tránh bị hiệu ứng mờ dần vào/ra làm mất
        if params.get('use_pan', True):
            effect_chain.append(cls.pan_effect)

        # Hiệu ứng mờ dần vào/ra nên là bước cuối cùng
        effect_chain.append(cls.fade_effect)

        processed_image = image.copy()
        for effect in effect_chain:
            processed_image = effect(
                processed_image, time_val, duration, params)
            # Không cần cắt lại sau mỗi hiệu ứng vì hàm hiệu ứng đã xử lý kích thước

        return processed_image
