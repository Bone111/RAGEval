from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from typing import List
from app.api.deps import get_db, get_current_user
from app.schemas.report import Report, ReportCreate, ReportUpdate
from app.models.report import Report as ReportModel
from app.models.user import User
from app.models.accuracy import AccuracyTest, AccuracyTestItem
from app.models.project import Project
from app.models.dataset import Dataset
from app.services.report_generator_service import ReportGeneratorService

router = APIRouter()

@router.get("/", response_model=List[Report])
def get_reports(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取项目的所有报告，自动为已完成评测生成报告"""
    # 1. 获取现有的报告
    existing_reports = db.query(ReportModel).filter(
        ReportModel.project_id == project_id,
        ReportModel.user_id == current_user.id
    ).all()
    
    # 2. 获取已完成但未生成报告的评测
    completed_tests = db.query(AccuracyTest).filter(
        AccuracyTest.project_id == project_id,
        AccuracyTest.status == "completed"
    ).all()
    
    # 3. 为未生成报告的评测自动生成报告
    report_generator = ReportGeneratorService(db)
    new_reports = []
    
    for test in completed_tests:
        # 检查是否已有报告
        has_report = any(
            report.config and report.config.get('test_id') == str(test.id)
            for report in existing_reports
        )
        
        if not has_report:
            try:
                # 生成报告
                report = report_generator.generate_accuracy_report(str(test.id), str(current_user.id))
                if report:
                    new_reports.append(report)
            except Exception as e:
                print(f"自动生成报告失败: test_id={test.id}, error={str(e)}")
    
    # 4. 返回所有报告（现有 + 新生成）
    all_reports = existing_reports + new_reports
    return sorted(all_reports, key=lambda x: x.created_at, reverse=True)

# 移除手动创建报告接口，报告应该基于评测自动生成

@router.get("/{report_id}", response_model=Report)
def get_report(
    report_id: str,
    force_refresh: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取报告详情，支持实时生成内容"""
    report = db.query(ReportModel).filter(
        ReportModel.id == report_id,
        ReportModel.user_id == current_user.id
    ).first()
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")
    
    # 如果是评测报告且有测试ID，检查是否需要更新内容
    if report.report_type == "evaluation" and report.config and report.config.get("test_id"):
        test_id = report.config["test_id"]
        
        # 检查测试是否有更新（通过updated_at时间戳）
        test = db.query(AccuracyTest).filter(AccuracyTest.id == test_id).first()
        if test:
            # 如果强制刷新或测试完成时间晚于报告更新时间，则重新生成内容
            if force_refresh or (test.completed_at and report.updated_at and test.completed_at > report.updated_at):
                try:
                    report_generator = ReportGeneratorService(db)
                    updated_content = report_generator._generate_accuracy_report_content(
                        test, 
                        db.query(Project).filter(Project.id == test.project_id).first(),
                        db.query(Dataset).filter(Dataset.id == test.dataset_id).first(),
                        db.query(AccuracyTestItem).filter(AccuracyTestItem.evaluation_id == test_id).all()
                    )
                    
                    # 更新报告内容
                    report.content = updated_content
                    report.updated_at = func.now()
                    db.commit()
                    db.refresh(report)
                    
                except Exception as e:
                    # 如果生成失败，记录日志但不影响返回现有内容
                    print(f"更新报告内容失败: {str(e)}")
    
    return report

# 移除更新报告接口，报告内容由系统自动生成，不允许手动修改

@router.delete("/{report_id}")
def delete_report(
    report_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除报告（仅限手动创建的报告）"""
    report = db.query(ReportModel).filter(
        ReportModel.id == report_id,
        ReportModel.user_id == current_user.id
    ).first()
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")
    
    # 检查是否为手动创建的报告（通过config字段判断）
    if report.config and report.config.get('manual_created'):
        db.delete(report)
        db.commit()
        return {"message": "报告已删除"}
    else:
        raise HTTPException(status_code=400, detail="无法删除自动生成的报告")

@router.post("/generate/accuracy/{test_id}", response_model=Report)
def generate_accuracy_report(
    test_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """手动生成精度评测报告"""
    report_generator = ReportGeneratorService(db)
    report = report_generator.generate_accuracy_report(test_id, str(current_user.id))
    if not report:
        raise HTTPException(status_code=404, detail="评测不存在或未完成")
    return report

@router.post("/generate/performance/{test_id}", response_model=Report)
def generate_performance_report(
    test_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """手动生成性能测试报告"""
    report_generator = ReportGeneratorService(db)
    report = report_generator.generate_performance_report(test_id, str(current_user.id))
    if not report:
        raise HTTPException(status_code=404, detail="测试不存在或未完成")
    return report

@router.post("/generate/comparison", response_model=Report)
def generate_comparison_report(
    data: dict = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """生成对比报告"""
    test_ids = data.get("test_ids", [])
    project_id = data.get("project_id")
    
    if not test_ids or not project_id:
        raise HTTPException(status_code=400, detail="缺少必要参数: test_ids 和 project_id")
    
    report_generator = ReportGeneratorService(db)
    report = report_generator.generate_comparison_report(test_ids, str(current_user.id), project_id)
    if not report:
        raise HTTPException(status_code=404, detail="测试不存在或项目不存在")
    return report

@router.get("/{report_id}/export")
def export_report(
    report_id: str,
    format: str = "pdf",  # pdf, html, json
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """导出报告"""
    report = db.query(ReportModel).filter(
        ReportModel.id == report_id,
        ReportModel.user_id == current_user.id
    ).first()
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")
    
    # 这里可以根据format参数生成不同格式的报告
    # 目前返回JSON格式，后续可以扩展为PDF或HTML
    return {
        "report": report,
        "format": format,
        "export_url": f"/api/v1/reports/{report_id}/download/{format}"
    }

# 移除分享功能
