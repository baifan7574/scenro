# text_case.py（文本大小写转换工具）
from io import BytesIO

def convert_case(input_file, case_mode="lower"):
    """
    功能：转换文本大小写（全小写/全大写/首字母大写）
    input_file：用户上传的TXT文件对象
    case_mode：转换模式，"lower"（全小写）、"upper"（全大写）、"title"（首字母大写）
    返回：转换后的数据流、状态提示
    """
    try:
        # 1. 读取文本内容
        content = input_file.read().decode("utf-8", errors="ignore")
        
        # 2. 核心转换逻辑
        if case_mode == "lower":
            converted_content = content.lower()
            msg = "成功：文本已转为全小写"
        elif case_mode == "upper":
            converted_content = content.upper()
            msg = "成功：文本已转为全大写"
        else:  # title：每个单词首字母大写（中文不受影响）
            converted_content = content.title()
            msg = "成功：文本已转为首字母大写"
        
        # 3. 生成数据流
        output_stream = BytesIO()
        output_stream.write(converted_content.encode("utf-8"))
        output_stream.seek(0)
        
        return output_stream, msg
    
    except Exception as e:
        return None, f"处理失败：{str(e)}"