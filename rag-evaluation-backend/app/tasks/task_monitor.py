"""
任务监控和自动恢复机制
用于检测卡住的任务并自动标记为失败
"""
import logging
from datetime import datetime, timedelta
from typing import List

from app.db.base import SessionLocal
from app.models.evalscope_task import EvalScopeTask

logger = logging.getLogger(__name__)


def check_stuck_tasks(timeout_minutes: int = 30) -> List[int]:
    """
    检查卡住的任务
    
    Args:
        timeout_minutes: 超时时间（分钟）
        
    Returns:
        被标记为失败的任务ID列表
    """
    db = SessionLocal()
    fixed_task_ids = []
    
    try:
        # 查找状态为running但运行时间超过timeout_minutes的任务
        cutoff_time = datetime.now() - timedelta(minutes=timeout_minutes)
        
        stuck_tasks = db.query(EvalScopeTask).filter(
            EvalScopeTask.status == 'running',
            EvalScopeTask.started_at < cutoff_time
        ).all()
        
        if stuck_tasks:
            logger.warning(f"发现 {len(stuck_tasks)} 个卡住的任务")
            
            for task in stuck_tasks:
                running_time = datetime.now() - task.started_at
                logger.warning(
                    f"任务 {task.id} ({task.task_name}) 已运行 {running_time}，"
                    f"超过 {timeout_minutes} 分钟，标记为失败"
                )
                
                task.status = 'failed'
                task.error_message = (
                    f"任务超时自动终止。运行时间: {running_time}。"
                    f"可能原因: Worker进程异常、网络问题或任务卡死。"
                    f"请检查日志后重新创建任务。"
                )
                task.completed_at = datetime.now()
                task.progress = 0
                
                fixed_task_ids.append(task.id)
            
            db.commit()
            logger.info(f"已将 {len(fixed_task_ids)} 个卡住的任务标记为失败")
        else:
            logger.debug("未发现卡住的任务")
            
    except Exception as e:
        logger.error(f"检查卡住任务时出错: {e}")
        db.rollback()
    finally:
        db.close()
    
    return fixed_task_ids


def monitor_task_health():
    """
    任务健康检查的主函数
    可以被定时任务调用
    """
    logger.info("开始任务健康检查...")
    fixed_task_ids = check_stuck_tasks(timeout_minutes=30)
    
    if fixed_task_ids:
        logger.warning(f"任务健康检查完成，修复了 {len(fixed_task_ids)} 个任务: {fixed_task_ids}")
    else:
        logger.info("任务健康检查完成，所有任务正常")
    
    return fixed_task_ids


if __name__ == "__main__":
    # 命令行执行
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    monitor_task_health()

