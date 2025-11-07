from io import BytesIO

def clean_spaces_empty_lines(input_file):
    """去除多余空格和空行"""
    try:
        content = input_file.read().decode("utf-8")
        # 去除多余空格（连续空格→单个空格）
        content = ' '.join(content.split())
        # 按行分割，过滤空行，再重新拼接
        lines = [line.strip() for line in content.split('\n') if line.strip()]
        cleaned_content = '\n'.join(lines)
        
        output_stream = BytesIO()
        output_stream.write(cleaned_content.encode("utf-8"))
        output_stream.seek(0)
        return output_stream, f"成功：已去除多余空格和空行，共{len(lines)}行"
    except Exception as e:
        return None, f"失败：{str(e)}"