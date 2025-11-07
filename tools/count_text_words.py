# text_count.py（文本处理分类下的“字数统计工具”）
from io import BytesIO

def count_text_words(input_file):
    """
    功能：统计文本文件的总字数、行数、段落数
    input_file：用户上传的TXT文件对象
    返回：统计结果的数据流、状态提示
    """
    try:
        # 1. 读取文本内容
        text = input_file.read().decode("utf-8")
        
        # 2. 核心统计逻辑
        total_words = len(text)  # 总字数（含标点）
        total_lines = len(text.splitlines())  # 总行数
        total_paragraphs = len([p for p in text.split("\n\n") if p.strip()])  # 总段落数（空行分隔）
        
        # 3. 生成统计结果
        result_text = f"""=== 文本统计结果 ===
总字数：{total_words}
总行数：{total_lines}
总段落数：{total_paragraphs}
"""
        output_stream = BytesIO()
        output_stream.write(result_text.encode("utf-8"))
        output_stream.seek(0)
        
        return output_stream, f"成功：已统计{total_words}字"
    
    except Exception as e:
        return None, f"处理失败：{str(e)}"