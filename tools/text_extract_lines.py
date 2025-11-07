from io import BytesIO

def extract_lines(input_file, extract_mode="keyword", keyword="", n=10):
    """提取指定行（关键词行/前N行/后N行）"""
    try:
        content = input_file.read().decode("utf-8")
        lines = [line.rstrip('\n') for line in content.split('\n')]  # 保留每行原始格式
        if not lines:
            return None, "失败：文本无内容"
        
        # 按模式提取
        if extract_mode == "keyword":
            result_lines = [line for line in lines if keyword in line]
            msg = f"成功：提取到包含'{keyword}'的行，共{len(result_lines)}行"
        elif extract_mode == "first":
            result_lines = lines[:n]
            msg = f"成功：提取前{n}行，共{len(result_lines)}行"
        else:  # last
            result_lines = lines[-n:] if n <= len(lines) else lines
            msg = f"成功：提取后{n}行，共{len(result_lines)}行"
        
        output_stream = BytesIO()
        output_stream.write('\n'.join(result_lines).encode("utf-8"))
        output_stream.seek(0)
        return output_stream, msg
    except Exception as e:
        return None, f"失败：{str(e)}"