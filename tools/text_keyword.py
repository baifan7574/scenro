# text_keyword.py（文本关键词提取工具）
from io import BytesIO
from collections import Counter
import re

def extract_keywords(input_file, top_n=10):
    """
    功能：提取文本中出现频率最高的N个关键词（排除常见停用词）
    input_file：用户上传的TXT文件对象
    top_n：要提取的关键词数量（默认10个）
    返回：关键词结果数据流、状态提示
    """
    try:
        # 1. 读取并预处理文本（去标点、小写化）
        content = input_file.read().decode("utf-8", errors="ignore")
        # 去除标点符号，只保留中文、英文、数字
        content_clean = re.sub(r"[^\u4e00-\u9fa5a-zA-Z0-9\s]", "", content)
        # 按空格/换行分割成词（简单分词，适合小白用户）
        words = [word.strip() for word in content_clean.split() if word.strip()]
        
        if not words:
            return None, "处理失败：文本中没有可提取的有效词汇"
        
        # 2. 排除常见停用词（比如“的、是、在”等无意义词）
        stop_words = {"的", "了", "是", "在", "有", "和", "就", "我", "他", "她", 
                     "它", "我们", "你们", "他们", "这", "那", "不", "也", "都", "要",
                     "a", "an", "the", "is", "are", "was", "were", "in", "on", "at", "for"}
        useful_words = [word for word in words if word not in stop_words and len(word) > 1]
        
        # 3. 统计词频，取Top N
        word_count = Counter(useful_words)
        top_keywords = word_count.most_common(top_n)  # 按频率排序
        
        # 4. 生成结果文本
        result = f"=== 文本关键词提取结果（Top {top_n}） ===\n"
        result += "排名 | 关键词 | 出现次数\n"
        result += "-------------------------\n"
        for i, (word, count) in enumerate(top_keywords, 1):
            result += f"{i:2d}   | {word:8s} | {count}次\n"
        
        # 5. 生成数据流
        output_stream = BytesIO()
        output_stream.write(result.encode("utf-8"))
        output_stream.seek(0)
        
        return output_stream, f"成功：提取到{len(top_keywords)}个关键词"
    
    except Exception as e:
        return None, f"处理失败：{str(e)}"