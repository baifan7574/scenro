from io import BytesIO

def batch_replace(input_file, old_str, new_str):
    """批量替换文本中的内容"""
    try:
        content = input_file.read().decode("utf-8")
        # 统计替换次数
        replace_count = content.count(old_str)
        replaced_content = content.replace(old_str, new_str)
        
        output_stream = BytesIO()
        output_stream.write(replaced_content.encode("utf-8"))
        output_stream.seek(0)
        return output_stream, f"成功：共替换{replace_count}处（{old_str}→{new_str}）"
    except Exception as e:
        return None, f"失败：{str(e)}"