from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from typing import List
from app.api.deps import get_db, get_current_user
from app.schemas.report import Report, ReportCreate, ReportUpdate
from app.models.report import Report as ReportModel
from app.models.user import User
from app.services.report_generator_service import ReportGeneratorService

router = APIRouter()

@router.get("/", response_model=List[Report])
def get_reports(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取项目的所有报告"""
    reports = db.query(ReportModel).filter(
        ReportModel.project_id == project_id,
        ReportModel.user_id == current_user.id
    ).all()
    return reports

# 移除手动创建报告接口，报告应该基于评测自动生成

@router.get("/{report_id}", response_model=Report)
def get_report(
    report_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取报告详情"""
    report = db.query(ReportModel).filter(
        ReportModel.id == report_id,
        ReportModel.user_id == current_user.id
    ).first()
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")
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
