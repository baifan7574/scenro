from io import BytesIO
import re

def split_cn_en(input_file):
    """分离文本中的中文和英文（彻底修正正则表达式）"""
    try:
        # 读取文本内容（忽略无法解码的特殊字符）
        content = input_file.read().decode("utf-8", errors="ignore")
        
        # 🌟 正确的中文匹配正则（无错误范围）
        # 匹配：中文汉字（\u4e00-\u9fa5） + 常见中文标点（。，！？；：“”‘’）
        cn_pattern = re.compile(r'[\u4e00-\u9fa5\u3002\uff0c\uff01\uff1f\uff1b\uff1a\u201c\u201d\u2018\u2019]')
        
        # 🌟 正确的英文匹配正则
        # 匹配：英文大小写字母（a-zA-Z） + 数字（0-9） + 英文标点（!-~包含所有英文符号）
        en_pattern = re.compile(r'[a-zA-Z0-9!-~]')
        
        # 提取中文和英文字符
        cn_chars = cn_pattern.findall(content)  # 所有中文及中文标点
        en_chars = en_pattern.findall(content)  # 所有英文及英文标点、数字
        
        # 生成结果文本（处理空内容情况）
        cn_text = ''.join(cn_chars) if cn_chars else "未检测到中文内容"
        en_text = ''.join(en_chars) if en_chars else "未检测到英文内容"
        result = f"=== 中文部分 ===\n{cn_text}\n\n=== 英文部分 ===\n{en_text}"
        
        # 转换为数据流返回
        output_stream = BytesIO()
        output_stream.write(result.encode("utf-8"))
        output_stream.seek(0)
        
        return output_stream, f"成功：提取到中文{len(cn_chars)}个，英文/数字{len(en_chars)}个"
    
    except Exception as e:
        return None, f"处理失败：{str(e)}"