#!/usr/bin/env python3
"""
LearnSubStudio 环境测试脚本
测试Python依赖和系统工具是否正确安装
"""

import sys
import subprocess
from pathlib import Path

def test_python_version():
    """测试Python版本"""
    print("🐍 检查Python版本...")
    version = sys.version_info
    if version.major >= 3 and version.minor >= 8:
        print(f"   ✅ Python {version.major}.{version.minor}.{version.micro} (满足要求)")
        return True
    else:
        print(f"   ❌ Python {version.major}.{version.minor}.{version.micro} (需要3.8+)")
        return False

def test_python_modules():
    """测试Python依赖模块"""
    print("\n📦 检查Python依赖模块...")
    modules = [
        ("requests", "网络请求库"),
        ("youtube_transcript_api", "YouTube字幕API")
    ]
    
    all_good = True
    for module_name, description in modules:
        try:
            __import__(module_name)
            print(f"   ✅ {module_name} - {description}")
        except ImportError:
            print(f"   ❌ {module_name} - {description} (未安装)")
            all_good = False
    
    return all_good

def test_system_tools():
    """测试系统工具"""
    print("\n🔧 检查系统工具...")
    tools = [
        ("ffmpeg", "视频处理工具"),
        ("ffprobe", "媒体信息探测"),
        ("yt-dlp", "YouTube下载器")
    ]
    
    all_good = True
    for tool, description in tools:
        try:
            result = subprocess.run([tool, "--version"], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                version_line = result.stdout.split('\n')[0]
                print(f"   ✅ {tool} - {description}")
                print(f"      版本: {version_line[:60]}...")
            else:
                print(f"   ❌ {tool} - {description} (运行失败)")
                all_good = False
        except (subprocess.TimeoutExpired, FileNotFoundError):
            print(f"   ❌ {tool} - {description} (未安装或不在PATH中)")
            all_good = False
    
    return all_good

def test_virtual_environment():
    """检查是否在虚拟环境中"""
    print("\n🌐 检查虚拟环境...")
    
    # 检查是否在虚拟环境中
    is_venv = hasattr(sys, 'real_prefix') or (
        hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix
    )
    
    if is_venv:
        print(f"   ✅ 运行在虚拟环境中")
        print(f"      Python路径: {sys.executable}")
        print(f"      环境前缀: {sys.prefix}")
        return True
    else:
        print(f"   ⚠️  运行在系统Python中")
        print(f"      建议使用虚拟环境: source ~/ytapi-venv/bin/activate")
        return False

def test_project_files():
    """检查项目文件"""
    print("\n📁 检查项目文件...")
    files = [
        ("build_from_video_id.py", "主程序脚本"),
        ("cover.jpg", "默认封面图片"),
        ("README.md", "项目文档")
    ]
    
    all_good = True
    for filename, description in files:
        if Path(filename).exists():
            file_size = Path(filename).stat().st_size
            print(f"   ✅ {filename} - {description} ({file_size} bytes)")
        else:
            print(f"   ❌ {filename} - {description} (不存在)")
            all_good = False
    
    return all_good

def main():
    print("=" * 60)
    print("LearnSubStudio 环境测试")
    print("=" * 60)
    
    tests = [
        ("Python版本", test_python_version),
        ("Python模块", test_python_modules), 
        ("系统工具", test_system_tools),
        ("虚拟环境", test_virtual_environment),
        ("项目文件", test_project_files)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"   ❌ 测试失败: {e}")
            results.append((test_name, False))
    
    # 显示总结
    print("\n" + "=" * 60)
    print("测试结果总结")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{test_name:<12} {status}")
    
    print("-" * 60)
    print(f"总计: {passed}/{total} 项测试通过")
    
    if passed == total:
        print("\n🎉 环境测试全部通过！可以开始使用 LearnSubStudio")
        print("\n💡 快速开始:")
        print("   python build_from_video_id.py QqeECC13HcM")
    else:
        print(f"\n⚠️  有 {total - passed} 项测试失败，请检查安装配置")
        print("\n🔧 常见解决方案:")
        print("   1. 激活虚拟环境: source ~/ytapi-venv/bin/activate")
        print("   2. 安装Python依赖: pip install requests youtube-transcript-api")
        print("   3. 安装系统工具: sudo apt install ffmpeg (Ubuntu)")
        print("   4. 安装yt-dlp: pip install yt-dlp")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)