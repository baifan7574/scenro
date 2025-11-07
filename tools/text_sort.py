from io import BytesIO

def sort_lines(input_file, sort_mode="asc", is_number=False):
    """按行排序（字母/数字，升序/降序）"""
    try:
        content = input_file.read().decode("utf-8")
        lines = [line.strip() for line in content.split('\n') if line.strip()]
        if not lines:
            return None, "失败：文本无有效内容"
        
        # 按数字排序（如果内容是数字）
        if is_number:
            lines = [float(line) if line.replace('.', '', 1).isdigit() else line for line in lines]
        
        # 升序/降序
        sorted_lines = sorted(lines, reverse=(sort_mode=="desc"))
        # 转回字符串
        sorted_lines = [str(line) for line in sorted_lines]
        
        output_stream = BytesIO()
        output_stream.write('\n'.join(sorted_lines).encode("utf-8"))
        output_stream.seek(0)
        return output_stream, f"成功：已按{'数字' if is_number else '字母'}{'降序' if sort_mode=='desc' else '升序'}排序，共{len(sorted_lines)}行"
    except Exception as e:
        return None, f"失败：{str(e)}"