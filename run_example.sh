#!/bin/bash

# LearnSubStudio 快速启动脚本
# 适用于虚拟机和服务器环境

echo "🚀 LearnSubStudio 快速启动"
echo "=========================="

# 检查虚拟环境
if [[ -z "$VIRTUAL_ENV" ]]; then
    echo "⚠️  未检测到虚拟环境，尝试激活..."
    
    # 尝试激活常见的虚拟环境路径
    VENV_PATHS=(
        "~/ytapi-venv/bin/activate"
        "./venv/bin/activate" 
        "./env/bin/activate"
        "$HOME/ytapi-venv/bin/activate"
    )
    
    ACTIVATED=false
    for venv_path in "${VENV_PATHS[@]}"; do
        if [[ -f "${venv_path/#\~/$HOME}" ]]; then
            echo "✅ 找到虚拟环境: $venv_path"
            source "${venv_path/#\~/$HOME}"
            ACTIVATED=true
            break
        fi
    done
    
    if [[ "$ACTIVATED" == false ]]; then
        echo "❌ 未找到虚拟环境，请手动激活:"
        echo "   source ~/ytapi-venv/bin/activate"
        echo ""
        echo "💡 或者使用系统Python继续 (不推荐):"
        read -p "继续使用系统Python? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
else
    echo "✅ 虚拟环境已激活: $VIRTUAL_ENV"
fi

echo ""

# 运行环境测试
echo "🧪 运行环境测试..."
if python test_environment.py > /dev/null 2>&1; then
    echo "✅ 环境测试通过"
else
    echo "⚠️  环境测试有警告，但继续运行..."
    echo "   (运行 'python test_environment.py' 查看详细信息)"
fi

echo ""

# 运行示例
if [[ $# -eq 0 ]]; then
    echo "🎬 使用示例视频 ID: QqeECC13HcM"
    echo "📝 命令: python build_from_video_id.py QqeECC13HcM"
    echo ""
    
    read -p "现在运行示例? (Y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Nn]$ ]]; then
        echo "💡 您可以手动运行: python build_from_video_id.py VIDEO_ID"
        exit 0
    fi
    
    python build_from_video_id.py QqeECC13HcM
else
    echo "🎬 使用提供的参数运行..."
    echo "📝 命令: python build_from_video_id.py $*"
    echo ""
    
    python build_from_video_id.py "$@"
fi

echo ""
echo "🎉 运行完成！"

# 显示输出文件
if [[ -f "QqeECC13HcM.mp4" ]]; then
    echo "📁 生成的文件:"
    ls -lh QqeECC13HcM.* 2>/dev/null | head -5
fi