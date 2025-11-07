# text_newline.py（文本换行符转换工具）
from io import BytesIO

def convert_newline(input_file, convert_to="linux"):
    """
    功能：转换文本文件的换行符（Windows ↔ Linux）
    input_file：用户上传的TXT文件对象
    convert_to：转换目标，"linux"（\n）或 "windows"（\r\n）
    返回：转换后的数据流、状态提示
    """
    try:
        # 1. 读取文本内容（保留原始字节，避免解码丢失换行符）
        content_bytes = input_file.read()
        # 先解码为字符串，统一处理
        content = content_bytes.decode("utf-8", errors="ignore")
        
        # 2. 核心转换逻辑
        if convert_to == "linux":
            # Windows(\r\n) → Linux(\n)
            converted_content = content.replace("\r\n", "\n")
            msg = "成功：换行符已转为Linux格式（\\n）"
        else:
            # Linux(\n) → Windows(\r\n)
            converted_content = content.replace("\n", "\r\n")
            msg = "成功：换行符已转为Windows格式（\\r\\n）"
        
        # 3. 生成输出数据流
        output_stream = BytesIO()
        output_stream.write(converted_content.encode("utf-8"))
        output_stream.seek(0)
        
        return output_stream, msg
    
    except Exception as e:
        return None, f"处理失败：{str(e)}"