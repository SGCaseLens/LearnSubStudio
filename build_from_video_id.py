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
CHAPTER_SAFE_Y = SAFE_AREA_TOP - 10      # 章节安全位置：150px（在标题上方）
TITLE_SAFE_Y = SAFE_AREA_TOP + 40        # 标题安全位置：200px
SUMMARY_SAFE_Y = SAFE_AREA_TOP + 120     # 摘要安全位置：280px  
HISTORY_SAFE_TOP = SAFE_AREA_TOP + 200   # 历史区域顶部：360px
HISTORY_SAFE_BOTTOM = VIDEO_H - SAFE_AREA_BOTTOM - 380  # 历史区域底部：1260px
SPECTRUM_SAFE_Y = VIDEO_H - SAFE_AREA_BOTTOM - 440     # 频谱安全位置：1200px
SUBTITLE_SAFE_Y = VIDEO_H - SAFE_AREA_BOTTOM - 120     # 字幕安全位置：1520px

# 📱 平台定制配置 - 针对不同短视频平台的视觉优化
PLATFORM_CONFIGS = {
    'xiaohongshu': {
        'name': '小红书',
        'description': '清新文艺风格，适合生活化学习内容',
        'colors': {
            'primary': '&H00FF6B6B&',      # 小红书红：温暖亲和
            'secondary': '&H00FFB347&',    # 暖橙色：活力青春
            'accent': '&H004ECDC4&',       # 薄荷绿：清新自然
            'background': '&H00F8F8F8&',   # 浅灰背景：简约干净
            'text': '&H00333333&',         # 深灰文字：温和易读
        },
        'font_style': {
            'main_weight': 'normal',        # 非粗体：柔和亲切
            'accent_italic': True,          # 斜体强调：手写感
            'rounded_corners': True,        # 圆角效果：可爱风格
        },
        'visual_elements': {
            'soft_shadows': True,           # 柔和阴影：质感提升
            'pastel_highlights': True,      # 马卡龙色彩：梦幻感
            'handwriting_style': True,      # 手写风格：个人化
        },
        'content_tone': '生活化、亲切、实用'
    },
    
    'tiktok': {
        'name': 'TikTok',
        'description': '年轻动感风格，适合快节奏学习内容',
        'colors': {
            'primary': '&H00FF0050&',      # TikTok粉：年轻活力
            'secondary': '&H0000F5FF&',    # 霓虹黄：时尚潮流
            'accent': '&H00FF6EC7&',       # 亮紫色：个性张扬
            'background': '&H00000000&',   # 纯黑背景：对比强烈
            'text': '&H00FFFFFF&',         # 纯白文字：清晰醒目
        },
        'font_style': {
            'main_weight': 'bold',          # 粗体：强烈冲击
            'accent_italic': False,         # 直体：干净利落
            'rounded_corners': False,       # 直角：锐利现代
        },
        'visual_elements': {
            'neon_glow': True,              # 霓虹发光：科技感
            'pulse_animation': True,        # 脉冲动画：动态节奏
            'gradient_text': True,          # 渐变文字：时尚效果
        },
        'content_tone': '快节奏、年轻化、国际范'
    },
    
    'douyin': {
        'name': '抖音',
        'description': '本土化风格，适合中文学习内容',
        'colors': {
            'primary': '&H000080FF&',      # 抖音红：热情奔放
            'secondary': '&H0000CCFF&',    # 金橙色：温暖亲民
            'accent': '&H00FF6600&',       # 活力橙：积极向上
            'background': '&H001a1a1a&',   # 深灰背景：沉稳大气
            'text': '&H00FFFFFF&',         # 白色文字：清晰明亮
        },
        'font_style': {
            'main_weight': 'bold',          # 粗体：强调重点
            'accent_italic': False,         # 直体：正式规范
            'rounded_corners': True,        # 圆角：友好亲切
        },
        'visual_elements': {
            'chinese_elements': True,       # 中国风元素：文化认同
            'warm_lighting': True,          # 暖色调：温馨感
            'traditional_accent': True,     # 传统装饰：文化底蕴
        },
        'content_tone': '接地气、实用性、中国特色'
    },
    
    'instagram': {
        'name': 'Instagram',
        'description': '高端质感风格，适合精品学习内容',
        'colors': {
            'primary': '&H00E1306C&',      # Instagram紫：优雅神秘
            'secondary': '&H00405DE6&',    # 蓝紫色：高级质感
            'accent': '&H00FFDC80&',       # 香槟金：奢华品质
            'background': '&H00F5F5F5&',   # 高级灰：简约高端
            'text': '&H002C2C2C&',         # 炭黑色：专业严谨
        },
        'font_style': {
            'main_weight': 'medium',        # 中等粗细：平衡美感
            'accent_italic': True,          # 斜体：艺术气息
            'rounded_corners': False,       # 直角：现代简约
        },
        'visual_elements': {
            'minimal_design': True,         # 极简设计：高级感
            'subtle_gradients': True,       # 微妙渐变：层次丰富
            'professional_layout': True,    # 专业布局：商务范
        },
        'content_tone': '高质量、国际化、专业性'
    },
    
    'universal': {
        'name': '通用',
        'description': '平衡各平台特点的通用风格',
        'colors': {
            'primary': '&H00FF9900&',      # 通用橙：活力友好
            'secondary': '&H0066CCFF&',    # 蓝色：专业可信
            'accent': '&H0099FF66&',       # 绿色：清新积极
            'background': '&H00F0F0F0&',   # 中性灰：适应性强
            'text': '&H00444444&',         # 深灰：可读性佳
        },
        'font_style': {
            'main_weight': 'normal',        # 标准粗细：通用性好
            'accent_italic': False,         # 直体：兼容性强
            'rounded_corners': True,        # 圆角：友好通用
        },
        'visual_elements': {
            'balanced_design': True,        # 平衡设计：适应各平台
            'cross_platform': True,        # 跨平台优化：兼容性
            'flexible_layout': True,       # 灵活布局：适应性强
        },
        'content_tone': '平衡、通用、适应性强'
    }
}

DEFAULT_LIBRETRANSLATE_ENDPOINT = os.environ.get(
    "LIBRETRANSLATE_ENDPOINT",
    "http://127.0.0.1:5000/translate",
)
DEFAULT_LIBRETRANSLATE_API_KEY = os.environ.get("LIBRETRANSLATE_API_KEY", "").strip() or None
TRANSLATION_CACHE_FILE = "translation_cache.json"

# 智能字体检测 - 优先使用Ubuntu字体，回退到系统最佳字体
def detect_best_font():
    """检测系统中最佳可用字体，优先Ubuntu字体"""
    import platform
    
    system = platform.system()
    font_candidates = []
    
    if system == "Darwin":  # macOS
        font_candidates = [
            ("/usr/local/share/fonts/Ubuntu-Regular.ttf", "Ubuntu"),  # Homebrew安装
            ("/System/Library/Fonts/Ubuntu-Regular.ttf", "Ubuntu"),
            ("/System/Library/Fonts/Helvetica.ttc", "Helvetica"),
            ("/System/Library/Fonts/Avenir.ttc", "Avenir"),
        ]
    elif system == "Linux":
        font_candidates = [
            ("/usr/share/fonts/truetype/ubuntu/Ubuntu-Regular.ttf", "Ubuntu"),  # 首选Ubuntu
            ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", "Noto Sans CJK SC"),  # 中文支持
            ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "DejaVu Sans"),
            ("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", "Liberation Sans"),
        ]
    else:  # Windows
        font_candidates = [
            ("C:/Windows/Fonts/Ubuntu-R.ttf", "Ubuntu"),
            ("C:/Windows/Fonts/arial.ttf", "Arial"),
            ("C:/Windows/Fonts/calibri.ttf", "Calibri"),
        ]
    
    # 检测第一个可用的字体
    for font_path, font_name in font_candidates:
        if os.path.exists(font_path):
            return font_path, font_name
    
    # 如果都没找到，使用默认回退
    return "/System/Library/Fonts/Helvetica.ttc", "Helvetica"

# 自动检测并设置字体
TITLE_FONTFILE, ASS_FONT_NAME = detect_best_font()

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


def fix_english_contractions(text: str) -> str:
    """
    修复英文缩写词中单引号后的异常空格
    例如: "how' s" → "how's", "you' re" → "you're"
    """
    if not text:
        return text
    
    # 使用通用的正则表达式模式来捕获所有可能的缩写形式
    # 这比逐个列举更加全面和可靠
    
    # 第一步：修复基本的单引号+空格+字母模式
    # 匹配：单词边界 + 单引号 + 一个或多个空白字符 + 1-3个字母 + 单词边界
    text = re.sub(r"\b(\w+)'\s+([a-zA-Z]{1,3})\b", r"\1'\2", text)
    
    # 第二步：处理其他可能的空白字符（制表符、不间断空格等）
    text = re.sub(r"\b(\w+)'[\s\u00A0\u2000-\u200B\u2028\u2029]+([a-zA-Z]{1,3})\b", r"\1'\2", text)
    
    # 第三步：处理特殊的不规则缩写形式，保持原有大小写
    def replace_preserving_case(match, target_contraction):
        """保持原有大小写的替换函数"""
        original = match.group(0)
        
        # 检查原文的大小写模式
        if original[0].isupper():
            # 句首大写
            return target_contraction.capitalize()
        elif original.isupper():
            # 全大写
            return target_contraction.upper()
        else:
            # 小写
            return target_contraction.lower()
    
    # 处理不规则缩写（需要特殊处理的）
    irregular_patterns = [
        (r"\b(won)'\s*(t)\b", "won't"),      # will not → won't
        (r"\b(can)'\s*(t)\b", "can't"),      # cannot → can't
        (r"\b(shan)'\s*(t)\b", "shan't"),    # shall not → shan't
    ]
    
    for pattern, target in irregular_patterns:
        def replacer(match):
            return replace_preserving_case(match, target)
        text = re.sub(pattern, replacer, text, flags=re.IGNORECASE)
    
    return text


def make_font_safe(text: str) -> str:
    """
    将文本转换为字体安全格式，替换可能导致显示问题的特殊字符
    """
    if not text:
        return text
    
    # 字符替换映射 - 将可能有问题的Unicode字符替换为字体兼容的替代
    font_safe_replacements = {
        # 引号类 - 弯引号可能在某些字体中显示不正确
        '"': '"', '"': '"',  # 左右双引号 → 直双引号
        ''': "'", ''': "'",  # 左右单引号 → 直单引号
        
        # 连字符类 - 特殊连字符可能不被支持
        '—': ' - ',          # em dash → 空格连字符空格
        '–': '-',            # en dash → 普通连字符
        
        # 省略号
        '…': '...',          # 省略号 → 三个点
        
        # 特殊符号类 - 这些符号可能不在所有字体中
        '®': '(R)',          # 注册商标 → (R)
        '©': '(C)',          # 版权符号 → (C)
        '™': '(TM)',         # 商标符号 → (TM)
        
        # 箭头和方向符号
        '→': '->',           # 右箭头 → ->
        '←': '<-',           # 左箭头 → <-
        '↑': '^',            # 上箭头 → ^
        '↓': 'v',            # 下箭头 → v
        
        # 项目符号
        '•': '*',            # 实心圆点 → 星号
        '·': '*',            # 中点 → 星号
        '▪': '*',            # 小方块 → 星号
        '▫': '*',            # 空心小方块 → 星号
        
        # 数学符号
        '×': 'x',            # 乘号 → x
        '÷': '/',            # 除号 → /
        '±': '+/-',          # 正负号 → +/-
        
        # 货币符号（保留常见的）
        '¢': 'c',            # 分 → c
        '£': 'GBP',          # 英镑 → GBP
        '¥': 'JPY',          # 日元 → JPY
        '€': 'EUR',          # 欧元 → EUR
    }
    
    # 应用替换
    for old_char, new_char in font_safe_replacements.items():
        if old_char in text:
            text = text.replace(old_char, new_char)
    
    # 移除可能有问题的Emoji和高位Unicode字符
    # 保留基本拉丁字符、扩展拉丁字符和常见符号
    safe_chars = []
    for char in text:
        cp = ord(char)
        # 保留ASCII字符 (0x00-0x7F)
        # 保留拉丁-1补充 (0x80-0xFF)  
        # 保留拉丁扩展A (0x100-0x17F)
        # 保留拉丁扩展B (0x180-0x24F)
        # 保留IPA扩展 (0x250-0x2AF)
        # 保留间距修饰字符 (0x2B0-0x2FF)
        # 保留组合变音符号 (0x300-0x36F)
        # 保留希腊字母和科普特字母 (0x370-0x3FF)
        # 保留一般标点 (0x2000-0x206F)
        # 保留货币符号 (0x20A0-0x20CF)
        # 保留CJK字符（中文、日文、韩文）
        if (cp <= 0x36F or                          # 基本拉丁扩展
            (0x2000 <= cp <= 0x206F) or            # 一般标点
            (0x20A0 <= cp <= 0x20CF) or            # 货币符号
            (0x3000 <= cp <= 0x9FFF) or            # CJK字符
            (0xAC00 <= cp <= 0xD7AF) or            # 韩文字符
            char in ' \n\t'):                      # 空白字符
            safe_chars.append(char)
        else:
            # 对于不支持的字符，尝试找到安全的替代
            # 如果是控制字符或格式字符，跳过
            import unicodedata
            cat = unicodedata.category(char)
            if not cat.startswith('C') and not cat.startswith('Cf'):
                # 对于其他字符，可以选择保留或替换为问号
                # 这里选择跳过以避免显示问题
                continue
    
    return ''.join(safe_chars)


def clean_text(text: str) -> str:
    # 先修复英文缩写中的异常空格
    text = fix_english_contractions(text)
    # 然后转换为字体安全格式
    text = make_font_safe(text)
    # 最后进行常规的文本清理
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
    # 保留真实的换行符，让FFmpeg drawtext能够正确处理多行文本
    # text = text.replace("\n", r"\n")  # 注释掉这行，保持原始换行符
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


def get_platform_config(platform: str = 'universal') -> dict:
    """
    📱 获取指定平台的配置信息
    支持: xiaohongshu, tiktok, douyin, instagram, universal
    """
    return PLATFORM_CONFIGS.get(platform.lower(), PLATFORM_CONFIGS['universal'])

def apply_platform_styling(base_color: str, platform: str = 'universal', element_type: str = 'primary') -> str:
    """
    🎨 根据平台风格调整颜色样式
    """
    config = get_platform_config(platform)
    platform_colors = config['colors']
    
    # 根据元素类型选择对应的平台色彩
    color_mapping = {
        'primary': platform_colors['primary'],
        'secondary': platform_colors['secondary'], 
        'accent': platform_colors['accent'],
        'text': platform_colors['text'],
        'background': platform_colors['background'],
    }
    
    return color_mapping.get(element_type, base_color)

def get_platform_font_effects(platform: str = 'universal') -> str:
    """
    🔤 获取平台特定的字体效果
    """
    config = get_platform_config(platform)
    font_style = config['font_style']
    
    effects = []
    
    # 字体粗细
    if font_style['main_weight'] == 'bold':
        effects.append(r'\b1')
    elif font_style['main_weight'] == 'medium':
        effects.append(r'\b0')  # 正常粗细
    
    # 斜体效果
    if font_style.get('accent_italic', False):
        effects.append(r'\i1')
    
    # 平台特殊效果
    visual_elements = config.get('visual_elements', {})
    
    if platform == 'xiaohongshu':
        # 小红书：柔和阴影效果
        if visual_elements.get('soft_shadows'):
            effects.append(r'\shad2')  # 轻微阴影
    elif platform == 'tiktok':
        # TikTok：霓虹发光效果
        if visual_elements.get('neon_glow'):
            effects.append(r'\3c&H000080FF&\3a&H80&')  # 边框发光
    elif platform == 'douyin':
        # 抖音：温暖光晕
        if visual_elements.get('warm_lighting'):
            effects.append(r'\shad1')  # 轻微阴影
    elif platform == 'instagram':
        # Instagram：极简风格，无额外效果
        pass
    
    return "".join(effects)

def analyze_emotion_and_sentiment(text: str) -> dict:
    """
    情感分析：分析文本的情绪、语调和重要性
    返回情绪分析结果
    """
    text_lower = text.lower().strip()
    
    # 情绪词汇库
    emotions = {
        'excitement': {
            'words': ['amazing', 'incredible', 'fantastic', 'wonderful', 'awesome', 'brilliant', 
                     'outstanding', 'spectacular', 'magnificent', 'extraordinary', 'phenomenal',
                     'thrilling', 'exciting', 'wow', 'unbelievable', 'stunning', 'breathtaking'],
            'intensity': 0.9
        },
        'surprise': {
            'words': ['surprising', 'shocked', 'unexpected', 'suddenly', 'whoa', 'omg', 
                     'can\'t believe', 'never thought', 'who knew', 'turns out', 'guess what'],
            'intensity': 0.8
        },
        'curiosity': {
            'words': ['interesting', 'fascinating', 'intriguing', 'wonder', 'curious', 'mystery',
                     'secret', 'hidden', 'behind', 'what if', 'imagine', 'think about'],
            'intensity': 0.7
        },
        'urgency': {
            'words': ['important', 'crucial', 'critical', 'must', 'need to', 'immediately',
                     'right now', 'asap', 'urgent', 'don\'t miss', 'limited time', 'act now'],
            'intensity': 0.8
        },
        'achievement': {
            'words': ['success', 'achieved', 'accomplished', 'mastered', 'learned', 'completed',
                     'finished', 'done', 'got it', 'nailed it', 'perfect', 'excellent'],
            'intensity': 0.7
        }
    }
    
    # 语调分析
    tone_analysis = {
        'question': '?' in text or any(text_lower.startswith(q) for q in 
                    ['what', 'how', 'why', 'when', 'where', 'who', 'which', 'can', 'could', 'would', 'should', 'do', 'does', 'did', 'is', 'are', 'was', 'were']),
        'exclamation': '!' in text or text_lower.endswith('!'),
        'emphasis': text.isupper() or '**' in text or '*' in text,
        'list_item': text_lower.strip().startswith(('1.', '2.', '3.', '•', '-', '*')) or 
                    any(word in text_lower for word in ['first', 'second', 'third', 'next', 'finally']),
    }
    
    # 重要性分析
    importance_indicators = {
        'high': ['key', 'important', 'crucial', 'essential', 'vital', 'critical', 'fundamental', 
                'core', 'main', 'primary', 'remember', 'note', 'pay attention'],
        'technical': ['algorithm', 'function', 'method', 'process', 'system', 'model', 'framework',
                     'api', 'code', 'programming', 'data', 'database', 'server', 'network'],
        'number_fact': bool(re.search(r'\d+[%$£€¥]?|\b\d{4}\b', text))  # 包含数字或年份
    }
    
    # 检测主要情绪
    detected_emotions = []
    max_intensity = 0
    primary_emotion = 'neutral'
    
    for emotion, data in emotions.items():
        for word in data['words']:
            if word in text_lower:
                detected_emotions.append(emotion)
                if data['intensity'] > max_intensity:
                    max_intensity = data['intensity']
                    primary_emotion = emotion
                break
    
    # 检测重要性级别
    importance = 'normal'
    for level, indicators in importance_indicators.items():
        if level == 'number_fact':
            if indicators:
                importance = 'high'
                break
        else:
            if any(indicator in text_lower for indicator in indicators):
                importance = 'high' if level == 'high' else 'medium'
                break
    
    return {
        'primary_emotion': primary_emotion,
        'emotions': detected_emotions,
        'intensity': max_intensity,
        'tone': tone_analysis,
        'importance': importance,
        'length': len(text.split())
    }

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


def get_emotion_visual_effects(emotion_data: dict, word_type: str, platform: str = 'universal') -> str:
    """
    🎨 情绪驱动的视觉系统 - 根据情感分析生成动态视觉效果
    返回包含颜色、缩放、闪烁等效果的ASS样式代码
    """
    primary_emotion = emotion_data['primary_emotion']
    intensity = emotion_data['intensity']
    tone = emotion_data['tone']
    importance = emotion_data['importance']
    
    # 📱 获取平台配置
    platform_config = get_platform_config(platform)
    platform_colors = platform_config['colors']
    
    # 🎨 情绪颜色映射（根据平台风格调整）
    if platform == 'xiaohongshu':
        # 小红书：温暖清新的色彩搭配
        emotion_colors = {
            'excitement': platform_colors['primary'],     # 小红书红：温暖兴奋
            'surprise': platform_colors['secondary'],     # 暖橙色：惊喜感
            'curiosity': platform_colors['accent'],       # 薄荷绿：好奇探索
            'urgency': '&H00FF6B6B&',                     # 温暖红：紧急但不突兀
            'achievement': '&H0066CC99&',                 # 清新绿：成就感
            'neutral': platform_colors['text'],           # 深灰：温和中性
        }
    elif platform == 'tiktok':
        # TikTok：年轻潮流的霓虹色彩
        emotion_colors = {
            'excitement': platform_colors['secondary'],   # 霓虹黄：狂欢兴奋
            'surprise': platform_colors['primary'],       # TikTok粉：惊艳震撼
            'curiosity': platform_colors['accent'],       # 亮紫色：神秘好奇
            'urgency': '&H000080FF&',                     # 鲜红色：紧急警告
            'achievement': '&H0000FF80&',                 # 霓虹绿：炫酷成就
            'neutral': platform_colors['text'],           # 纯白：清晰中性
        }
    elif platform == 'douyin':
        # 抖音：热情大气的中国风色彩
        emotion_colors = {
            'excitement': platform_colors['secondary'],   # 金橙色：热情兴奋
            'surprise': platform_colors['primary'],       # 抖音红：震撼惊讶
            'curiosity': platform_colors['accent'],       # 活力橙：探索好奇
            'urgency': platform_colors['primary'],        # 抖音红：重要紧急
            'achievement': '&H00FF9900&',                 # 成就金：荣耀感
            'neutral': platform_colors['text'],           # 白色：大气中性
        }
    elif platform == 'instagram':
        # Instagram：高级优雅的渐变色彩
        emotion_colors = {
            'excitement': platform_colors['accent'],      # 香槟金：优雅兴奋
            'surprise': platform_colors['primary'],       # Instagram紫：高级惊喜
            'curiosity': platform_colors['secondary'],    # 蓝紫色：深度好奇
            'urgency': '&H00D93025&',                     # 高级红：重要不失雅致
            'achievement': '&H00228B22&',                 # 深绿色：成熟成就感
            'neutral': platform_colors['text'],           # 炭黑：专业中性
        }
    else:
        # 通用：平衡的多彩搭配
        emotion_colors = {
            'excitement': '&H0000FFFF&',    # 金黄色：通用兴奋
            'surprise': '&H00FF8C00&',      # 亮橙色：通用惊讶
            'curiosity': '&H00FF6B47&',     # 蓝橙色：通用好奇
            'urgency': '&H000080FF&',       # 红色：通用紧急
            'achievement': '&H0066FF66&',   # 绿色：通用成就
            'neutral': '&H00FFFFFF&',       # 白色：通用中性
        }
    
    # 词汇类型颜色（融入平台风格）
    word_type_colors = {
        'person': apply_platform_styling('&H005599FF&', platform, 'secondary'),
        'brand': apply_platform_styling('&H0000FFFF&', platform, 'accent'),
        'number': apply_platform_styling('&H0066FF66&', platform, 'accent'),
        'verb': apply_platform_styling('&H00FF66FF&', platform, 'primary'),
        'tech': apply_platform_styling('&H00FF9900&', platform, 'primary'),
        'default': apply_platform_styling('&H0099CCFF&', platform, 'secondary')
    }
    
    # 基础颜色选择（优先情绪，其次词汇类型）
    if primary_emotion != 'neutral':
        base_color = emotion_colors[primary_emotion]
    else:
        base_color = word_type_colors.get(word_type, word_type_colors['default'])
    
    effects = []
    
    # 🔥 兴奋激动效果 - 金色闪烁
    if primary_emotion == 'excitement':
        if intensity > 0.8:
            # 强烈兴奋：金色闪烁 + 轻微放大
            effects.append(rf"\c{base_color}")
            effects.append(r"\fscx110\fscy110")  # 放大10%
            # 简化的闪烁效果（通过颜色变化）
            effects.append(r"\t(0,200,\c&H00FFFF00&)\t(200,400,\c" + base_color + ")")
        else:
            # 中等兴奋：金色高亮
            effects.append(rf"\c{base_color}")
            effects.append(r"\fscx105\fscy105")  # 轻微放大5%
    
    # 🎯 惊讶震撼效果 - 橙色爆发
    elif primary_emotion == 'surprise':
        effects.append(rf"\c{base_color}")
        effects.append(r"\fscx115\fscy115")  # 放大15%
        # 添加粗体强调
        effects.append(r"\b1")
    
    # 🔍 好奇探索效果 - 蓝色波动
    elif primary_emotion == 'curiosity':
        effects.append(rf"\c{base_color}")
        effects.append(r"\fscx108\fscy108")  # 放大8%
        # 添加斜体效果，营造探索感
        effects.append(r"\i1")
    
    # ⚡ 紧急重要效果 - 红色警告
    elif primary_emotion == 'urgency':
        effects.append(rf"\c{base_color}")
        effects.append(r"\fscx112\fscy112")  # 放大12%
        effects.append(r"\b1")  # 粗体
        # 红色闪烁效果
        effects.append(r"\t(0,150,\c&H000080FF&)\t(150,300,\c" + base_color + ")")
    
    # 🏆 成就完成效果 - 绿色荣耀
    elif primary_emotion == 'achievement':
        effects.append(rf"\c{base_color}")
        effects.append(r"\fscx107\fscy107")  # 放大7%
        effects.append(r"\b1")  # 粗体强调成就感
    
    # 📊 重要性级别视觉增强
    if importance == 'high':
        if not any('fscx' in effect for effect in effects):
            effects.append(r"\fscx110\fscy110")  # 重要内容放大10%
        if not any(r'\b' in effect for effect in effects):
            effects.append(r"\b1")  # 重要内容加粗
    elif importance == 'medium':
        if not any('fscx' in effect for effect in effects):
            effects.append(r"\fscx105\fscy105")  # 中等重要内容放大5%
    
    # 🎵 语调视觉化
    if tone['question']:
        # 疑问句：添加向上箭头效果（通过位置微调模拟）
        effects.append(r"\move(0,0,0,-2)")  # 轻微上移2像素
    elif tone['exclamation']:
        # 感叹句：添加强调效果
        if not any(r'\b' in effect for effect in effects):
            effects.append(r"\b1")  # 感叹加粗
    elif tone['emphasis']:
        # 强调文本：全大写或特殊标记
        effects.append(r"\b1\i1")  # 粗体+斜体双重强调
    
    # 🔢 数字和列表项特殊处理
    if tone['list_item']:
        # 列表项：添加结构化视觉提示
        if not any('c&H' in effect for effect in effects):
            effects.append(r"\c&H0066FF66&")  # 列表项用绿色
    
    # 📱 添加平台特定的字体效果
    platform_font_effects = get_platform_font_effects(platform)
    if platform_font_effects:
        effects.append(platform_font_effects)
    
    # 如果没有特殊效果，返回基础颜色 + 平台效果
    if not effects or len(effects) == 1 and effects[0] == platform_font_effects:
        return rf"\c{base_color}{platform_font_effects}"
    
    return "".join(effects)

def get_highlight_color(word_type: str) -> str:
    """
    兼容性函数：根据词汇类型返回对应的ASS颜色代码（BGR格式）
    此函数保持向后兼容，新的情绪系统使用get_emotion_visual_effects
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
    emotion_boost: bool = False,
    platform: str = 'universal',
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
    
    # 最后再次应用缩写修复，确保之前的正则处理没有破坏缩写词
    en_text = fix_english_contractions(en_text)
    
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
            
            # 🎨 情绪驱动的视觉系统
            word_type = classify_word_type(tok.strip())
            
            # 如果启用情绪增强模式
            if emotion_boost:
                # 对整个句子进行情感分析
                emotion_data = analyze_emotion_and_sentiment(en_text)
                # 对当前词汇进行情感分析（更精确）
                word_emotion_data = analyze_emotion_and_sentiment(tok.strip())
                
                # 使用更强烈的情绪数据
                if word_emotion_data['primary_emotion'] != 'neutral':
                    final_emotion_data = word_emotion_data
                else:
                    final_emotion_data = emotion_data
                
                # 生成情绪驱动的视觉效果
                if raw in keyword_set or word_type != 'default' or final_emotion_data['primary_emotion'] != 'neutral':
                    visual_effects = get_emotion_visual_effects(final_emotion_data, word_type, platform)
                    piece = rf"{{\kf{dur}{visual_effects}}}{escaped}{{\r}}"
                else:
                    piece = rf"{{\kf{dur}}}{escaped}"
            else:
                # 传统的智能分类高亮
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
    emotion_boost: bool = False,
    platform: str = 'universal',
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
        emotion_boost=emotion_boost,
        platform=platform,
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
    # 修复英文缩写词中的异常空格
    en_text = fix_english_contractions(en_text)
    
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
    if not items or sections <= 0:  # 如果没有内容或章节数为0，返回空列表
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


def get_youtube_chapters(video_id: str) -> List[Tuple[float, float, str]]:
    """
    📋 获取YouTube视频的原生章节信息
    返回章节列表: [(开始时间, 结束时间, 章节标题), ...]
    """
    url = f"https://www.youtube.com/watch?v={video_id}"
    
    try:
        print("   🔍 正在获取YouTube视频章节信息...")
        
        # 使用yt-dlp获取视频的详细信息，包括章节
        result = subprocess.run([
            "yt-dlp", 
            "--print", "%(chapters)j",  # 获取章节信息的JSON格式
            "--print", "%(duration)s",   # 获取视频总时长
            url
        ], capture_output=True, text=True, check=False)
        
        if result.returncode != 0:
            print("   ⚠️ 无法获取视频信息，跳过章节功能")
            return []
        
        output_lines = [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
        
        if len(output_lines) < 2:
            print("   ⚠️ 视频信息不完整，跳过章节功能")
            return []
            
        chapters_json = output_lines[0]
        duration_str = output_lines[1]
        
        # 解析视频总时长
        try:
            video_duration = float(duration_str)
        except (ValueError, TypeError):
            print("   ⚠️ 无法解析视频时长，跳过章节功能")
            return []
        
        # 解析章节信息
        if chapters_json == "null" or not chapters_json:
            print("   ℹ️ 该视频没有设置章节标记")
            return []
        
        try:
            chapters_data = json.loads(chapters_json)
        except json.JSONDecodeError:
            print("   ⚠️ 章节信息格式错误，跳过章节功能")
            return []
        
        if not chapters_data or not isinstance(chapters_data, list):
            print("   ℹ️ 该视频没有有效的章节标记")
            return []
        
        # 转换章节数据为我们需要的格式
        youtube_chapters = []
        
        for i, chapter in enumerate(chapters_data):
            if not isinstance(chapter, dict):
                continue
                
            # 获取章节开始时间
            start_time = chapter.get('start_time', 0)
            title = chapter.get('title', f'Chapter {i + 1}')
            
            # 清理章节标题
            title = clean_text(title)
            if not title:
                title = f"Chapter {i + 1}"
            
            # 计算结束时间
            if i < len(chapters_data) - 1:
                # 不是最后一章，结束时间是下一章的开始时间
                end_time = chapters_data[i + 1].get('start_time', start_time + 60)
            else:
                # 最后一章，结束时间是视频结束
                end_time = video_duration
            
            # 确保时间有效
            if isinstance(start_time, (int, float)) and isinstance(end_time, (int, float)):
                if end_time > start_time:
                    youtube_chapters.append((float(start_time), float(end_time), title))
        
        if youtube_chapters:
            print(f"   ✅ 成功获取到 {len(youtube_chapters)} 个章节标记")
            for i, (start, end, title) in enumerate(youtube_chapters):
                mins_start, secs_start = divmod(int(start), 60)
                mins_end, secs_end = divmod(int(end), 60)
                print(f"      {i+1}. {title} ({mins_start:02d}:{secs_start:02d} - {mins_end:02d}:{secs_end:02d})")
            return youtube_chapters
        else:
            print("   ℹ️ 没有找到有效的章节标记")
            return []
            
    except subprocess.CalledProcessError as e:
        print(f"   ⚠️ 获取章节信息失败: {e}")
        return []
    except Exception as e:
        print(f"   ⚠️ 解析章节信息时出错: {e}")
        return []


def create_multi_line_title_drawtext(wrapped_title: str, safe_fontfile: str, base_y: int = None) -> tuple[str, str]:
    """
    为多行标题创建独立的drawtext滤镜
    返回 (滤镜字符串, 最后的标签名称)
    """
    if base_y is None:
        base_y = TITLE_SAFE_Y
    
    # 分割标题为多行
    lines = [line.strip() for line in wrapped_title.split('\n') if line.strip()]
    
    if not lines:
        return "", "[input]"
    
    if len(lines) == 1:
        # 单行标题，使用原来的方式
        safe_line = sanitize_drawtext_text(lines[0])
        drawtext_filter = (
            f"[input]drawtext="
            f"fontfile='{safe_fontfile}':"
            f"text='{safe_line}':"
            f"fontcolor=#FF6600:"
            f"fontsize=40:"
            f"box=1:"
            f"boxcolor=black@0.45:"
            f"boxborderw=20:"
            f"x=(w-text_w)/2:"
            f"y={base_y}[title1];"
        )
        return drawtext_filter, "[title1]"
    
    # 多行标题，为每行创建独立的drawtext滤镜
    drawtext_filters = []
    line_height = 50  # 行间距
    
    for i, line in enumerate(lines):
        # 转义单引号和特殊字符，但不转义换行符（因为这里每行是独立的）
        safe_line = line.replace("\\", r"\\\\")
        safe_line = safe_line.replace("'", r"\'")
        safe_line = safe_line.replace(":", r"\:")
        safe_line = safe_line.replace("%", r"\%")
        safe_line = safe_line.replace(",", r"\,")
        safe_line = safe_line.replace("[", r"\[")
        safe_line = safe_line.replace("]", r"\]")
        
        y_pos = base_y + (i * line_height)
        
        # 多行标题所有行都不显示背景，保持简洁的视觉效果
        drawtext_filter = (
            f"drawtext="
            f"fontfile='{safe_fontfile}':"
            f"text='{safe_line}':"
            f"fontcolor=#FF6600:"
            f"fontsize=40:"
            f"x=(w-text_w)/2:"
            f"y={y_pos}"
        )
        
        drawtext_filters.append(drawtext_filter)
    
    # 组合多个drawtext滤镜
    filter_string = ""
    input_tag = "[input]"
    
    for i, drawtext in enumerate(drawtext_filters):
        output_tag = f"[title{i+1}]"
        filter_string += f"{input_tag}{drawtext}{output_tag};"
        input_tag = output_tag  # 下一个滤镜的输入是当前的输出
    
    final_tag = f"[title{len(drawtext_filters)}]"
    return filter_string, final_tag


def calc_history_block_height(item: Dict) -> int:
    # 统一字体大小后的历史字幕高度计算
    en_wrapped = wrap_text_by_visual_width(item.get("en", ""), 32.0)
    zh_wrapped = wrap_text_by_visual_width(item.get("zh", ""), 24.0)

    en_lines = count_ass_lines(en_wrapped)
    zh_lines = count_ass_lines(zh_wrapped) if zh_wrapped else 0

    # 统一字体大小(38px)后，每行高度一致
    line_h = 42  # 历史字体38px对应的行高
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
    emotion_boost: bool = False,  # 🎨 情绪驱动视觉系统
    platform: str = 'universal',  # 📱 平台定制优化
) -> None:
    # 字幕层级设计：英文突出，中文辅助（短视频安全区）
    english_fontsize = 44      # 英文字体大小，避免超出边界（减小到44px）
    chinese_fontsize = 38      # 中文字体适中，清晰可读（调整到38px）
    
    # 计算短视频安全区字幕边距 - 英文在上，中文在下
    # ASS中MarginV是从底部开始计算：值越大越靠近顶部，值越小越靠近底部
    english_margin_v = SAFE_AREA_BOTTOM + 145  # 英文字幕在上方：425px距底
    chinese_margin_v = SAFE_AREA_BOTTOM + 65   # 中文字幕在下方：345px距底，使用保守间距确保完全无覆盖
    subtitle_line_gap = 80  # 英中文字幕间距：80px，保守设计，充分避免字体渲染差异导致的覆盖问题

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
Style: Chapter,{ASS_FONT_NAME},28,&H00FFAA66,&H000080FF,&H00000000,&H60000000,1,0,0,0,100,100,0,0,1,2,1,2,80,80,1770,1
Style: HistoryEn,{ASS_FONT_NAME},{english_fontsize-6},&H000066FF,&H00C0C0C0,&H00000000,&H70000000,0,0,0,0,100,100,0,0,1,2.5,1,8,80,80,0,1
Style: HistoryCn,{ASS_FONT_NAME},{english_fontsize-6},&H000066FF,&H00707070,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,1.5,0.5,8,80,80,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    with open(path, "w", encoding="utf-8") as f:
        f.write(header)

        for start, end, title in chapters:
            # 应用片头时间偏移
            adjusted_start = start + intro_offset
            adjusted_end = end + intro_offset
            # 📋 章节格式：Chapter: [章节标题]，显示在标题上方左对齐
            chapter_text = f"Chapter: {title}"
            line = f"Dialogue: 0,{ass_time(adjusted_start)},{ass_time(adjusted_end)},Chapter,,0,0,0,,{ass_escape_text(chapter_text)}\n"
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
                emotion_boost=emotion_boost,  # 🎨 情绪驱动视觉系统
                platform=platform,  # 📱 平台定制优化
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
    show_source: bool = False,  # 是否显示视频来源
    video_id: str = "",  # 视频ID，用于构建来源URL
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
        
        # 生成多行标题drawtext滤镜
        title_drawtext, title_output = create_multi_line_title_drawtext(wrapped_title, safe_fontfile, TITLE_SAFE_Y)
        
        filter_complex += (

            "[bg][bars]"
            f"overlay=(W-w)/2:{overlay_y}[tmp1];"

            # 添加多行标题
            f"{title_drawtext.replace('[input]', '[tmp1]')}"
        )
        
        # 更新后续处理的输入标签
        ass_input = title_output
    else:
        # 生成多行标题drawtext滤镜
        title_drawtext, title_output = create_multi_line_title_drawtext(wrapped_title, safe_fontfile, TITLE_SAFE_Y)
        
        filter_complex = (
            f"[0:v]"
            f"scale={VIDEO_W}:{VIDEO_H}:force_original_aspect_ratio=increase,"
            f"crop={VIDEO_W}:{VIDEO_H},"
            f"setsar=1,"
            f"zoompan=z='min(1.15,1+on/2500)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"s={VIDEO_W}x{VIDEO_H}:fps=25[bg];"

            # 添加多行标题
            f"{title_drawtext.replace('[input]', '[bg]')}"
        )
        
        # 更新后续处理的输入标签
        ass_input = title_output

    if subtitle_text:
        filter_complex += (
            f"{ass_input}drawtext="
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
    # ass_input 已经在前面设置好了，不需要else分支

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
            f"[intro_added]ass='{safe_ass}'[subtitled];"
            
            # 只添加淡入效果，不添加全画面淡出（片尾保留背景和标题）
            f"[subtitled]fade=t=in:st=0:d=0.5[faded]"
        )
    else:
        # 无片头：直接显示字幕，片尾保留背景和标题
        filter_complex += (
            f"{ass_input}ass='{safe_ass}'[subtitled];"
            f"[subtitled]fade=t=in:st=0:d={intro_duration}[faded]"
        )
    
    # 添加视频来源显示（可选）
    if show_source and video_id:
        source_url = f"source: https://www.youtube.com/watch?v={video_id}"
        safe_source_text = sanitize_drawtext_text(source_url)
        
        # 在最底部显示来源，位置在安全区内
        source_y = VIDEO_H - 50  # 距离底部50像素
        
        filter_complex += (
            f";[faded]drawtext="
            f"fontfile='{safe_fontfile}':"
            f"text='{safe_source_text}':"
            f"fontcolor=#CCCCCC:"  # 灰色文字，不太突出
            f"fontsize=20:"
            f"x=(w-text_w)/2:"  # 居中对齐
            f"y={source_y}[v]"
        )
    else:
        # 不显示来源，直接重命名输出
        filter_complex += ";[faded]null[v]"

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
  python build_from_video_id.py QqeECC13HcM --cover tech.jpg --summary "学习AI技术" --show-intro --show-source --emotion-boost --platform xiaohongshu

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
    
    parser.add_argument('--show-source',
                       action='store_true',
                       help='在视频底部显示YouTube来源链接 (默认: false)')
    
    parser.add_argument('--emotion-boost',
                       action='store_true',
                       help='🎨 启用情绪驱动视觉系统：智能识别情感并添加动态视觉效果 (默认: false)')
    
    parser.add_argument('--platform', '-p',
                       choices=['xiaohongshu', 'tiktok', 'douyin', 'instagram', 'universal'],
                       default='universal',
                       help='📱 平台定制优化：xiaohongshu(小红书清新风), tiktok(年轻潮流风), douyin(本土大气风), instagram(高端质感风), universal(通用平衡风) (默认: universal)')
    
    parser.add_argument('--auto-chapters',
                       action='store_true', 
                       default=True,
                       help='📋 自动获取并显示YouTube视频的原生章节标记 (默认: 启用)')
    
    parser.add_argument('--no-chapters',
                       action='store_true',
                       help='📋 关闭章节功能，不显示任何章节标记')

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
            show_source = False  # 旧格式不支持显示来源
            emotion_boost = False  # 旧格式不支持情绪增强
            platform = 'universal'  # 旧格式使用通用平台样式
            auto_chapters = True  # 旧格式默认启用章节功能
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
            show_source = args.show_source  # 是否显示视频来源
            emotion_boost = args.emotion_boost  # 🎨 情绪驱动视觉系统
            platform = args.platform  # 📱 平台定制优化
            auto_chapters = not args.no_chapters  # 📋 章节功能控制（默认启用，除非用户关闭）
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
        show_source = args.show_source  # 是否显示视频来源
        emotion_boost = args.emotion_boost  # 🎨 情绪驱动视觉系统
        platform = args.platform  # 📱 平台定制优化
        auto_chapters = not args.no_chapters  # 📋 章节功能控制（默认启用，除非用户关闭）
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
    
    # 📋 智能章节系统：优先使用YouTube原生章节，否则跳过章节功能
    chapters = []
    if auto_chapters:  # 用户可控制是否启用章节功能
        print("   🔍 尝试获取YouTube视频原生章节...")
        youtube_chapters = get_youtube_chapters(video_id)
        
        if youtube_chapters:
            # 找到了YouTube原生章节，使用它们
            chapters = youtube_chapters
            print(f"   ✅ 使用YouTube原生章节 ({len(chapters)} 个)")
        else:
            # 没有找到YouTube原生章节，不生成任何章节
            chapters = []
            print("   ℹ️ 未找到YouTube章节，跳过章节功能")
    else:
        print("   ⏭️ 章节功能已被用户关闭")
        chapters = []
    # 如果启用片头，字幕需要延后显示
    intro_offset_time = 1.5 if show_intro else 0.0  # 片头时长1.5秒
    # 先用None作为subtitle_end_time，在音频下载后重新生成字幕
    write_ass_karaoke(bilingual_items, ass_path, keywords, chapters, show_bars=show_bars, intro_offset=intro_offset_time, subtitle_end_time=None, emotion_boost=emotion_boost, platform=platform)

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
        write_ass_karaoke(bilingual_items, ass_path, keywords, chapters, show_bars=show_bars_final, intro_offset=intro_offset_time, subtitle_end_time=None, emotion_boost=emotion_boost, platform=platform)
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
        write_ass_karaoke(bilingual_items, ass_path, keywords, chapters, show_bars=show_bars_final, intro_offset=intro_offset_time, subtitle_end_time=subtitle_end_time, emotion_boost=emotion_boost, platform=platform)
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
        show_source=show_source,
        video_id=video_id,
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