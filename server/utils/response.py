from datetime import datetime
from fastapi.responses import JSONResponse


class APIException(Exception):
    def __init__(self, detail: str, status: str = "error"):
        super().__init__(detail)
        self.detail = detail
        self.status = status


def make_response(data=None, msg='', status='success'):
    """Định dạng phản hồi thống nhất

    Args:
        data: Dữ liệu trả về
        msg: Thông điệp trả về, mặc định là chuỗi rỗng
        status: Trạng thái, mặc định là 'success'

    Returns:
        JSONResponse:
        {
            'status': 'success' | 'error',
            'data': Any,
            'message': str
        }
    """
    status_code = 200 if status == 'success' else 400
    return JSONResponse(status_code=status_code, content={
        'status': status,
        'data': data,
        'message': msg,
    })
