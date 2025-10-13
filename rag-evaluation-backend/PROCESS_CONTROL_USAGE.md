# 进程控制使用说明

## 概述

新的进程控制机制提供了更可靠的任务暂停和继续功能：

- **暂停**: 直接终止所有相关的EvalScope进程
- **继续**: 使用现有结果继续执行，支持断点续评

## 核心组件

### 1. ProcessManager 进程管理器

位置: `app/core/process_manager.py`

主要功能:
- 保存和管理进程信息
- 终止相关进程
- 检查现有结果
- 获取任务状态

### 2. 更新的API接口

#### 暂停任务
```http
POST /api/v1/evalscope/tasks/{task_id}/pause
```

响应:
```json
{
  "success": true,
  "message": "任务已暂停，终止了 3 个进程: mmlu, gsm8k, cmmlu",
  "terminated_processes": ["mmlu", "gsm8k", "cmmlu"]
}
```

#### 继续任务
```http
POST /api/v1/evalscope/tasks/{task_id}/resume
```

响应:
```json
{
  "success": true,
  "message": "任务已恢复，将从断点继续执行，可继续的数据集: mmlu, gsm8k",
  "resumable_datasets": ["mmlu", "gsm8k"]
}
```

#### 获取进程状态
```http
GET /api/v1/evalscope/tasks/{task_id}/process-status
```

响应:
```json
{
  "success": true,
  "task_id": 219,
  "task_status": "running",
  "process_status": {
    "status": "running",
    "running_processes": [
      {
        "dataset_name": "mmlu",
        "pid": 88442,
        "status": "running",
        "start_time": 1760325577.1065578,
        "cmd_args": ["python", "-m", "evalscope.cli.cli", "eval", "..."]
      }
    ],
    "paused_processes": [],
    "total_processes": 1
  }
}
```

## 使用流程

### 1. 启动任务
任务启动时，进程管理器会自动保存每个数据集的进程信息到 `./outputs/evalscope_task_{task_id}/process_info.json`

### 2. 暂停任务
```python
# 前端调用暂停API
response = requests.post(f"/api/v1/evalscope/tasks/{task_id}/pause")

# 进程管理器会：
# 1. 查找所有相关进程
# 2. 终止进程及其子进程
# 3. 更新进程状态
# 4. 返回终止的进程列表
```

### 3. 继续任务
```python
# 前端调用继续API
response = requests.post(f"/api/v1/evalscope/tasks/{task_id}/resume")

# 进程管理器会：
# 1. 检查现有结果文件
# 2. 返回可继续的数据集列表
# 3. 重新启动任务（使用EvalScope的use_cache功能）
```

## 进程信息文件格式

`./outputs/evalscope_task_{task_id}/process_info.json`:

```json
{
  "processes": [
    {
      "task_id": 219,
      "dataset_name": "mmlu",
      "pid": 88442,
      "cmd_args": ["python", "-m", "evalscope.cli.cli", "eval", "..."],
      "start_time": 1760325577.1065578,
      "status": "running"
    }
  ]
}
```

## 优势

1. **可靠性**: 直接控制进程，不依赖Celery的取消机制
2. **完整性**: 终止进程及其所有子进程
3. **可恢复**: 支持断点续评，利用现有结果
4. **透明性**: 提供详细的进程状态信息
5. **独立性**: 进程控制独立于任务调度系统

## 注意事项

1. 进程信息文件会在任务完成后自动清理
2. 暂停操作会强制终止进程，可能导致数据不完整
3. 继续操作会检查现有结果文件，确保数据完整性
4. 进程管理器使用psutil库，需要安装: `pip install psutil`

## 测试

运行测试脚本:
```bash
python3 test_process_manager.py
```

测试内容包括:
- 进程信息保存和加载
- 任务状态获取
- 现有结果检查
- 进程暂停和继续
- 真实进程控制测试
