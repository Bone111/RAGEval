#!/usr/bin/env python3
"""
测试 mineru 异步转换功能
"""

import requests
import time
import json

def test_async_conversion():
    """测试异步转换功能"""
    
    # 测试文件路径（使用项目中的PDF文件）
    pdf_file = "../data/基于改进元胞自动机模型的烟气场景地下商场疏散管理研究_谢尊贤.pdf"
    
    print("开始测试异步转换功能...")
    
    # 1. 上传文件并创建异步任务
    print("1. 上传文件...")
    with open(pdf_file, 'rb') as f:
        files = {'file': f}
        response = requests.post('http://localhost:8000/api/v1/convert-to-md-async/', files=files)
    
    if response.status_code != 200:
        print(f"上传失败: {response.status_code}")
        print(response.text)
        return
    
    data = response.json()
    print(f"任务创建成功，任务ID: {data.get('task_id')}")
    
    task_id = data.get('task_id')
    if not task_id:
        print("未获取到任务ID")
        return
    
    # 2. 轮询进度
    print("2. 开始轮询进度...")
    while True:
        time.sleep(1)  # 等待1秒
        
        progress_response = requests.get(f'http://localhost:8000/api/v1/convert-progress/{task_id}')
        if progress_response.status_code != 200:
            print(f"获取进度失败: {progress_response.status_code}")
            break
        
        progress_data = progress_response.json()
        progress = progress_data.get('progress', 0)
        message = progress_data.get('message', '')
        step = progress_data.get('step', '')
        success = progress_data.get('success')
        
        print(f"进度: {progress}% - {step} - {message}")
        
        # 检查是否完成
        if success is True:
            print("转换完成！")
            break
        elif success is False:
            print(f"转换失败: {progress_data.get('error', '未知错误')}")
            break
    
    # 3. 获取结果
    print("3. 获取转换结果...")
    result_response = requests.get(f'http://localhost:8000/api/v1/convert-result/{task_id}')
    if result_response.status_code == 200:
        result_data = result_response.json()
        if result_data.get('success'):
            md_content = result_data.get('md_content', '')
            print(f"转换成功！Markdown内容长度: {len(md_content)} 字符")
            print("前500字符预览:")
            print(md_content[:500])
        else:
            print(f"获取结果失败: {result_data.get('error')}")
    else:
        print(f"获取结果请求失败: {result_response.status_code}")
    
    # 4. 清理任务
    print("4. 清理任务...")
    delete_response = requests.delete(f'http://localhost:8000/api/v1/convert-task/{task_id}')
    if delete_response.status_code == 200:
        print("任务清理成功")
    else:
        print("任务清理失败")

if __name__ == "__main__":
    test_async_conversion() 