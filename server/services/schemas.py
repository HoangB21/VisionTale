from __future__ import annotations
import json
from typing import Dict, List, Optional
from pydantic import BaseModel, RootModel, Field, ConfigDict

# Kết quả trích xuất cảnh: ánh xạ khóa-giá trị (tên cảnh -> mô tả tiếng Anh)


class SceneExtractionResult(RootModel[Dict[str, str]]):
    model_config = ConfigDict(json_schema_extra={
        "title": "SceneExtractionResult",
        "description": "Ánh xạ tên cảnh (bằng tiếng Việt) sang mô tả hình ảnh ngắn gọn bằng tiếng Anh. Chỉ mô tả môi trường; không mô tả nhân vật.",
        "examples": [
            {"Bậc thang giảng đường": "Concrete steps leading to a campus building entrance, metal handrails, bulletin board"}
        ]
    })


# Văn bản phân cảnh: danh sách spans
class TextSpan(BaseModel):
    content: str = Field(..., description="Nội dung đoạn văn gốc", examples=[
                         "Gia Huy đỏ mặt, thì thầm nhỏ…"])
    base_scene: str = Field(..., description="Tên cảnh nền (từ thư viện cảnh)", examples=[
                            "Bậc thang giảng đường"])
    scene: str = Field(..., description="Mô tả hình ảnh không bao gồm cảnh nền, ưu tiên động từ, giữ tính từ quan trọng; có thể chứa tên nhân vật trong {}",
                       examples=["{Gia Huy} đỏ mặt, thì thầm nhỏ"])


class TextDescResult(BaseModel):
    spans: List[TextSpan] = Field(...,
                                  description="Danh sách các đoạn phân cảnh")
    model_config = ConfigDict(json_schema_extra={
        "examples": [
            {
                "spans": [
                    {"content": "Gia Huy đỏ mặt, thì thầm nhỏ…",
                        "base_scene": "Bậc thang giảng đường", "scene": "{Gia Huy} đỏ mặt, thì thầm nhỏ"}
                ]
            }
        ]
    })


# Danh sách prompt dịch thường: list string
class PromptList(RootModel[List[str]]):
    model_config = ConfigDict(json_schema_extra={
        "title": "PromptList",
        "description": "Translated prompts list in English; each item is a concise, comma-separated prompt without trailing periods.",
        "examples": [[
            "A young woman, soft daylight, medium shot, street background, casual outfit, cinematic color grading"
        ]]
    })


# Prompt cho Kontext: mảng đối tượng
class PromptKontextItem(BaseModel):
    id: int = Field(..., ge=1,
                    description="Thứ tự của prompt đầu vào", examples=[1])
    convert_entity: str = Field(..., description="Ánh xạ/tóm tắt thực thể và cảnh",
                                examples=["Buồng lái->the cockpit, Liên Anh->the male commander"])
    thinking: str = Field(..., description="Phân tích ngắn: cách chia cảnh thành 1-4 bước mệnh lệnh và lý do chọn động từ",
                          examples=["Identify subject and cockpit; keep composition; adjust pose; add tapping gesture"])
    answer: str = Field(..., description="Chỉ thị tiếng Anh cuối cùng (1-4 câu mệnh lệnh)",
                        examples=["Place the male commander inside the cockpit. Change the pose to gaze out of the window. Adjust the right hand to tap the navigation console."])


class PromptKontextList(RootModel[List[PromptKontextItem]]):
    model_config = ConfigDict(json_schema_extra={
        "title": "PromptKontextList",
        "description": "List of FLUX.1 Kontext edit instructions per input item.",
        "examples": [[
            {
                "id": 1,
                "convert_entity": "Buồng lái->the cockpit, Liên Anh->the male commander",
                "thinking": "Identify subject and cockpit; keep composition; adjust pose; add tapping gesture",
                "answer": "Place the male commander inside the cockpit. Change the pose to gaze out of the window. Adjust the right hand to tap the navigation console."
            }
        ]]
    })


def append_output_schema_to_prompt(prompt: str, model_type: type[BaseModel]) -> str:
    """Thêm JSON Schema vào cuối prompt, để LLM xuất kết quả đúng định dạng."""
    schema_dict = model_type.model_json_schema()
    schema_json = json.dumps(schema_dict, ensure_ascii=False)
    suffix = "\n-OutputFormat: Vui lòng trả kết quả đúng theo Json Schema dưới đây\n" + schema_json
    return prompt.rstrip() + suffix


# Tóm tắt thay đổi quan hệ nhân vật
class RelationshipChange(BaseModel):
    type: str = Field(..., description="Loại quan hệ", examples=[
                      "bạn bè", "đồng nghiệp", "cha con"])
    source: str = Field(..., description="Tên thực thể nguồn",
                        examples=["Liên Anh"])
    target: str = Field(..., description="Tên thực thể đích",
                        examples=["Gia Huy"])
    attributes: Optional[Dict[str, str]] = Field(
        default=None, description="Từ điển thuộc tính bổ sung (tùy chọn)", examples=[[{"since": "Trung học"}]])


class CharacterExtractionSummary(BaseModel):
    added_entities: List[str] = Field(
        default_factory=list, description="Danh sách thực thể mới thêm", examples=[["Liên Anh"]])
    updated_entities: List[str] = Field(
        default_factory=list, description="Danh sách thực thể có cập nhật thuộc tính", examples=[["Gia Huy"]])
    new_relationships: List[RelationshipChange] = Field(
        default_factory=list, description="Danh sách quan hệ mới")
    updated_relationships: List[RelationshipChange] = Field(
        default_factory=list, description="Danh sách quan hệ được cập nhật")
    notes: Optional[str] = Field(default=None, description="Ghi chú hoặc giải thích thêm", examples=[
                                 "Bỏ qua cập nhật thuộc tính cho thực thể đã khóa"])
    model_config = ConfigDict(json_schema_extra={
        "title": "CharacterExtractionSummary",
        "description": "A compact summary of KG changes performed via tools during character extraction.",
    })


class StoryChapter(BaseModel):
    content: str = Field(..., description="Nội dung của một chương, tối đa 200 từ", examples=[
                         "Lâm Tiểu Hạ bước vào khu rừng, ánh trăng mờ ảo chiếu qua tán lá…"])


class StorySplitResult(BaseModel):
    chapters: List[StoryChapter] = Field(
        ..., description="Danh sách các chương đã chia từ câu chuyện")
    model_config = ConfigDict(json_schema_extra={
        "title": "StorySplitResult",
        "description": "Danh sách các chương được chia từ câu chuyện, mỗi chương không quá 200 từ, đảm bảo tính mạch lạc và logic.",
        "examples": [
            {
                "chapters": [
                    {"content": "Lâm Tiểu Hạ bước vào khu rừng, ánh trăng mờ ảo chiếu qua tán lá, chiếu sáng con đường mòn phủ đầy lá khô. Cô dừng lại, lắng nghe tiếng gió nhẹ thổi qua những cành cây. Một cảm giác bất an len lỏi trong lòng, như thể có ai đang theo dõi từ xa. Cô nắm chặt chiếc đèn pin, ánh sáng yếu ớt quét qua bóng tối, tìm kiếm dấu hiệu của sự sống."},
                    {"content": "Tiếng động lạ vang lên từ phía sau, khiến tim Lâm Tiểu Hạ đập thình thịch. Cô quay lại, nhưng chỉ thấy bóng cây lay động. Bước chân cô nhanh hơn, cố gắng tìm lối ra khỏi khu rừng. Đột nhiên, một ánh sáng lóe lên phía xa, như ngọn lửa nhỏ lập lòe. Tò mò xen lẫn sợ hãi, cô tiến về phía ánh sáng, hy vọng tìm được câu trả lời."}
                ]
            }
        ]
    })
