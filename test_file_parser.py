#!/usr/bin/env python3
"""
文件解析服务测试脚本
用于测试各种文件格式的解析功能
"""

import os
import sys
import tempfile
import requests
from pathlib import Path

# 添加项目路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'RAGEval', 'rag-evaluation-backend'))

def test_file_parser_service():
    """测试文件解析服务"""
    print("=== 文件解析服务测试 ===\n")
    
    # 测试文件路径
    test_files = [
        "data/test.pdf",
        "data/2022毕业记录.doc",
        "data/基于改进元胞自动机模型的烟气场景地下商场疏散管理研究_谢尊贤.pdf",
        "data/基于网络网格模型的卢浮宫疏散系统.docx",
        "data/基于网络网格模型的卢富宫疏散系统（增加噪声版）.docx",
        "data/联通助理5G视频客服业务规则20240712.doc"
    ]
    
    # 检查测试文件是否存在
    available_files = []
    for file_path in test_files:
        if os.path.exists(file_path):
            available_files.append(file_path)
            print(f"✓ 找到测试文件: {file_path}")
        else:
            print(f"✗ 测试文件不存在: {file_path}")
    
    if not available_files:
        print("\n❌ 没有找到可用的测试文件")
        return
    
    print(f"\n找到 {len(available_files)} 个测试文件")
    
    # 测试文件解析服务
    for file_path in available_files:
        print(f"\n--- 测试文件: {os.path.basename(file_path)} ---")
        test_single_file(file_path)

def test_single_file(file_path):
    """测试单个文件的解析"""
    try:
        # 导入文件解析服务
        from RAGEval.rag_evaluation_backend.app.services.file_parser_service import FileParserService
        
        # 创建解析服务实例
        parser = FileParserService()
        
        # 检查文件是否支持
        if not parser.is_supported(file_path):
            print(f"❌ 不支持的文件格式: {Path(file_path).suffix}")
            return
        
        # 获取文件信息
        file_info = parser.get_file_info(file_path)
        print(f"📄 文件信息:")
        print(f"   名称: {file_info['name']}")
        print(f"   扩展名: {file_info['extension']}")
        print(f"   MIME类型: {file_info['mime_type']}")
        print(f"   大小: {file_info['size']} 字节")
        print(f"   支持: {'是' if file_info['supported'] else '否'}")
        
        # 解析文件
        print(f"🔄 开始解析...")
        md_content = parser.parse_file(file_path)
        
        # 显示解析结果
        print(f"✅ 解析成功!")
        print(f"📝 生成的Markdown内容长度: {len(md_content)} 字符")
        
        # 显示前200个字符的预览
        preview = md_content[:200] + "..." if len(md_content) > 200 else md_content
        print(f"📋 内容预览:\n{preview}\n")
        
        # 保存解析结果到临时文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
            f.write(md_content)
            temp_file = f.name
        
        print(f"💾 解析结果已保存到: {temp_file}")
        
    except ImportError as e:
        print(f"❌ 导入错误: {e}")
        print("请确保已安装所有必要的依赖库")
    except Exception as e:
        print(f"❌ 解析失败: {e}")

def test_parser_info():
    """测试解析器信息"""
    print("\n=== 解析器信息测试 ===\n")
    
    try:
        from RAGEval.rag_evaluation_backend.app.services.file_parser_service import FileParserService
        
        parser = FileParserService()
        info = parser.get_parser_info()
        
        print("📋 支持的文件格式:")
        for ext, desc in info['supported_formats'].items():
            print(f"   {ext} - {desc}")
        
        print(f"\n🔧 依赖库状态:")
        for lib, available in info['libraries'].items():
            status = "✓ 可用" if available else "✗ 不可用"
            print(f"   {lib}: {status}")
            
    except Exception as e:
        print(f"❌ 获取解析器信息失败: {e}")

def test_api_endpoints():
    """测试API端点（需要服务器运行）"""
    print("\n=== API端点测试 ===\n")
    
    base_url = "http://localhost:8000/api/v1/file-parser"
    
    # 测试获取支持格式
    try:
        response = requests.get(f"{base_url}/supported-formats/")
        if response.status_code == 200:
            data = response.json()
            print("✅ 获取支持格式成功")
            print(f"   支持 {len(data['supported_formats'])} 种文件格式")
        else:
            print(f"❌ 获取支持格式失败: {response.status_code}")
    except requests.exceptions.ConnectionError:
        print("❌ 无法连接到服务器，请确保服务器正在运行")
    except Exception as e:
        print(f"❌ API测试失败: {e}")

def create_test_files():
    """创建测试文件"""
    print("\n=== 创建测试文件 ===\n")
    
    # 创建测试目录
    test_dir = Path("test_files")
    test_dir.mkdir(exist_ok=True)
    
    # 创建文本文件
    text_content = """# 测试文档

这是一个测试文档，用于验证文件解析功能。

## 功能特性

1. 支持多种格式
2. 智能解析
3. 批量处理

## 表格示例

| 列1 | 列2 | 列3 |
|-----|-----|-----|
| 数据1 | 数据2 | 数据3 |
| 数据4 | 数据5 | 数据6 |

## 代码示例

```python
def hello_world():
    print("Hello, World!")
```

---
*测试文档结束*
"""
    
    # 保存为不同格式
    files_created = []
    
    # 纯文本文件
    text_file = test_dir / "test.txt"
    with open(text_file, 'w', encoding='utf-8') as f:
        f.write(text_content)
    files_created.append(str(text_file))
    
    # Markdown文件
    md_file = test_dir / "test.md"
    with open(md_file, 'w', encoding='utf-8') as f:
        f.write(text_content)
    files_created.append(str(md_file))
    
    # HTML文件
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>测试文档</title>
    <meta charset="utf-8">
</head>
<body>
    <h1>测试文档</h1>
    <p>这是一个测试文档，用于验证文件解析功能。</p>
    <h2>功能特性</h2>
    <ul>
        <li>支持多种格式</li>
        <li>智能解析</li>
        <li>批量处理</li>
    </ul>
    <h2>表格示例</h2>
    <table border="1">
        <tr><th>列1</th><th>列2</th><th>列3</th></tr>
        <tr><td>数据1</td><td>数据2</td><td>数据3</td></tr>
        <tr><td>数据4</td><td>数据5</td><td>数据6</td></tr>
    </table>
</body>
</html>"""
    
    html_file = test_dir / "test.html"
    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    files_created.append(str(html_file))
    
    print(f"✅ 创建了 {len(files_created)} 个测试文件:")
    for file_path in files_created:
        print(f"   {file_path}")
    
    return files_created

def main():
    """主函数"""
    print("文件解析服务测试工具")
    print("=" * 50)
    
    # 测试解析器信息
    test_parser_info()
    
    # 创建测试文件
    test_files = create_test_files()
    
    # 测试文件解析
    if test_files:
        print(f"\n开始测试 {len(test_files)} 个测试文件...")
        for file_path in test_files:
            test_single_file(file_path)
    
    # 测试现有文件
    test_file_parser_service()
    
    # 测试API端点
    test_api_endpoints()
    
    print("\n=== 测试完成 ===")
    print("如果遇到错误，请检查:")
    print("1. 是否安装了所有必要的依赖库")
    print("2. 服务器是否正在运行")
    print("3. 文件路径是否正确")

if __name__ == "__main__":
    main() 