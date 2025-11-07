# text_tool.py（文本处理分类下的“文本去重工具”）
from io import BytesIO

def remove_duplicate_lines(input_file):
    """
    功能：去除文本文件中的重复行（保留第一次出现的行）
    input_file：用户上传的TXT文件对象
    返回：去重后的文本数据流、状态提示
    """
    try:
        # 1. 读取用户上传的文本内容
        text = input_file.read().decode("utf-8")  # 解码为字符串
        lines = text.splitlines()  # 按行分割
        
        # 2. 核心去重逻辑（保留首次出现的行）
        seen = set()  # 记录已出现的行
        unique_lines = []
        for line in lines:
            if line not in seen:
                seen.add(line)
                unique_lines.append(line)
        
        # 3. 生成去重后的文本（内存数据流）
        result_text = "\n".join(unique_lines)  # 重新拼接成行
        output_stream = BytesIO()
        output_stream.write(result_text.encode("utf-8"))  # 编码回字节流
        output_stream.seek(0)
        
        return output_stream, f"成功：原文件共{len(lines)}行，去重后剩{len(unique_lines)}行"
    
    except Exception as e:
        return None, f"处理失败：{str(e)}（请确保上传的是TXT文件）"