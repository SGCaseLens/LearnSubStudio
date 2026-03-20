"""
LearnSubStudio - YouTube 双语字幕学习工具

⚠️ 重要法律声明:
本工具仅供个人学习和非商业研究用途。
使用本工具处理YouTube内容可能涉及版权问题。
用户必须遵守当地法律法规并自行承担法律责任。

禁止用于:
- 商业用途
- 公开分发
- 批量处理
- 侵犯版权的行为

详细法律信息请查看 README.md 中的法律声明和版权指南。

使用本工具即表示您已阅读、理解并同意遵守相关法律条款。
"""

import html
import json
import os
import re
import shutil
import subprocess
import sys
import time
import unicodedata
import argparse
from pathlib import Path
from typing import Dict, List, Tuple

import requests
from youtube_transcript_api import YouTubeTranscriptApi


VIDEO_W = 1080
VIDEO_H = 1920

# 短视频安全区设计 - 避开平台UI遮挡
SAFE_AREA_TOP = 160      # 顶部安全距离：避开状态栏、平台UI
SAFE_AREA_BOTTOM = 280   # 底部安全距离：避开操作按钮、评论区
SAFE_AREA_SIDE = 60      # 左右安全距离：避开边缘裁切

# 短视频布局区域定义
TITLE_SAFE_Y = SAFE_AREA_TOP + 40        # 标题安全位置：200px
SUMMARY_SAFE_Y = SAFE_AREA_TOP + 120     # 摘要安全位置：280px  
HISTORY_SAFE_TOP = SAFE_AREA_TOP + 200   # 历史区域顶部：360px
HISTORY_SAFE_BOTTOM = VIDEO_H - SAFE_AREA_BOTTOM - 380  # 历史区域底部：1260px
SPECTRUM_SAFE_Y = VIDEO_H - SAFE_AREA_BOTTOM - 440     # 频谱安全位置：1200px
SUBTITLE_SAFE_Y = VIDEO_H - SAFE_AREA_BOTTOM - 120     # 字幕安全位置：1520px

DEFAULT_LIBRETRANSLATE_ENDPOINT = os.environ.get(
    "LIBRETRANSLATE_ENDPOINT",
    "http://127.0.0.1:5000/translate",
)
DEFAULT_LIBRETRANSLATE_API_KEY = os.environ.get("LIBRETRANSLATE_API_KEY", "").strip() or None
TRANSLATION_CACHE_FILE = "translation_cache.json"

TITLE_FONTFILE = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
ASS_FONT_NAME = "Noto Sans CJK SC"

DEFAULT_SHOW_BARS = True
HISTORY_MAX_ROWS = 28  # 增加到原来的2倍，以容纳更多内容


def ensure_cmd(name: str) -> None:
    if shutil.which(name) is None:
        raise RuntimeError(f"找不到命令: {name}")


def parse_bool_arg(value: str) -> bool:
    v = value.strip().lower()
    if v in {"1", "true", "yes", "y", "on"}:
        return True
    if v in {"0", "false", "no", "n", "off"}:
        return False
    raise ValueError(f"无法解析布尔参数: {value}")


def is_valid_video_id(video_id: str) -> bool:
    """
    验证是否为有效的YouTube video_id
    YouTube video_id格式：11个字符，包含字母数字下划线连字符
    """
    if not video_id or len(video_id) != 11:
        return False
    return re.match(r'^[a-zA-Z0-9_-]{11}$', video_id) is not None


def extract_video_id_from_url(url_or_id: str) -> str:
    """
    从YouTube URL或直接的video_id中提取video_id
    支持的格式：
    - 直接video_id: "dQw4w9WgXcQ"
    - 标准YouTube URL: "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    - YouTube短链接: "https://youtu.be/dQw4w9WgXcQ"
    - 移动端URL: "https://m.youtube.com/watch?v=dQw4w9WgXcQ"
    - 嵌入URL: "https://www.youtube.com/embed/dQw4w9WgXcQ"
    """
    url_or_id = url_or_id.strip()
    
    if not url_or_id:
        raise ValueError("输入不能为空")
    
    # 如果输入看起来不像URL，验证是否为有效的video_id
    if not url_or_id.startswith(('http://', 'https://', 'www.', 'youtube.com', 'youtu.be', 'm.youtube.com')):
        if is_valid_video_id(url_or_id):
            return url_or_id
        else:
            raise ValueError(f"无效的YouTube video_id格式: {url_or_id}（应为11个字符的字母数字组合）")
    
    # 各种YouTube URL格式的正则表达式
    patterns = [
        r'(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})',  # 标准格式
        r'(?:https?://)?(?:www\.)?youtube\.com/watch\?.*v=([a-zA-Z0-9_-]{11})',  # 包含其他参数
        r'(?:https?://)?youtu\.be/([a-zA-Z0-9_-]{11})',  # 短链接
        r'(?:https?://)?(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]{11})',  # 嵌入格式
        r'(?:https?://)?m\.youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})',  # 移动端
        r'(?:https?://)?(?:www\.)?youtube\.com/v/([a-zA-Z0-9_-]{11})',  # 旧格式
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url_or_id, re.IGNORECASE)
        if match:
            video_id = match.group(1)
            if is_valid_video_id(video_id):
                return video_id
    
    # 如果没有匹配到任何模式，可能是一个不完整的URL或格式错误
    # 尝试从URL中提取可能的video_id
    video_id_match = re.search(r'([a-zA-Z0-9_-]{11})', url_or_id)
    if video_id_match:
        video_id = video_id_match.group(1)
        if is_valid_video_id(video_id):
            return video_id
    
    # 如果都失败了，抛出错误
    raise ValueError(f"无法从输入中提取有效的YouTube video_id: {url_or_id}")


def remove_garbled_chars(text: str) -> str:
    if not text:
        return ""

    text = html.unescape(text)
    text = unicodedata.normalize("NFKC", text)

    # 移除HTML标签和常见音频注释
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\[(music|applause|laughter|__+|inaudible|unclear)\]", " ", text, flags=re.I)
    text = re.sub(r"\((music|applause|laughter|inaudible|unclear)\)", " ", text, flags=re.I)
    text = text.replace("♪", " ")
    
    # 移除常见的乱码模式
    text = re.sub(r"[��]+", " ", text)  # 常见乱码字符
    text = re.sub(r"[\uFFF0-\uFFFF]+", " ", text)  # 特殊Unicode范围
    text = re.sub(r"[\u0000-\u001F]+", " ", text)  # 控制字符（除了\n \t）
    text = re.sub(r"[\u007F-\u009F]+", " ", text)  # 扩展控制字符

    cleaned = []
    for ch in text:
        cp = ord(ch)
        cat = unicodedata.category(ch)

        # 跳过替换字符和字节顺序标记
        if ch in {"\uFFFD", "\uFEFF", "\u200B", "\u200C", "\u200D"}:
            continue
        # 跳过私有使用区字符
        if 0xE000 <= cp <= 0xF8FF or 0xF0000 <= cp <= 0xFFFFF or 0x100000 <= cp <= 0x10FFFF:
            continue
        # 跳过代理对
        if 0xD800 <= cp <= 0xDFFF:
            continue
        # 跳过大部分控制字符，但保留换行、制表符和空格
        if cat.startswith("C") and ch not in {"\n", "\t", " "}:
            continue
        # 跳过格式字符（除了空格类）
        if cat.startswith("Cf") and not cat.startswith("Z"):
            continue

        cleaned.append(ch)

    text = "".join(cleaned)
    # 规范化空白字符
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"^\s+|\s+$", "", text, flags=re.MULTILINE)  # 移除行首行尾空格
    text = re.sub(r"\s+", " ", text).strip()
    return text


def clean_text(text: str) -> str:
    return remove_garbled_chars(text)


def dedupe_adjacent(items: List[Dict]) -> List[Dict]:
    result: List[Dict] = []
    prev = None
    for item in items:
        text = item["text"]
        if not text:
            continue
        if text == prev:
            continue
        result.append(item)
        prev = text
    return result


def fetch_transcript(video_id: str, lang: str = "en") -> List[Dict]:
    api = YouTubeTranscriptApi()
    fetched = api.fetch(video_id, languages=[lang, "en", "en-US", "en-GB"])

    items: List[Dict] = []
    for x in fetched:
        text = clean_text(x.text)
        if not text:
            continue
        start = float(x.start)
        duration = float(x.duration)
        items.append(
            {
                "text": text,
                "start": start,
                "duration": duration,
                "end": start + duration,
            }
        )

    if not items:
        raise RuntimeError("没有获取到可用英文字幕")
    return dedupe_adjacent(items)


def merge_short_items(items: List[Dict], min_duration: float = 1.25) -> List[Dict]:
    if not items:
        return items

    merged: List[Dict] = []
    buffer_item = None

    for item in items:
        if buffer_item is None:
            buffer_item = dict(item)
            continue

        if buffer_item["duration"] < min_duration:
            buffer_item["text"] = f"{buffer_item['text']} {item['text']}".strip()
            buffer_item["end"] = item["end"]
            buffer_item["duration"] = buffer_item["end"] - buffer_item["start"]
        else:
            merged.append(buffer_item)
            buffer_item = dict(item)

    if buffer_item is not None:
        merged.append(buffer_item)

    return merged


def build_text(items: List[Dict]) -> str:
    paragraphs: List[str] = []
    current: List[str] = []
    prev_end = None

    for item in items:
        start = item["start"]
        end = item["end"]
        text = item["text"]

        split_now = False
        if prev_end is not None and start - prev_end >= 2.5:
            split_now = True
        if sum(len(x) for x in current) > 180:
            split_now = True

        if split_now and current:
            paragraphs.append(" ".join(current))
            current = []

        current.append(text)
        prev_end = end

    if current:
        paragraphs.append(" ".join(current))

    paragraphs = [re.sub(r"\s+", " ", p).strip() for p in paragraphs if p.strip()]
    paragraphs = [p if p[-1] in ".!?" else p + "." for p in paragraphs]
    return "\n\n".join(paragraphs)


def get_youtube_title(video_id: str) -> str:
    url = f"https://www.youtube.com/watch?v={video_id}"
    result = subprocess.run(
        ["yt-dlp", "--print", "%(title)s", url],
        check=True,
        capture_output=True,
        text=True,
    )
    title = clean_text(result.stdout.strip())
    return title or video_id


def sanitize_drawtext_text(text: str) -> str:
    text = clean_text(text)
    text = text.replace("\\", r"\\\\")
    text = text.replace("'", r"\'")
    text = text.replace(":", r"\:")
    text = text.replace("%", r"\%")
    text = text.replace(",", r"\,")
    text = text.replace("[", r"\[")
    text = text.replace("]", r"\]")
    text = text.replace("\n", r"\n")
    return text


def ffmpeg_escape_path(path: str) -> str:
    path = path.replace("\\", r"\\")
    path = path.replace(":", r"\:")
    path = path.replace("'", r"\'")
    path = path.replace(",", r"\,")
    path = path.replace("[", r"\[")
    path = path.replace("]", r"\]")
    return path


def ass_escape_text(text: str) -> str:
    text = clean_text(text)
    text = text.replace("\\", r"\\")
    text = text.replace("{", r"\{")
    text = text.replace("}", r"\}")
    text = text.replace("\r", " ")
    return text


def ass_time(seconds: float) -> str:
    if seconds < 0:
        seconds = 0
    cs = int(round(seconds * 100))
    h = cs // 360000
    cs %= 360000
    m = cs // 6000
    cs %= 6000
    s = cs // 100
    cs %= 100
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def is_cjk_char(ch: str) -> bool:
    east = unicodedata.east_asian_width(ch)
    return east in {"F", "W"}


def char_display_width(ch: str) -> float:
    if ch == "\n":
        return 0.0
    if ch == " ":
        return 0.38
    if ch == "\t":
        return 1.2
    if is_cjk_char(ch):
        return 1.0
    if re.match(r"[A-Z]", ch):
        return 0.68
    if re.match(r"[a-z0-9]", ch):
        return 0.58
    return 0.72


def split_text_preserve_spaces(text: str) -> List[str]:
    text = clean_text(text)
    if not text:
        return []
    return re.findall(r"\s+|[A-Za-z0-9'’-]+|[^\sA-Za-z0-9]", text)


def token_visual_width(token: str) -> float:
    return sum(char_display_width(ch) for ch in token)


def wrap_text_by_visual_width(text: str, max_units: float) -> str:
    text = clean_text(text)
    if not text:
        return ""

    tokens = split_text_preserve_spaces(text)
    if not tokens:
        return ""

    lines: List[str] = []
    current: List[str] = []
    current_units = 0.0

    for token in tokens:
        if token == "":
            continue

        if token.isspace():
            if current:
                current.append(" ")
                current_units += char_display_width(" ")
            continue

        t_units = token_visual_width(token)

        if current and current_units + t_units > max_units:
            line = "".join(current).strip()
            if line:
                lines.append(line)
            current = [token]
            current_units = t_units
        else:
            current.append(token)
            current_units += t_units

    if current:
        line = "".join(current).strip()
        if line:
            lines.append(line)

    return r"\N".join(lines)


def wrap_title_for_mobile(title: str, max_units_per_line: float = 20.0, max_lines: int = 3) -> str:
    title = clean_text(title)
    if not title:
        return ""

    wrapped = wrap_text_by_visual_width(title, max_units=max_units_per_line)
    lines = [x.strip() for x in wrapped.split(r"\N") if x.strip()]

    if len(lines) <= max_lines:
        return "\n".join(lines)

    lines = lines[:max_lines]
    last = lines[-1]
    if len(last) >= 1:
        last = last[:-1].rstrip() + "…"
    else:
        last = "…"
    lines[-1] = last
    return "\n".join(lines)


def count_ass_lines(text: str) -> int:
    if not text:
        return 0
    return text.count(r"\N") + 1


def ensure_english_word_spacing(text: str) -> str:
    """
    确保英文单词之间有正确的空格
    """
    if not text:
        return ""
    
    # 在英文单词之间确保有空格
    text = re.sub(r'([a-zA-Z])([A-Z][a-z])', r'\1 \2', text)  # 驼峰式命名分割
    text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)          # 小写后跟大写
    text = re.sub(r'([a-zA-Z])(\d)', r'\1 \2', text)          # 字母后跟数字
    text = re.sub(r'(\d)([a-zA-Z])', r'\1 \2', text)          # 数字后跟字母
    text = re.sub(r'([.!?])([A-Z])', r'\1 \2', text)          # 句号后跟大写字母
    
    # 标准化多个空格为单个空格
    text = re.sub(r'[ \t]+', ' ', text)
    
    return text.strip()


def split_for_karaoke(text: str) -> List[str]:
    if not text:
        return []

    tokens = re.findall(r"\n|\s+|[A-Za-z0-9'’-]+|[^\sA-Za-z0-9]", text)
    return tokens


def classify_word_type(word: str) -> str:
    """
    根据词汇特征分类，返回词汇类型
    """
    word_clean = word.strip().lower()
    
    # 数字类型（包括年份、百分比、货币等）
    if re.match(r'^\d+([.,]\d+)*[%$£€¥]?$', word_clean) or \
       re.match(r'^[£€¥$]\d+([.,]\d+)*$', word_clean) or \
       re.match(r'^\d{4}$', word_clean):  # 年份
        return 'number'
    
    # 专有名词（首字母大写的词汇）
    if word[0].isupper() and len(word) > 1:
        # 常见品牌名（扩展列表）
        brand_keywords = {
            # 科技巨头
            'apple', 'google', 'microsoft', 'amazon', 'facebook', 'meta', 'tesla', 
            'nvidia', 'intel', 'amd', 'samsung', 'huawei', 'xiaomi', 'sony', 'lg',
            'dell', 'hp', 'lenovo', 'asus', 'acer', 'ibm', 'oracle', 'salesforce',
            
            # 社交媒体和平台
            'netflix', 'youtube', 'twitter', 'instagram', 'tiktok', 'linkedin',
            'snapchat', 'whatsapp', 'telegram', 'discord', 'slack', 'zoom',
            
            # AI和新兴技术
            'openai', 'anthropic', 'deepmind', 'chatgpt', 'gpt', 'claude', 
            'gemini', 'bard', 'copilot', 'midjourney', 'stability',
            
            # 娱乐和游戏
            'disney', 'marvel', 'dc', 'warner', 'universal', 'paramount',
            'pokemon', 'nintendo', 'playstation', 'xbox', 'steam', 
            'minecraft', 'fortnite', 'roblox', 'unity', 'unreal',
            
            # 操作系统和软件
            'iphone', 'android', 'windows', 'macos', 'linux', 'ubuntu',
            'chrome', 'safari', 'firefox', 'edge', 'photoshop', 'illustrator',
            
            # 汽车和交通
            'uber', 'lyft', 'airbnb', 'spacex', 'boeing', 'airbus',
            'toyota', 'honda', 'bmw', 'mercedes', 'audi', 'volkswagen',
            
            # 金融和支付
            'paypal', 'visa', 'mastercard', 'bitcoin', 'ethereum', 'coinbase',
            'robinhood', 'stripe', 'square', 'alipay', 'wechat'
        }
        
        if word_clean in brand_keywords:
            return 'brand'
        
        # 常见人名（可以扩展）
        name_indicators = {
            'mr', 'mrs', 'dr', 'prof', 'sir', 'lady', 'lord'
        }
        
        # 检查是否为人名（简单启发式规则）
        if len(word) >= 3 and word.isalpha():
            return 'person'
    
    # 核心动词（重要的行为词汇）
    core_verbs = {
        # 创造和建设
        'create', 'build', 'develop', 'design', 'implement', 'execute', 'make', 'produce',
        'construct', 'generate', 'establish', 'found', 'launch', 'initiate', 'start', 'begin',
        
        # 分析和优化  
        'analyze', 'optimize', 'improve', 'enhance', 'transform', 'innovate', 'upgrade', 
        'refactor', 'streamline', 'automate', 'scale', 'accelerate', 'maximize', 'minimize',
        
        # 学习和研究
        'discover', 'explore', 'research', 'investigate', 'study', 'learn', 'understand',
        'master', 'acquire', 'absorb', 'grasp', 'comprehend', 'realize', 'recognize',
        
        # 教学和传播
        'teach', 'explain', 'demonstrate', 'present', 'communicate', 'share', 'show',
        'guide', 'mentor', 'train', 'educate', 'inspire', 'motivate', 'influence',
        
        # 成就和完成
        'achieve', 'accomplish', 'succeed', 'win', 'complete', 'finish', 'solve',
        'overcome', 'conquer', 'master', 'excel', 'outperform', 'breakthrough'
    }
    
    if word_clean in core_verbs:
        return 'verb'
    
    # 技术关键词
    tech_keywords = {
        # AI和机器学习
        'ai', 'artificial', 'intelligence', 'machine', 'learning', 'deep', 'neural', 
        'network', 'algorithm', 'model', 'training', 'inference', 'transformer',
        'llm', 'gpt', 'bert', 'attention', 'embedding', 'tokenization',
        
        # 数据科学
        'data', 'science', 'analytics', 'big', 'dataset', 'database', 'sql',
        'python', 'pandas', 'numpy', 'tensorflow', 'pytorch', 'sklearn',
        
        # 云计算和基础设施  
        'cloud', 'computing', 'aws', 'azure', 'docker', 'kubernetes', 'api',
        'microservices', 'serverless', 'devops', 'cicd', 'automation',
        
        # 区块链和加密货币
        'blockchain', 'cryptocurrency', 'bitcoin', 'ethereum', 'nft', 'defi',
        'smart', 'contract', 'wallet', 'mining', 'consensus', 'decentralized',
        
        # 编程和开发
        'programming', 'coding', 'development', 'frontend', 'backend', 'fullstack',
        'javascript', 'react', 'vue', 'angular', 'node', 'express', 'django',
        'framework', 'library', 'repository', 'github', 'git', 'version',
        
        # 通用技术
        'software', 'hardware', 'technology', 'digital', 'internet', 'web',
        'mobile', 'app', 'application', 'platform', 'system', 'architecture',
        'security', 'encryption', 'authentication', 'authorization', 'protocol'
    }
    
    if word_clean in tech_keywords:
        return 'tech'
    
    return 'default'


def get_highlight_color(word_type: str) -> str:
    """
    根据词汇类型返回对应的ASS颜色代码（BGR格式）
    颜色经过优化，在深色背景上有优秀的对比度和可读性
    """
    color_map = {
        'person': '&H005599FF&',    # 人名：亮蓝色 - 专业感，代表人物
        'brand': '&H0000FFFF&',     # 品牌：亮黄色 - 醒目，代表商业品牌  
        'number': '&H0066FF66&',    # 数字：亮绿色 - 清晰，代表数据
        'verb': '&H00FF66FF&',      # 核心动词：亮紫色 - 动感，代表行为
        'tech': '&H00FF9900&',      # 技术词汇：橙色 - 创新感，代表科技
        'default': '&H0099CCFF&'    # 默认高亮：浅橙色 - 温和突出
    }
    return color_map.get(word_type, color_map['default'])


def extract_keywords(items: List[Dict], top_n: int = 8) -> List[str]:
    stopwords = {
        "the", "a", "an", "and", "or", "to", "of", "in", "on", "for", "with",
        "is", "are", "was", "were", "be", "been", "being", "that", "this",
        "it", "as", "at", "by", "from", "you", "your", "i", "we", "they",
        "he", "she", "them", "our", "us", "but", "if", "so", "do", "does",
        "did", "have", "has", "had", "will", "would", "can", "could", "just"
    }
    words: List[str] = []
    for item in items:
        for w in re.findall(r"[A-Za-z][A-Za-z'-]{2,}", item["text"].lower()):
            if w not in stopwords:
                words.append(w)

    counter: Dict[str, int] = {}
    for w in words:
        counter[w] = counter.get(w, 0) + 1

    ranked = sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))
    return [w for w, _ in ranked[:top_n]]


def build_karaoke_en_line(
    en_text: str,
    duration_sec: float,
    keywords: List[str] | None = None,
    max_units: float = 32.0,
) -> str:
    en_text = clean_text(en_text)
    # 确保英文单词之间有正确的空格
    en_text = ensure_english_word_spacing(en_text)
    # 进一步确保单词间有空格：在字母和字母、字母和数字之间添加空格
    en_text = re.sub(r'([a-zA-Z])([A-Z][a-z])', r'\1 \2', en_text)
    en_text = re.sub(r'([a-z])([A-Z])', r'\1 \2', en_text)  
    en_text = re.sub(r'([A-Za-z])(\d)', r'\1 \2', en_text)
    en_text = re.sub(r'(\d)([A-Za-z])', r'\1 \2', en_text)
    # 规范化多个空格为单个空格
    en_text = re.sub(r'[ \t]+', ' ', en_text).strip()
    
    keyword_set = {k.lower() for k in (keywords or [])}

    wrapped_en_plain = wrap_text_by_visual_width(en_text, max_units)
    display_text = wrapped_en_plain.replace(r"\N", "\n")

    en_tokens = split_for_karaoke(display_text)
    visible_tokens = [t for t in en_tokens if t.strip() and t != "\n"]

    if not visible_tokens:
        return ass_escape_text(display_text).replace(r"\\N", r"\N")

    total_cs = max(1, int(round(duration_sec * 100)))
    per_token = max(1, total_cs // len(visible_tokens))
    remainder = total_cs - per_token * len(visible_tokens)

    parts: List[str] = []
    visible_idx = 0

    for tok in en_tokens:
        if tok == "\n":
            parts.append(r"\N")
            continue

        escaped = ass_escape_text(tok)

        if tok.strip():
            raw = tok.strip(" ,.!?;:\"'()[]{}").lower()
            dur = per_token + (1 if visible_idx < remainder else 0)
            
            # 智能分类高亮：根据词汇类型使用不同颜色
            word_type = classify_word_type(tok.strip())
            
            # 如果是关键词或特殊类型，使用对应颜色高亮
            if raw in keyword_set or word_type != 'default':
                color_code = get_highlight_color(word_type)
                piece = rf"{{\kf{dur}\c{color_code}}}{escaped}{{\c}}"
            else:
                piece = rf"{{\kf{dur}}}{escaped}"
            parts.append(piece)
            visible_idx += 1
        else:
            # 确保空格字符被正确保留，特别是英文单词之间的空格
            if tok.isspace() and " " in tok:
                parts.append(" ")  # 确保英文单词间的空格
            else:
                parts.append(escaped)

    return "".join(parts)


def build_bilingual_karaoke_ass_text(
    en_text: str,
    zh_text: str,
    duration_sec: float,
    keywords: List[str] | None = None,
    max_units_en: float = 32.0,
    max_units_zh: float = 24.0,
) -> tuple[str, str]:
    """
    构建分层双语字幕：返回(英文字幕, 中文字幕)
    英文：更大、更亮、更突出（主焦点）
    中文：更小、更稳、更辅助（理解辅助）
    """
    # 构建突出的英文卡拉OK字幕
    en_line = build_karaoke_en_line(
        en_text=en_text,
        duration_sec=duration_sec,
        keywords=keywords,
        max_units=max_units_en,
    )

    # 构建辅助的中文字幕（更柔和，不抢夺注意力）
    zh_line = ""
    if zh_text:
        zh_wrapped = wrap_text_by_visual_width(zh_text, max_units_zh)
        zh_line = ass_escape_text(zh_wrapped).replace(r"\\N", r"\N")
        

    return en_line, zh_line


def format_bilingual_block(
    en_text: str,
    zh_text: str,
    max_units_en: float,
    max_units_zh: float,
) -> tuple[str, str]:
    """
    格式化分层双语历史块：返回(英文文本, 中文文本)
    """
    en = wrap_text_by_visual_width(en_text, max_units_en)
    en = ass_escape_text(en).replace(r"\\N", r"\N")
    
    zh = ""
    if zh_text:
        zh = wrap_text_by_visual_width(zh_text, max_units_zh)
        zh = ass_escape_text(zh).replace(r"\\N", r"\N")

    return en, zh


def load_translation_cache() -> dict:
    path = Path(TRANSLATION_CACHE_FILE)
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_translation_cache(cache: dict) -> None:
    with open(TRANSLATION_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def translate_with_libretranslate(
    text: str,
    source: str = "en",
    target: str = "zh",
    endpoint: str = DEFAULT_LIBRETRANSLATE_ENDPOINT,
    api_key: str | None = DEFAULT_LIBRETRANSLATE_API_KEY,
    timeout: int = 30,
    max_retries: int = 5,
) -> str:
    payload = {
        "q": text,
        "source": source,
        "target": target,
        "format": "text",
    }
    if api_key:
        payload["api_key"] = api_key

    retry_wait = 1.0

    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.post(endpoint, data=payload, timeout=timeout)
            if resp.status_code == 429:
                if attempt == max_retries:
                    raise RuntimeError("翻译接口限流，重试后仍失败")
                time.sleep(retry_wait)
                retry_wait *= 2
                continue

            resp.raise_for_status()
            data = resp.json()
            translated = clean_text(data.get("translatedText", "").strip())
            if not translated:
                raise RuntimeError("LibreTranslate 没有返回 translatedText")
            return translated
        except requests.RequestException as e:
            if attempt == max_retries:
                raise RuntimeError(f"翻译请求失败: {e}") from e
            time.sleep(retry_wait)
            retry_wait *= 2

    raise RuntimeError("翻译失败")




def build_bilingual_items_with_libretranslate(
    items: List[Dict],
    endpoint: str = DEFAULT_LIBRETRANSLATE_ENDPOINT,
    api_key: str | None = DEFAULT_LIBRETRANSLATE_API_KEY,
    sleep_sec: float = 0.02,
) -> List[Dict]:
    bilingual_items: List[Dict] = []
    cache = load_translation_cache()

    for idx, item in enumerate(items, start=1):
        en_text = clean_text(item["text"].strip())
        if not en_text:
            continue

        if en_text in cache:
            zh_text = clean_text(cache[en_text])
        else:
            try:
                zh_text = translate_with_libretranslate(
                    text=en_text,
                    source="en",
                    target="zh",
                    endpoint=endpoint,
                    api_key=api_key,
                    max_retries=5,
                )
                cache[en_text] = zh_text
                save_translation_cache(cache)
            except Exception as e:
                print(f"第 {idx} 条翻译失败，中文留空。原因: {e}")
                zh_text = ""

            if sleep_sec > 0:
                time.sleep(sleep_sec)

        bilingual_items.append(
            {
                "en": en_text,
                "zh": zh_text,
                "start": item["start"],
                "duration": item["duration"],
                "end": item["end"],
            }
        )

    return bilingual_items


def summarize_items_to_bullets(items: List[Dict], max_bullets: int = 3) -> List[str]:
    text = " ".join(clean_text(x["en"]) for x in items[: min(len(items), 30)])
    text = re.sub(r"\[[^\]]+\]", " ", text)
    text = re.sub(r"[♪]+", " ", text)
    text = clean_text(text)
    sentences = re.split(r"(?<=[.!?])\s+", text)

    bullets: List[str] = []
    for s in sentences:
        s = clean_text(s)
        if len(s) < 30:
            continue
        bullets.append(s[:80] + ("..." if len(s) > 80 else ""))
        if len(bullets) >= max_bullets:
            break
    return bullets


def translate_bullets_to_zh(bullets: List[str]) -> List[str]:
    result: List[str] = []
    for b in bullets:
        try:
            zh = translate_with_libretranslate(b)
            zh = clean_text(zh)
            result.append("• " + zh)
        except Exception:
            result.append("• " + clean_text(b))
    return result


def print_safe_area_layout():
    """
    显示短视频安全区布局设计
    - 确保内容不被平台UI遮挡
    - 适配TikTok、Instagram Reels、YouTube Shorts等移动端平台
    """
    print("📱 短视频安全区布局 (1080x1920):")
    print("┌" + "─" * 50 + "┐")
    print(f"│ 顶部安全区 ({SAFE_AREA_TOP}px)       │ ← 避开状态栏/平台UI")
    print(f"├─ 标题区域 ({TITLE_SAFE_Y}px)        │")
    print(f"├─ 摘要区域 ({SUMMARY_SAFE_Y}px)        │")
    print(f"├─ 历史字幕 ({HISTORY_SAFE_TOP}-{HISTORY_SAFE_BOTTOM}px) │")
    print(f"├─ 频谱图   ({SPECTRUM_SAFE_Y}px)       │ ← 位于历史字幕和主字幕之间")
    print(f"├─ 主字幕   ({SUBTITLE_SAFE_Y}px)       │")
    print(f"│ 底部安全区 ({SAFE_AREA_BOTTOM}px)       │ ← 避开操作按钮/评论")
    print("└" + "─" * 50 + "┘")
    print(f"📐 安全边距: 顶部{SAFE_AREA_TOP}px, 底部{SAFE_AREA_BOTTOM}px, 左右{SAFE_AREA_SIDE}px")


def detect_audio_content_type(items: List[Dict]) -> str:
    """
    智能检测音频内容类型：人声为主 vs 音乐为主
    基于字幕内容和语言特征进行分析
    
    Returns:
        'speech': 讲话/演讲/教学类内容
        'music': 音乐/娱乐类内容  
        'mixed': 混合类型
    """
    if not items:
        return 'speech'  # 默认为讲话类
    
    # 分析指标
    total_text_length = 0
    music_indicators = 0
    speech_indicators = 0
    short_segments = 0
    
    # 音乐相关关键词
    music_keywords = {
        # 音乐术语
        'song', 'music', 'beat', 'rhythm', 'melody', 'harmony', 'bass', 'drum',
        'guitar', 'piano', 'vocal', 'singer', 'band', 'album', 'track', 'sound',
        'audio', 'recording', 'mix', 'remix', 'dj', 'producer', 'studio',
        
        # 情感表达词汇（音乐中常见）
        'yeah', 'oh', 'baby', 'love', 'heart', 'feel', 'dance', 'party',
        'tonight', 'forever', 'never', 'always', 'dream', 'fire', 'fly',
        
        # 音乐流派
        'rock', 'pop', 'jazz', 'blues', 'hip', 'hop', 'rap', 'electronic',
        'classical', 'country', 'folk', 'metal', 'punk', 'reggae', 'techno'
    }
    
    # 讲话类关键词
    speech_keywords = {
        # 教学词汇
        'learn', 'teach', 'explain', 'understand', 'know', 'think', 'believe',
        'example', 'problem', 'solution', 'method', 'process', 'result', 'data',
        'research', 'study', 'analysis', 'theory', 'practice', 'experiment',
        
        # 演讲词汇
        'today', 'discuss', 'talk', 'presentation', 'topic', 'question', 'answer',
        'important', 'point', 'issue', 'concept', 'idea', 'information', 'fact',
        
        # 技术词汇
        'technology', 'system', 'software', 'computer', 'internet', 'digital',
        'program', 'code', 'algorithm', 'artificial', 'intelligence', 'machine',
        
        # 商务词汇
        'business', 'company', 'market', 'customer', 'product', 'service',
        'strategy', 'management', 'project', 'team', 'work', 'develop'
    }
    
    for item in items:
        text = item.get('en', '').lower()
        text_length = len(text.strip())
        total_text_length += text_length
        
        # 检测短片段（音乐中常见短语或重复）
        if text_length < 30:  # 很短的文本片段
            short_segments += 1
        
        # 统计音乐相关词汇
        music_count = sum(1 for word in music_keywords if word in text)
        music_indicators += music_count
        
        # 统计讲话相关词汇  
        speech_count = sum(1 for word in speech_keywords if word in text)
        speech_indicators += speech_count
        
    # 分析结果
    avg_text_length = total_text_length / len(items) if items else 0
    short_segment_ratio = short_segments / len(items) if items else 0
    
    # 决策逻辑
    music_score = 0
    speech_score = 0
    
    # 音乐类型指标
    if music_indicators > speech_indicators * 1.5:
        music_score += 2
    if short_segment_ratio > 0.4:  # 超过40%是短片段
        music_score += 2
    if avg_text_length < 25:  # 平均文本很短
        music_score += 1
    if music_indicators > 5:  # 有明显音乐词汇
        music_score += 1
        
    # 讲话类型指标  
    if speech_indicators > music_indicators * 1.5:
        speech_score += 2
    if avg_text_length > 50:  # 平均文本较长
        speech_score += 2
    if short_segment_ratio < 0.2:  # 短片段比例低
        speech_score += 1
    if speech_indicators > 8:  # 有明显讲话词汇
        speech_score += 1
        
    # 返回检测结果
    if music_score > speech_score + 1:
        return 'music'
    elif speech_score > music_score + 1:
        return 'speech'
    else:
        return 'mixed'


def auto_detect_show_bars(content_type: str) -> bool:
    """
    基于音频内容类型自动决定是否显示柱状图
    音乐类内容自动启用，讲话类内容自动关闭
    
    Args:
        content_type: 音频类型 ('music', 'speech', 'mixed')
        
    Returns:
        bool: 是否应该显示柱状图
    """
    auto_show_rules = {
        'music': True,    # 音乐类：自动启用柱状图，增强视觉效果
        'mixed': True,    # 混合类：启用柱状图，可能包含音乐元素
        'speech': False,  # 讲话类：关闭柱状图，避免干扰专注
    }
    
    return auto_show_rules.get(content_type, False)


def get_audio_visualization_params(content_type: str) -> Dict[str, str]:
    """
    根据音频内容类型返回对应的可视化参数
    包含精美的渐变色方案，提升视觉质感
    
    Args:
        content_type: 'speech', 'music', 'mixed'
        
    Returns:
        包含showfreqs参数的字典
    """
    if content_type == 'music':
        # 音乐类：活力渐变 - 从深蓝到紫色到亮白
        # 强烈动感的视觉效果，适合音乐内容
        return {
            'size': '760x220',           # 更高的显示区域
            'mode': 'bar',               # 柱状图模式
            'ascale': 'log',             # 对数振幅缩放
            'fscale': 'log',             # 对数频率缩放  
            'colors': '0x4A90E2@0.8|0x7B68EE@0.85|0xFFFFFF@0.9',  # 蓝→紫→白渐变
            'rate': '25',                # 更高的刷新率
            'overlap': '0.8'             # 更密集的重叠
        }
    elif content_type == 'speech':  
        # 讲话类：温和渐变 - 从浅橙到橙色到柔和白
        # 柔和稳重，不干扰学习专注力
        return {
            'size': '760x160',           # 较低的显示区域
            'mode': 'bar',               # 柱状图模式
            'ascale': 'sqrt',            # 平方根缩放（更平缓）
            'fscale': 'log',             # 对数频率缩放
            'colors': '0xFFB366@0.5|0xFF8C42@0.65|0xFFF8F0@0.7',  # 浅橙→橙→暖白渐变
            'rate': '15',                # 较低的刷新率
            'overlap': '0.5'             # 适中的重叠
        }
    else:  # mixed
        # 混合类：科技渐变 - 从青色到蓝色到纯白
        # 现代感强，适合各种内容类型
        return {
            'size': '760x180',           # 标准显示区域
            'mode': 'bar',               # 柱状图模式  
            'ascale': 'log',             # 对数振幅缩放
            'fscale': 'log',             # 对数频率缩放
            'colors': '0x20B2AA@0.65|0x4169E1@0.75|0xFFFFFF@0.8',  # 青→蓝→白渐变
            'rate': '20',                # 标准刷新率
            'overlap': '0.6'             # 标准重叠
        }


def build_chapter_markers(items: List[Dict], sections: int = 3) -> List[Tuple[float, float, str]]:
    if not items:
        return []
    total_start = items[0]["start"]
    total_end = items[-1]["end"]
    total = max(1.0, total_end - total_start)
    seg = total / sections

    markers: List[Tuple[float, float, str]] = []
    for i in range(sections):
        s = total_start + i * seg
        e = min(total_end, s + 2.5)
        markers.append((s, e, f"Part {i + 1}"))
    return markers


def calc_history_block_height(item: Dict) -> int:
    # 统一字体大小后的历史字幕高度计算
    en_wrapped = wrap_text_by_visual_width(item.get("en", ""), 32.0)
    zh_wrapped = wrap_text_by_visual_width(item.get("zh", ""), 24.0)

    en_lines = count_ass_lines(en_wrapped)
    zh_lines = count_ass_lines(zh_wrapped) if zh_wrapped else 0

    # 统一字体大小(40px)后，每行高度一致
    line_h = 40  # 历史字体40px对应的行高
    line_gap = 8  # 英中文之间的行间距
    
    # 英文行数 + 行间距（如果有中文） + 中文行数
    total_height = en_lines * line_h
    if zh_lines > 0:
        total_height += line_gap + zh_lines * line_h
    
    padding = 10  # 上下边距
    return total_height + padding


def calc_english_lines_height(en_text: str) -> int:
    """计算英文文本的实际显示高度（像素）"""
    if not en_text:
        return 0
    en_lines = count_ass_lines(en_text)
    return en_lines * 40  # 40px字体对应40px行高


def write_ass_karaoke(
    items: List[Dict],
    path: str,
    keywords: List[str],
    chapters: List[Tuple[float, float, str]],
    show_bars: bool,
    intro_offset: float = 0.0,
    subtitle_end_time: float = None,  # 字幕结束时间，用于片尾效果
) -> None:
    # 字幕层级设计：英文突出，中文辅助（短视频安全区）
    english_fontsize = 44      # 英文字体大小，避免超出边界（减小到44px）
    chinese_fontsize = 38      # 中文字体适中，清晰可读（调整到38px）
    
    # 计算短视频安全区字幕边距 - 英文在上，中文在下
    # ASS中MarginV是从底部开始计算：值越大越靠近顶部，值越小越靠近底部
    english_margin_v = SAFE_AREA_BOTTOM + 145  # 英文字幕在上方：425px距底，适中间距
    chinese_margin_v = SAFE_AREA_BOTTOM + 25   # 中文字幕在下方：305px距底
    subtitle_line_gap = 120  # 英中文字幕间距：120px，平衡美观与安全性

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {VIDEO_W}
PlayResY: {VIDEO_H}
ScaledBorderAndShadow: yes
WrapStyle: 2
YCbCr Matrix: TV.601

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: EnglishMain,{ASS_FONT_NAME},{english_fontsize},&H00FFFFFF,&H000080FF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,4,2,2,80,80,{english_margin_v},1
Style: ChineseAux,{ASS_FONT_NAME},{chinese_fontsize},&H000066FF,&H00808080,&H00000000,&H90000000,0,0,0,0,100,100,0,0,1,2,1,2,80,80,{chinese_margin_v},1
Style: Chapter,{ASS_FONT_NAME},34,&H00FFFFFF,&H000080FF,&H00000000,&H60000000,1,0,0,0,100,100,0,0,1,2,1,8,60,60,500,1
Style: HistoryEn,{ASS_FONT_NAME},{english_fontsize-8},&H000066FF,&H00C0C0C0,&H00000000,&H70000000,0,0,0,0,100,100,0,0,1,2.5,1,8,80,80,0,1
Style: HistoryCn,{ASS_FONT_NAME},{english_fontsize-8},&H000066FF,&H00707070,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,1.5,0.5,8,80,80,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    with open(path, "w", encoding="utf-8") as f:
        f.write(header)

        for start, end, title in chapters:
            # 应用片头时间偏移
            adjusted_start = start + intro_offset
            adjusted_end = end + intro_offset
            line = f"Dialogue: 0,{ass_time(adjusted_start)},{ass_time(adjusted_end)},Chapter,,0,0,0,,{ass_escape_text(title)}\n"
            f.write(line)

        history_center_x = VIDEO_W // 2

        # 短视频安全区历史字幕布局 - 使用最终的柱状图显示决定
        if show_bars:
            history_top_y = HISTORY_SAFE_TOP      # 安全区内开始
            history_bottom_y = SPECTRUM_SAFE_Y - 40   # 频谱图上方留出空间
        else:
            history_top_y = HISTORY_SAFE_TOP      # 安全区内开始  
            history_bottom_y = HISTORY_SAFE_BOTTOM  # 字幕区上方安全结束

        history_gap = 8  # 历史字幕间隙

        for i, item in enumerate(items):
            start = item["start"] + intro_offset  # 应用片头偏移
            if i + 1 < len(items):
                end = max(start + 0.05, items[i + 1]["start"] + intro_offset)
            else:
                end = item["end"] + 0.5 + intro_offset
            
            # 片尾效果：如果字幕开始时间超过subtitle_end_time，跳过该字幕
            if subtitle_end_time is not None and start >= subtitle_end_time:
                continue
                
            # 如果字幕结束时间超过subtitle_end_time，截断结束时间
            if subtitle_end_time is not None and end > subtitle_end_time:
                end = subtitle_end_time

            window_start = max(0, i - HISTORY_MAX_ROWS + 1)
            window = items[window_start: i + 1]

            visible_window: List[Dict] = []
            total_height = 0

            for hist in reversed(window):
                h = calc_history_block_height(hist)
                needed = h if not visible_window else h + history_gap
                if total_height + needed > (history_bottom_y - history_top_y):
                    break
                visible_window.append(hist)
                total_height += needed

            visible_window.reverse()

            current_y = history_top_y
            for hist in visible_window:
                # 获取分离的英文和中文历史文本
                en_text, zh_text = format_bilingual_block(
                    en_text=hist["en"],
                    zh_text=hist["zh"],
                    max_units_en=32.0,  # 从24.0增加到32.0，与calc_history_block_height保持一致
                    max_units_zh=24.0,  # 从20.0增加到24.0
                )

                # 英文历史：使用HistoryEn样式，更突出
                en_override = rf"{{\an8\pos({history_center_x},{current_y})}}{en_text}"
                en_line = f"Dialogue: 1,{ass_time(start)},{ass_time(end)},HistoryEn,,0,0,0,,{en_override}\n"
                f.write(en_line)

                # 中文历史：使用HistoryCn样式，更辅助（如果存在）
                if zh_text:
                    # 根据英文实际行数计算中文位置，避免覆盖
                    en_actual_height = calc_english_lines_height(en_text)
                    zh_y = current_y + en_actual_height + 8  # 英文高度 + 8px间距
                    zh_override = rf"{{\an8\pos({history_center_x},{zh_y})}}{zh_text}"
                    zh_line = f"Dialogue: 0,{ass_time(start)},{ass_time(end)},HistoryCn,,0,0,0,,{zh_override}\n"
                    f.write(zh_line)

                current_y += calc_history_block_height(hist) + history_gap

        # 生成分层双语字幕：英文突出，中文辅助
        for item in items:
            # 应用片头时间偏移
            adjusted_start = item["start"] + intro_offset
            adjusted_end = item["end"] + intro_offset
            start = ass_time(adjusted_start)
            end = ass_time(adjusted_end)
            
            # 获取分离的英文和中文字幕
            en_text, zh_text = build_bilingual_karaoke_ass_text(
                item["en"],
                item["zh"],
                item["duration"],
                keywords=keywords,
                max_units_en=32.0,  # 与历史字幕宽度保持一致
                max_units_zh=24.0,  # 与历史字幕宽度保持一致
            )
            
            # 英文字幕：Layer 3, EnglishMain样式，更突出，主要位置
            en_line = f"Dialogue: 3,{start},{end},EnglishMain,,0,0,0,,{en_text}\n"
            f.write(en_line)
            
            # 中文字幕：Layer 2, ChineseAux样式，辅助理解，下方位置（如果存在）
            if zh_text:
                # 中文字幕使用ChineseAux样式，通过MarginV定位在英文字幕下方
                zh_line = f"Dialogue: 2,{start},{end},ChineseAux,,0,0,0,,{zh_text}\n"
                f.write(zh_line)


def download_youtube_mp3(video_id: str, output_mp3: str) -> str:
    url = f"https://www.youtube.com/watch?v={video_id}"
    tmp_template = f"{video_id}.source.%(ext)s"

    subprocess.run(
        [
            "yt-dlp",
            "-f", "bestaudio",
            "-x",
            "--audio-format", "mp3",
            "-o", tmp_template,
            url,
        ],
        check=True,
    )

    matches = sorted(Path(".").glob(f"{video_id}.source*.mp3"))
    if not matches:
        raise RuntimeError("没有找到 yt-dlp 导出的 mp3 文件")

    source_mp3 = str(matches[0])
    if source_mp3 != output_mp3:
        shutil.move(source_mp3, output_mp3)
    return output_mp3


def create_default_cover(output_path: str) -> str:
    """
    创建默认封面图片（纯色背景）
    """
    try:
        # 尝试创建带文字的默认封面
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",  # Debian/Ubuntu
            "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",             # Arch Linux
            "/System/Library/Fonts/Arial.ttf",                     # macOS
            "/Windows/Fonts/arial.ttf",                            # Windows
        ]
        
        font_found = None
        for font_path in font_paths:
            if Path(font_path).exists():
                font_found = font_path
                break
        
        if font_found:
            cmd = [
                "ffmpeg", "-y", "-f", "lavfi",
                "-i", "color=0x1a1a2e:size=1080x1920",
                "-vf", f"drawtext=fontfile='{font_found}':text='LearnSubStudio':fontsize=60:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2:box=1:boxcolor=black@0.5:boxborderw=10",
                "-frames:v", "1", output_path
            ]
        else:
            # 如果找不到字体，创建纯色背景
            cmd = [
                "ffmpeg", "-y", "-f", "lavfi", 
                "-i", "color=0x1a1a2e:size=1080x1920",
                "-frames:v", "1", output_path
            ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0 and Path(output_path).exists():
            print(f"已创建默认封面图: {output_path}")
            return output_path
            
    except Exception as e:
        print(f"创建默认封面失败: {e}")
    
    # 最后的后备方案：抛出详细错误信息
    raise FileNotFoundError(
        f"无法创建默认封面图: {output_path}\n"
        f"请确保:\n"
        f"1. 设置了 UNSPLASH_ACCESS_KEY 环境变量，或\n"
        f"2. 提供了有效的本地图片文件路径（非目录）\n"
        f"3. FFmpeg 已正确安装并可用"
    )


def get_cover_image(output_path: str, query: str = "podcast studio", fallback_cover: str = "cover.jpg") -> str:
    access_key = os.environ.get("UNSPLASH_ACCESS_KEY", "").strip()

    if access_key:
        try:
            headers = {
                "Authorization": f"Client-ID {access_key}",
                "Accept-Version": "v1",
            }
            params = {
                "query": query,
                "orientation": "portrait",
                "content_filter": "high",
            }

            resp = requests.get(
                "https://api.unsplash.com/photos/random",
                headers=headers,
                params=params,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()

            image_url = data["urls"]["regular"]
            img_resp = requests.get(image_url, timeout=60)
            img_resp.raise_for_status()

            with open(output_path, "wb") as f:
                f.write(img_resp.content)

            print(f"已从 Unsplash 下载封面图: {output_path}")
            return output_path
        except Exception as e:
            print(f"Unsplash 下载失败，改用本地封面图。原因: {e}")

    fallback = Path(fallback_cover)
    
    # 检查fallback_cover是否有效
    if not fallback.exists():
        print(f"封面文件不存在: {fallback_cover}，创建默认封面图...")
        return create_default_cover(output_path)
    
    if fallback.is_dir():
        print(f"封面路径是目录而非文件: {fallback_cover}，创建默认封面图...")
        return create_default_cover(output_path)
    
    # 检查是否是支持的图片格式
    supported_formats = {'.jpg', '.jpeg', '.png', '.webp', '.bmp'}
    if fallback.suffix.lower() not in supported_formats:
        print(f"不支持的图片格式: {fallback.suffix}，创建默认封面图...")
        return create_default_cover(output_path)

    print(f"使用本地封面图: {fallback_cover}")
    return str(fallback)


def detect_hardware_decoder() -> str:
    """
    检测可用的硬件解码器，用于输入优化
    """
    decoders_to_test = [
        'cuda',          # NVIDIA CUDA解码
        'vaapi',         # Intel VAAPI解码
        'videotoolbox',  # Apple VideoToolbox解码
    ]
    
    for decoder in decoders_to_test:
        try:
            # 测试硬件解码器是否可用（使用较短的测试）
            result = subprocess.run([
                'ffmpeg', '-hide_banner', '-hwaccel', decoder, 
                '-f', 'lavfi', '-i', 'testsrc2=duration=0.1:size=320x240:rate=1',
                '-t', '0.1', '-f', 'null', '-'
            ], capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0:
                print(f"   🚀 检测到硬件解码器: {decoder}")
                return decoder
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            continue
    
    print("   💻 使用软件解码器")
    return 'none'


def detect_hardware_encoder() -> str:
    """
    检测可用的硬件编码器，优先级：NVIDIA > Intel > Apple > 软件编码
    """
    encoders_to_test = [
        ('h264_nvenc', 'NVIDIA NVENC'),     # NVIDIA GPU编码
        ('h264_qsv', 'Intel QuickSync'),    # Intel QuickSync
        ('h264_videotoolbox', 'Apple VideoToolbox'),  # macOS硬件编码
    ]
    
    for encoder, name in encoders_to_test:
        try:
            # 测试编码器是否可用
            result = subprocess.run([
                'ffmpeg', '-hide_banner', '-f', 'lavfi', '-i', 'testsrc2=duration=1:size=320x240:rate=1',
                '-c:v', encoder, '-t', '1', '-f', 'null', '-'
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                print(f"   🚀 检测到硬件编码器: {name} ({encoder})")
                return encoder
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            continue
    
    print("   💻 使用软件编码器: libx264")
    return 'libx264'


def get_optimal_threads() -> str:
    """
    获取最佳线程数：CPU核心数，最大16
    """
    import os
    try:
        cpu_count = os.cpu_count() or 4
        optimal_threads = min(cpu_count, 16)  # 限制最大16线程，避免过度占用
        print(f"   ⚡ 优化线程数: {optimal_threads} (CPU核心数: {cpu_count})")
        return str(optimal_threads)
    except:
        print("   ⚡ 使用默认线程数: 4")
        return "4"


def build_video(
    cover_jpg: str,
    audio_mp3: str,
    ass_path: str,
    output_mp4: str,
    video_title: str,
    subtitle_lines: List[str],
    show_bars: bool = DEFAULT_SHOW_BARS,
    show_intro: bool = False,
    show_outro: bool = True,  # 默认启用片尾效果
    content_type: str = 'mixed',
    intro_duration: float = 1.5,
    outro_duration: float = 2.0,
) -> None:
    wrapped_title = wrap_title_for_mobile(video_title, max_units_per_line=30.0, max_lines=3)  # 40号字体支持更长标题，确保完整显示
    safe_title = sanitize_drawtext_text(wrapped_title)
    safe_ass = ffmpeg_escape_path(str(Path(ass_path).resolve()))
    safe_fontfile = ffmpeg_escape_path(TITLE_FONTFILE)

    cleaned_subtitle_lines = [clean_text(x) for x in subtitle_lines if clean_text(x)]
    subtitle_text = sanitize_drawtext_text("\n".join(cleaned_subtitle_lines[:3])) if cleaned_subtitle_lines else ""

    probe = subprocess.run(
        [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            audio_mp3,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    duration = float(probe.stdout.strip())
    if show_outro:
        # 片尾效果：字幕在原音频结束时停止，然后播放outro_duration的片尾
        video_total_duration = duration + outro_duration
        subtitle_end_time = duration  # 字幕在原音频结束时结束
        outro_start_time = duration   # 片尾从原音频结束时开始
    else:
        # 无片尾：视频时长等于音频时长
        video_total_duration = duration
        outro_start_time = duration  # 用于判断，但实际不会用到

    if show_bars:
        # 获取智能音频可视化参数
        viz_params = get_audio_visualization_params(content_type)
        showfreqs_params = f"s={viz_params['size']}:mode={viz_params['mode']}:ascale={viz_params['ascale']}:fscale={viz_params['fscale']}:colors={viz_params['colors']}"
        
        # 短视频安全区频谱位置 - 确保不被底部UI遮挡
        spectrum_y_offset = SPECTRUM_SAFE_Y
        # 不同类型的频谱可能有不同高度，需要相应调整
        if content_type == 'music':
            spectrum_y_offset -= 20  # 音乐类频谱更高，需要稍微上移
        elif content_type == 'speech':
            spectrum_y_offset += 10  # 讲话类频谱较低，可以稍微下移
            
        overlay_y = str(spectrum_y_offset)
        
        filter_complex = (
            f"[0:v]"
            f"scale={VIDEO_W}:{VIDEO_H}:force_original_aspect_ratio=increase,"
            f"crop={VIDEO_W}:{VIDEO_H},"
            f"setsar=1,"
            f"zoompan=z='min(1.15,1+on/2500)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"s={VIDEO_W}x{VIDEO_H}:fps=25[bg];"

            "[1:a]"
            "aformat=channel_layouts=stereo,"
            f"showfreqs={showfreqs_params},"
            "format=rgba"
        )
        
        # 只有启用片尾时才添加柱状图淡出效果
        if show_outro:
            filter_complex += f",fade=t=out:st={outro_start_time}:d={outro_duration}[bars];"
        else:
            filter_complex += "[bars];"
        
        filter_complex += (

            "[bg][bars]"
            f"overlay=(W-w)/2:{overlay_y}[tmp1];"

            f"[tmp1]drawtext="
            f"fontfile='{safe_fontfile}':"
            f"text='{safe_title}':"
            f"fontcolor=#FF6600:"  # 使用十六进制橙色值
            f"fontsize=40:"  # 从48减小到40，确保标题不会超出边界
            f"line_spacing=15:"  # 调整行间距，适应40号字体
            f"box=1:"
            f"boxcolor=black@0.45:"
            f"boxborderw=20:"
            f"x=(w-text_w)/2:"
            f"y={TITLE_SAFE_Y}[tmp2];"  # 使用短视频安全区位置
        )
    else:
        filter_complex = (
            f"[0:v]"
            f"scale={VIDEO_W}:{VIDEO_H}:force_original_aspect_ratio=increase,"
            f"crop={VIDEO_W}:{VIDEO_H},"
            f"setsar=1,"
            f"zoompan=z='min(1.15,1+on/2500)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"s={VIDEO_W}x{VIDEO_H}:fps=25[bg];"

            f"[bg]drawtext="
            f"fontfile='{safe_fontfile}':"
            f"text='{safe_title}':"
            f"fontcolor=#FF6600:"  # 使用十六进制橙色值
            f"fontsize=40:"  # 从48减小到40，确保标题不会超出边界
            f"line_spacing=15:"  # 调整行间距，适应40号字体
            f"box=1:"
            f"boxcolor=black@0.45:"
            f"boxborderw=20:"
            f"x=(w-text_w)/2:"
            f"y={TITLE_SAFE_Y}[tmp2];"  # 使用短视频安全区位置
        )

    if subtitle_text:
        filter_complex += (
            f"[tmp2]drawtext="
            f"fontfile='{safe_fontfile}':"
            f"text='{subtitle_text}':"
            f"fontcolor=white:"
            f"fontsize=24:"
            f"line_spacing=12:"
            f"box=1:"
            f"boxcolor=black@0.30:"
            f"boxborderw=12:"
            f"x=(w-text_w)/2:"
            f"y={SUMMARY_SAFE_Y}[tmp3];"  # 摘要安全区位置
        )
        ass_input = "[tmp3]"
    else:
        ass_input = "[tmp2]"

    # 处理片头和字幕
    if show_intro:
        # 有片头：添加片头提示文字，字幕延后显示
        intro_text = "LearnSubStudio"
        safe_intro_text = sanitize_drawtext_text(intro_text)
        
        filter_complex += (
            # 先添加片头文字（在指定时间段显示）
            f"{ass_input}drawtext="
            f"fontfile='{safe_fontfile}':"
            f"text='{safe_intro_text}':"
            f"fontcolor=#FF6600:"
            f"fontsize=32:"
            f"box=1:"
            f"boxcolor=black@0.6:"
            f"boxborderw=15:"
            f"x=(w-text_w)/2:"
            f"y=(h-text_h)/2+200:"  # 在中心下方显示
            f"enable='between(t,0.2,{intro_duration-0.2})'[intro_added];"
            
            # 然后添加字幕（延后显示）
            f"[intro_added]ass='{safe_ass}':force_style='PlayResX={VIDEO_W},PlayResY={VIDEO_H}'[subtitled];"
            
            # 只添加淡入效果，不添加全画面淡出（片尾保留背景和标题）
            f"[subtitled]fade=t=in:st=0:d=0.5[v]"
        )
    else:
        # 无片头：直接显示字幕，片尾保留背景和标题
        filter_complex += (
            f"{ass_input}ass='{safe_ass}'"
            f",fade=t=in:st=0:d={intro_duration}[v]"
        )

    # 检测最佳编码参数
    print("🚀 优化编码参数...")
    hardware_decoder = detect_hardware_decoder()
    video_encoder = detect_hardware_encoder()
    threads_count = get_optimal_threads()
    
    # 根据编码器类型设置参数
    if video_encoder == 'libx264':
        # 软件编码参数（保持质量）
        codec_params = [
            "-c:v", "libx264",
            "-preset", "superfast",  # 快速预设
            "-crf", "26",           # 保持原质量
            "-threads", threads_count,  # 多线程优化
        ]
    elif 'nvenc' in video_encoder:
        # NVIDIA硬件编码参数
        codec_params = [
            "-c:v", video_encoder,
            "-preset", "p4",        # 快速预设 (p1=fastest, p7=slowest)
            "-cq", "26",           # 对应软件编码的CRF 26
            "-b:v", "0",           # VBR模式
        ]
    elif 'qsv' in video_encoder:
        # Intel硬件编码参数
        codec_params = [
            "-c:v", video_encoder,
            "-preset", "faster",    # 快速预设
            "-global_quality", "26", # 对应CRF 26
        ]
    elif 'videotoolbox' in video_encoder:
        # Apple硬件编码参数
        codec_params = [
            "-c:v", video_encoder,
            "-q:v", "65",          # 质量参数 (对应CRF 26)
            "-realtime", "0",      # 非实时编码，更好质量
        ]
    else:
        # 默认软件编码
        codec_params = [
            "-c:v", "libx264",
            "-preset", "superfast",
            "-crf", "26",
            "-threads", threads_count,
        ]

    # 根据是否启用片尾来处理音频
    if show_outro:
        # 创建扩展后的音频（原音频 + 片尾静音）
        extended_audio_filter = (
            f"[1:a]apad=pad_dur={outro_duration}[extended_audio]"
        )
        filter_complex = extended_audio_filter + ";" + filter_complex
        audio_map = "[extended_audio]"
    else:
        # 无片尾：直接使用原音频
        audio_map = "1:a"
    
    # 构建FFmpeg命令
    ffmpeg_cmd = [
        "ffmpeg",
        "-y",
    ]
    
    # 根据检测结果添加硬件解码参数
    if hardware_decoder != 'none':
        ffmpeg_cmd.extend(["-hwaccel", hardware_decoder])
    
    ffmpeg_cmd.extend([
        # 输入文件
        "-loop", "1",
        "-i", cover_jpg,
        "-i", audio_mp3,
        # 滤镜处理
        "-filter_complex", filter_complex,
        "-map", "[v]",
        "-map", audio_map,
        # 时长控制
        "-t", str(video_total_duration),
        # 帧率设置
        "-r", "25",
    ] + codec_params + [
        # 像素格式
        "-pix_fmt", "yuv420p",
        # 音频编码优化
        "-c:a", "aac", 
        "-b:a", "160k",
        "-ac", "2",               # 强制立体声
        # 输出优化
        "-movflags", "+faststart", # Web优化，快速启动
        "-max_muxing_queue_size", "1024",  # 增大缓冲区
        output_mp4,
    ])
    
    print("   📹 开始视频编码...")
    print(f"   📥 解码器: {hardware_decoder if hardware_decoder != 'none' else '软件解码'}")
    print(f"   🔧 编码器: {video_encoder}")
    print(f"   ⚡ 线程数: {threads_count}")
    print(f"   📏 总时长: {video_total_duration:.1f}s")
    
    subprocess.run(ffmpeg_cmd, check=True)


def main() -> None:
    # 记录总开始时间
    import time
    total_start_time = time.time()
    step_times = {}  # 记录每个步骤的耗时
    current_step_start = None
    
    def start_step(step_name: str):
        """开始记录步骤时间"""
        nonlocal current_step_start
        current_step_start = time.time()
        
    def end_step(step_name: str):
        """结束步骤并记录耗时"""
        if current_step_start is not None:
            elapsed = time.time() - current_step_start
            step_times[step_name] = elapsed
            print(f"   ⏱️  耗时: {elapsed:.2f}秒")
    
    # 显示法律警告
    print("=" * 70)
    print("⚠️  重要法律提示")
    print("=" * 70)
    print("本工具仅供个人学习和非商业研究用途！")
    print("使用本工具处理YouTube内容可能涉及版权问题。")
    print("用户必须遵守当地法律法规并自行承担法律责任。")
    print("详细法律信息请查看 README.md 中的法律声明。")
    print("=" * 70)
    print()
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(
        prog='build_from_video_id.py',
        description='LearnSubStudio - 生成双语字幕学习视频',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 基础使用
  python build_from_video_id.py QqeECC13HcM

  # 使用完整YouTube URL
  python build_from_video_id.py "https://www.youtube.com/watch?v=QqeECC13HcM"

  # 友好的命名参数方式（推荐）
  python build_from_video_id.py QqeECC13HcM --cover tech.jpg --summary "学习AI技术" --show-intro

  # 自定义封面和摘要
  python build_from_video_id.py QqeECC13HcM --query "tech background" --cover my_cover.jpg --summary "深度学习教程"
  
  # 启用所有功能
  python build_from_video_id.py QqeECC13HcM --show-bars --show-intro --show-outro
  
  # 自定义输出路径
  python build_from_video_id.py QqeECC13HcM --output /path/to/output/video.mp4
  python build_from_video_id.py QqeECC13HcM --output ./videos/  # 输出到指定目录
  
  # 保留中间文件
  python build_from_video_id.py QqeECC13HcM --keep-temp --summary "学习材料"
  
  # 完整功能示例（自定义路径+保留文件）
  python build_from_video_id.py QqeECC13HcM --output ./videos/ai_tutorial.mp4 --keep-temp --show-intro

注意: 同时支持新的命名参数方式和旧的位置参数方式（向后兼容）
默认会自动清理中间文件(.mp3, .txt, .ass等)，只保留最终的.mp4视频文件
        """
    )
    
    # 必需参数
    parser.add_argument('video_input', nargs='?',
                       help='YouTube视频ID或完整URL（如: QqeECC13HcM 或 https://www.youtube.com/watch?v=xxx）')
    
    # 可选参数 - 内容设置
    parser.add_argument('--query', '-q', 
                       default='podcast studio',
                       help='Unsplash封面搜索词 (默认: "podcast studio")')
    
    parser.add_argument('--cover', '-c',
                       default='cover.jpg', 
                       help='本地封面图片路径，支持jpg/png/webp/bmp格式 (默认: "cover.jpg")')
    
    parser.add_argument('--summary', '-s',
                       default='',
                       help='自定义摘要文本，留空则不显示摘要')
    
    # 功能开关
    parser.add_argument('--show-bars', '-b',
                       action='store_true',
                       help='显示音频频谱图（自动检测：音乐类启用，讲话类关闭）')
    
    parser.add_argument('--no-bars',
                       action='store_true', 
                       help='强制关闭频谱图显示')
    
    parser.add_argument('--show-intro', '-i',
                       action='store_true',
                       help='显示1.5秒片头效果 (默认: false)')
    
    
    parser.add_argument('--no-outro',
                       action='store_true',
                       help='关闭2秒片尾效果 (默认显示片尾)')
    
    parser.add_argument('--show-outro', '-o',
                       action='store_true',
                       help='显示2秒优雅片尾效果 (默认: true)')
    
    # 输出设置
    parser.add_argument('--output', '--out',
                       default='',
                       help='指定输出MP4文件路径 (默认: 当前目录下以视频ID命名)')
    
    parser.add_argument('--keep-temp',
                       action='store_true',
                       help='保留中间文件 (.mp3, .txt, .ass等) (默认: 自动清理)')
    
    parser.add_argument('--clean-temp',
                       action='store_true',
                       help='强制清理中间文件 (默认: true)')

    # 检查是否使用旧的位置参数方式（向后兼容）
    if len(sys.argv) >= 2 and not sys.argv[1].startswith('-'):
        # 检查是否看起来像旧的位置参数方式
        looks_like_old_format = (
            len(sys.argv) > 2 and 
            not any(arg.startswith('-') for arg in sys.argv[2:])  # 没有任何命名参数
        )
        
        if looks_like_old_format:
            print("🔄 检测到旧的位置参数格式，自动兼容处理...")
            print("💡 建议使用新的命名参数方式，更清晰易懂！")
            print("   示例: python build_from_video_id.py VIDEO_ID --show-intro")
            print()
        
        # 兼容旧格式的参数解析将在下面处理
    
    # 如果没有提供参数，显示帮助信息
    if len(sys.argv) < 2:
        parser.print_help()
        sys.exit(1)

    ensure_cmd("ffmpeg")
    ensure_cmd("ffprobe")
    ensure_cmd("yt-dlp")

    # 检查是否使用旧的位置参数方式（向后兼容）
    if len(sys.argv) >= 2 and not sys.argv[1].startswith('-'):
        # 单个参数或多个位置参数（没有命名参数）视为旧格式
        looks_like_old_format = (
            len(sys.argv) == 2 or  # 只有video_id
            (len(sys.argv) > 2 and not any(arg.startswith('-') for arg in sys.argv[2:]))
        )
        
        if looks_like_old_format:
            # 使用旧的解析方式
            try:
                video_id = extract_video_id_from_url(sys.argv[1])
                print(f"✅ 解析得到video_id: {video_id}")
            except ValueError as e:
                print(f"❌ 错误: {e}")
                print("请提供有效的YouTube视频ID或URL")
                sys.exit(1)
            
            unsplash_query = sys.argv[2].strip() if len(sys.argv) >= 3 else "podcast studio"
            fallback_cover = sys.argv[3].strip() if len(sys.argv) >= 4 else "cover.jpg"
            show_bars = parse_bool_arg(sys.argv[4]) if len(sys.argv) >= 5 else DEFAULT_SHOW_BARS
            custom_summary = sys.argv[5].strip() if len(sys.argv) >= 6 else ""
            show_intro = parse_bool_arg(sys.argv[6]) if len(sys.argv) >= 7 else False
            show_outro = parse_bool_arg(sys.argv[8]) if len(sys.argv) >= 9 else True
            output_path = ''  # 旧格式不支持自定义输出路径
            keep_temp = False  # 旧格式默认清理中间文件
        else:
            # 使用新的argparse方式
            args = parser.parse_args()
            
            if not args.video_input:
                print("❌ 错误: 必须提供YouTube视频ID或URL")
                parser.print_help()
                sys.exit(1)
                
            try:
                video_id = extract_video_id_from_url(args.video_input)
                print(f"✅ 解析得到video_id: {video_id}")
            except ValueError as e:
                print(f"❌ 错误: {e}")
                print("请提供有效的YouTube视频ID或URL")
                sys.exit(1)
            
            unsplash_query = args.query
            fallback_cover = args.cover
            custom_summary = args.summary
            show_intro = args.show_intro
            show_outro = not args.no_outro  # 默认true，除非显式关闭
            output_path = args.output.strip() if args.output else ''
            keep_temp = args.keep_temp
            
            # 处理show_bars逻辑
            if args.no_bars:
                show_bars = False
            elif args.show_bars:
                show_bars = True
            else:
                show_bars = DEFAULT_SHOW_BARS  # 使用自动检测
    else:
        # 使用新的argparse方式
        args = parser.parse_args()
        
        if not args.video_input:
            print("❌ 错误: 必须提供YouTube视频ID或URL")
            parser.print_help()
            sys.exit(1)
            
        try:
            video_id = extract_video_id_from_url(args.video_input)
            print(f"✅ 解析得到video_id: {video_id}")
        except ValueError as e:
            print(f"❌ 错误: {e}")
            print("请提供有效的YouTube视频ID或URL")
            sys.exit(1)
        
        unsplash_query = args.query
        fallback_cover = args.cover
        custom_summary = args.summary
        show_intro = args.show_intro
        show_outro = not args.no_outro
        output_path = args.output.strip() if args.output else ''
        keep_temp = args.keep_temp
        
        # 处理show_bars逻辑
        if args.no_bars:
            show_bars = False
        elif args.show_bars:
            show_bars = True
        else:
            show_bars = DEFAULT_SHOW_BARS

    base = video_id
    
    # 处理输出路径
    if output_path:
        # 用户指定了输出路径
        output_path_obj = Path(output_path)
        
        if output_path.endswith('/') or output_path.endswith('\\') or output_path_obj.is_dir():
            # 用户指定了目录，使用视频ID作为文件名
            mp4_path = str(output_path_obj / f"{base}.mp4")
        else:
            # 用户指定了完整路径
            if output_path_obj.suffix.lower() != '.mp4':
                # 如果没有扩展名或不是.mp4，添加.mp4
                output_path_obj = output_path_obj.with_suffix('.mp4')
            mp4_path = str(output_path_obj)
        
        # 确保输出目录存在
        Path(mp4_path).parent.mkdir(parents=True, exist_ok=True)
        print(f"📁 自定义输出路径: {mp4_path}")
    else:
        # 默认输出到当前目录
        mp4_path = f"{base}.mp4"
        print(f"📁 默认输出路径: {mp4_path}")
    
    # 中间文件路径（始终在当前目录）
    ass_path = f"{base}.ass"
    txt_path = f"{base}.txt"
    mp3_path = f"{base}.mp3"
    downloaded_cover_path = f"{base}.cover.jpg"
    
    # 中间文件清理设置
    clean_temp_files = not keep_temp  # 默认清理，除非用户要求保留
    if clean_temp_files:
        print("🧹 设置: 完成后自动清理中间文件")
    else:
        print("📁 设置: 保留所有中间文件")

    # 显示短视频安全区布局信息
    print_safe_area_layout()
    print()
    
    print("1/8 获取英文字幕...")
    start_step("获取英文字幕")
    items = fetch_transcript(video_id, lang="en")
    items = merge_short_items(items)
    end_step("获取英文字幕")

    print("2/8 翻译中文字幕...")
    start_step("翻译中文字幕")
    bilingual_items = build_bilingual_items_with_libretranslate(items)
    end_step("翻译中文字幕")

    print("3/8 生成字幕和文本...")
    start_step("生成字幕和文本")
    keywords = extract_keywords(items, top_n=8)
    chapters = build_chapter_markers(bilingual_items, sections=3)
    # 如果启用片头，字幕需要延后显示
    intro_offset_time = 1.5 if show_intro else 0.0  # 片头时长1.5秒
    # 先用None作为subtitle_end_time，在音频下载后重新生成字幕
    write_ass_karaoke(bilingual_items, ass_path, keywords, chapters, show_bars=show_bars, intro_offset=intro_offset_time, subtitle_end_time=None)

    english_items_for_text = [
        {
            "text": item["en"],
            "start": item["start"],
            "duration": item["duration"],
            "end": item["end"],
        }
        for item in bilingual_items
    ]
    text = build_text(english_items_for_text)
    Path(txt_path).write_text(text, encoding="utf-8")
    end_step("生成字幕和文本")

    print("4/8 获取标题...")
    start_step("获取标题")
    video_title = get_youtube_title(video_id)
    
    # 处理摘要：如果用户提供了自定义摘要，使用自定义的；否则不添加摘要
    if custom_summary:
        print("   使用自定义摘要...")
        zh_bullets = [f"• {custom_summary}"]
    else:
        print("   跳过摘要生成（默认不添加摘要）")
        zh_bullets = []
    end_step("获取标题")

    print("5/8 下载音频...")
    start_step("下载音频")
    download_youtube_mp3(video_id, mp3_path)
    end_step("下载音频")

    print("6/8 智能音频分析...")
    start_step("智能音频分析")
    # 总是进行音频类型检测，用于自动决定是否显示柱状图
    content_type = detect_audio_content_type(bilingual_items)
    print(f"   检测到音频类型: {content_type}")
    
    # 基于内容类型自动决定是否显示柱状图
    auto_show_bars = auto_detect_show_bars(content_type)
    
    # 用户可以通过参数覆盖自动检测结果
    user_specified_bars = False
    
    # 检查旧的位置参数格式
    if len(sys.argv) >= 5 and sys.argv[4].strip().lower() in ['true', 'false']:
        user_specified_bars = True
    
    # 检查新的命名参数格式
    if '--show-bars' in sys.argv or '--no-bars' in sys.argv or '-b' in sys.argv:
        user_specified_bars = True
    
    if user_specified_bars:
        # 用户明确指定了show_bars参数
        show_bars_final = show_bars
        print(f"   柱状图显示: {show_bars_final} (用户指定)")
    else:
        # 使用自动检测结果
        show_bars_final = auto_show_bars
        print(f"   柱状图显示: {show_bars_final} (自动检测)")
    
    type_descriptions = {
        'speech': '讲话类 - 专注内容，无视觉干扰',
        'music': '音乐类 - 强烈频谱效果，增强律动', 
        'mixed': '混合类 - 平衡频谱效果，视觉丰富'
    }
    bar_status = "启用频谱图" if show_bars_final else "关闭频谱图"
    print(f"   视觉效果: {type_descriptions.get(content_type, '标准效果')} - {bar_status}")
    
    # 如果智能检测结果与初始设置不同，需要重新生成字幕文件
    if show_bars_final != show_bars:
        print(f"   🔄 智能检测结果与初始设置不同，重新生成字幕文件...")
        write_ass_karaoke(bilingual_items, ass_path, keywords, chapters, show_bars=show_bars_final, intro_offset=intro_offset_time, subtitle_end_time=None)
    end_step("智能音频分析")

    print("7/8 优化字幕时间...")
    start_step("优化字幕时间")
    # 如果启用片尾效果，需要重新生成字幕文件以限制字幕显示时间
    if show_outro:
        print("   🎭 计算片尾时间，重新生成字幕...")
        probe = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                mp3_path,
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        audio_duration = float(probe.stdout.strip())
        # 片尾效果：字幕在原音频结束时停止显示
        subtitle_end_time = audio_duration + intro_offset_time
        
        # 重新生成字幕文件，这次带有准确的结束时间
        write_ass_karaoke(bilingual_items, ass_path, keywords, chapters, show_bars=show_bars_final, intro_offset=intro_offset_time, subtitle_end_time=subtitle_end_time)
        print(f"   字幕将在 {subtitle_end_time:.1f}秒 时停止显示，然后播放2秒片尾")
    else:
        print("   跳过片尾时间优化（片尾效果未启用）")
    end_step("优化字幕时间")

    print("8/8 合成视频...")
    start_step("合成视频")
    final_cover_path = get_cover_image(
        output_path=downloaded_cover_path,
        query=unsplash_query,
        fallback_cover=fallback_cover,
    )
    
    build_video(
        final_cover_path,
        mp3_path,
        ass_path,
        mp4_path,
        video_title,
        zh_bullets,
        show_bars=show_bars_final,
        show_intro=show_intro,
        show_outro=show_outro,
        content_type=content_type,
    )
    
    # 计算编码速度（如果有视频时长信息）
    try:
        probe = subprocess.run([
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", mp4_path
        ], capture_output=True, text=True)
        if probe.returncode == 0:
            video_duration = float(probe.stdout.strip())
            encoding_elapsed = step_times.get("合成视频", 0) if "合成视频" not in step_times else time.time() - current_step_start
            if encoding_elapsed > 0:
                speed_ratio = video_duration / encoding_elapsed
                print(f"   🚀 编码速度: {speed_ratio:.1f}x 实时速度")
    except:
        pass
    
    end_step("合成视频")

    # 显示详细耗时统计
    total_elapsed_time = time.time() - total_start_time
    print("\n" + "=" * 70)
    print("🕒 详细耗时统计")
    print("=" * 70)
    for i, (step_name, elapsed) in enumerate(step_times.items(), 1):
        percentage = (elapsed / total_elapsed_time * 100) if total_elapsed_time > 0 else 0
        print(f"{i}. {step_name:<20} {elapsed:>8.2f}秒 ({percentage:>5.1f}%)")
    
    print("-" * 70)
    print(f"   {'总耗时':<20} {total_elapsed_time:>8.2f}秒 (100.0%)")
    print("=" * 70)
    
    print("\n✅ 处理完成！")
    
    # 清理中间文件
    if clean_temp_files:
        print("\n🧹 清理中间文件...")
        temp_files = [ass_path, txt_path, mp3_path, downloaded_cover_path]
        cleaned_count = 0
        
        for temp_file in temp_files:
            try:
                if Path(temp_file).exists():
                    Path(temp_file).unlink()
                    print(f"   ✅ 已删除: {temp_file}")
                    cleaned_count += 1
            except Exception as e:
                print(f"   ⚠️  删除失败: {temp_file} - {e}")
        
        if cleaned_count > 0:
            print(f"   🎯 成功清理 {cleaned_count} 个中间文件")
        else:
            print("   📝 无中间文件需要清理")
    
    print(f"\n📁 最终输出文件：")
    if clean_temp_files:
        print(f"   🎬 视频文件: {mp4_path}")
    else:
        print(f"   📄 字幕文件: {ass_path}")
        print(f"   📝 文本文件: {txt_path}")
        print(f"   🎵 音频文件: {mp3_path}")
        print(f"   🖼️  封面文件: {downloaded_cover_path}")
        print(f"   🎬 视频文件: {mp4_path}")
    print("=" * 70)
    print("⚖️  法律提醒")
    print("=" * 70)
    print("生成的内容仅供个人学习使用，请勿：")
    print("• 用于商业目的")
    print("• 公开分发或上传")
    print("• 侵犯原作者版权")
    print("请遵守当地法律法规，尊重原创者权益。")
    print("=" * 70)


if __name__ == "__main__":
    main()