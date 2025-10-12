"""
报告生成服务
支持生成PDF、Excel等格式的评测报告
"""
import os
import json
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import logging

# PDF生成
try:
    from reportlab.lib.pagesizes import A4, letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    from reportlab.platypus import Image as RLImage
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

# Excel生成
try:
    import pandas as pd
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    from openpyxl.utils.dataframe import dataframe_to_rows
    EXCEL_AVAILABLE = True
except ImportError:
    EXCEL_AVAILABLE = False

# Markdown和HTML转换
try:
    import markdown
    from markdown.extensions import tables, codehilite, toc
    MARKDOWN_AVAILABLE = True
except ImportError:
    MARKDOWN_AVAILABLE = False

# HTML转PDF工具
try:
    import subprocess
    import webbrowser
    HTML_TO_PDF_AVAILABLE = True
except ImportError:
    HTML_TO_PDF_AVAILABLE = False

# 图表生成
try:
    import matplotlib.pyplot as plt
    import matplotlib
    matplotlib.use('Agg')  # 使用非交互式后端
    import seaborn as sns
    import numpy as np
    CHARTS_AVAILABLE = True
except ImportError:
    CHARTS_AVAILABLE = False

logger = logging.getLogger(__name__)

class ReportService:
    """报告生成服务"""
    
    def __init__(self):
        self.supported_formats = ['pdf', 'excel', 'html']
        self.temp_dir = tempfile.mkdtemp()
        
    def generate_report(
        self, 
        task_ids: List[str], 
        report_config: Dict[str, Any],
        db_session
    ) -> Tuple[str, str]:
        """
        生成评测报告
        
        Args:
            task_ids: 评测任务ID列表
            report_config: 报告配置
            db_session: 数据库会话
            
        Returns:
            Tuple[文件路径, 文件名]
        """
        try:
            # 获取任务数据
            tasks_data = self._get_tasks_data(task_ids, db_session)
            if not tasks_data:
                raise ValueError("未找到有效的评测任务数据")
            
            # 根据格式生成报告
            format_type = report_config.get('format', 'pdf')
            
            if format_type == 'pdf':
                return self._generate_pdf_report(tasks_data, report_config)
            elif format_type == 'excel':
                return self._generate_excel_report(tasks_data, report_config)
            elif format_type == 'html':
                return self._generate_html_report(tasks_data, report_config)
            else:
                raise ValueError(f"不支持的报告格式: {format_type}")
                
        except Exception as e:
            logger.error(f"生成报告失败: {str(e)}")
            raise
    
    def _get_tasks_data(self, task_ids: List[str], db_session) -> List[Dict[str, Any]]:
        """获取任务数据"""
        from app.models.evalscope_task import EvalScopeTask, EvalScopeResult
        
        tasks_data = []
        
        for task_id in task_ids:
            # 获取任务基本信息
            task = db_session.query(EvalScopeTask).filter(
                EvalScopeTask.id == task_id
            ).first()
            
            if not task:
                logger.warning(f"任务 {task_id} 不存在")
                continue
            
            # 获取评测结果
            results = db_session.query(EvalScopeResult).filter(
                EvalScopeResult.task_id == task_id
            ).all()
            
            if not results:
                logger.warning(f"任务 {task_id} 没有评测结果")
                continue
            
            # 整理数据
            task_data = {
                'task_id': task.id,
                'task_name': task.task_name,
                'model_id': task.model_id,
                'datasets': task.datasets,
                'status': task.status,
                'created_at': task.created_at,
                'completed_at': task.completed_at,
                'results': []
            }
            
            # 整理结果数据
            for result in results:
                task_data['results'].append({
                    'benchmark': result.benchmark,
                    'metric_name': result.metric_name,
                    'metric_value': result.metric_value,
                    'category': result.category,
                    'subset_name': result.subset_name,
                    'num_samples': result.num_samples,
                    'raw_results': result.raw_results
                })
            
            tasks_data.append(task_data)
        
        return tasks_data
    
    def _generate_pdf_report(self, tasks_data: List[Dict[str, Any]], config: Dict[str, Any]) -> Tuple[str, str]:
        """生成PDF报告 - 使用Markdown转HTML再转PDF的方案"""
        try:
            # 优先使用Markdown转PDF方案
            return self._generate_pdf_via_markdown(tasks_data, config)
        except Exception as e:
            logger.warning(f"Markdown转PDF失败，回退到reportlab: {e}")
            # 回退到原来的reportlab方案
            return self._generate_pdf_via_reportlab(tasks_data, config)
    
    def _generate_pdf_via_markdown(self, tasks_data: List[Dict[str, Any]], config: Dict[str, Any]) -> Tuple[str, str]:
        """通过Markdown转HTML再转PDF生成报告"""
        if not MARKDOWN_AVAILABLE:
            raise ImportError("Markdown库未安装，请安装 markdown")
        
        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"EvalScope_Report_{timestamp}.pdf"
        filepath = os.path.join(self.temp_dir, filename)
        
        # 生成Markdown内容
        md_content = self._generate_markdown_content(tasks_data, config)
        
        # 转换Markdown为HTML
        html_content = self._convert_markdown_to_html(md_content)
        
        # 转换HTML为PDF
        self._convert_html_to_pdf(html_content, filepath)
        
        logger.info(f"PDF报告生成成功 (Markdown方案): {filepath}")
        return filepath, filename
    
    def _generate_pdf_via_reportlab(self, tasks_data: List[Dict[str, Any]], config: Dict[str, Any]) -> Tuple[str, str]:
        """使用reportlab生成PDF报告（原方案）"""
        if not PDF_AVAILABLE:
            raise ImportError("PDF生成库未安装，请安装 reportlab")
        
        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"EvalScope_Report_{timestamp}.pdf"
        filepath = os.path.join(self.temp_dir, filename)
        
        # 创建PDF文档
        doc = SimpleDocTemplate(
            filepath,
            pagesize=A4,
            rightMargin=50,
            leftMargin=50,
            topMargin=50,
            bottomMargin=50
        )
        
        # 获取样式
        styles = getSampleStyleSheet()
        
        # 自定义样式 - 简化版本避免超时
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            spaceAfter=20,
            alignment=TA_CENTER,
            textColor=colors.darkblue,
            fontName='Helvetica-Bold'
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=16,
            spaceAfter=12,
            textColor=colors.darkblue,
            fontName='Helvetica-Bold'
        )
        
        subheading_style = ParagraphStyle(
            'CustomSubHeading',
            parent=styles['Heading3'],
            fontSize=14,
            spaceAfter=8,
            textColor=colors.blue,
            fontName='Helvetica-Bold'
        )
        
        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontSize=11,
            spaceAfter=6,
            textColor=colors.black,
            fontName='Helvetica'
        )
        
        # 构建内容
        story = []
        
        # 标题区域
        title = config.get('customTitle', 'EvalScope 评测报告')
        story.append(Paragraph(title, title_style))
        
        # 添加分隔线
        story.append(Spacer(1, 10))
        story.append(Paragraph("─" * 80, normal_style))
        story.append(Spacer(1, 15))
        
        # 报告概览卡片
        overview_data = [
            ['生成时间', datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
            ['评测任务数', str(len(tasks_data))],
            ['报告模板', config.get('template', 'standard')],
            ['输出格式', config.get('format', 'pdf').upper()]
        ]
        
        overview_table = Table(overview_data, colWidths=[2*inch, 4*inch])
        overview_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 1), (-1, -1), 10)
        ]))
        
        story.append(overview_table)
        story.append(Spacer(1, 25))
        
        # 执行摘要
        if config.get('includeSummary', True):
            story.append(Paragraph("执行摘要", heading_style))
            
            # 添加分隔线
            story.append(Paragraph("─" * 60, normal_style))
            story.append(Spacer(1, 8))
            
            summary_text = self._generate_summary(tasks_data)
            story.append(Paragraph(summary_text, normal_style))
            story.append(Spacer(1, 25))
        
        # 评测任务详情
        story.append(Paragraph("评测任务详情", heading_style))
        
        # 添加分隔线
        story.append(Paragraph("─" * 60, normal_style))
        story.append(Spacer(1, 12))
        
        for task_data in tasks_data:
            # 任务标题卡片
            task_title = f"{task_data['task_name']} ({task_data['model_id']})"
            story.append(Paragraph(task_title, subheading_style))
            
            # 任务信息表格
            task_info = [
                ['模型ID', task_data['model_id']],
                ['数据集', ', '.join(task_data['datasets'])],
                ['状态', task_data['status']],
                ['完成时间', task_data['completed_at'].strftime('%Y-%m-%d %H:%M:%S') if task_data['completed_at'] else 'N/A']
            ]
            
            task_table = Table(task_info, colWidths=[1.5*inch, 4.5*inch])
            task_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 11),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('FONTSIZE', (0, 1), (-1, -1), 10)
            ]))
            
            story.append(task_table)
            story.append(Spacer(1, 15))
            
            # 评测结果表格
            if task_data['results']:
                story.append(Paragraph("评测结果", subheading_style))
                
                results_data = [['数据集', '指标', '子集', '分数', '样本数']]
                
                for result in task_data['results']:
                    score_text = f"{result['metric_value']:.4f}" if result['metric_value'] is not None else 'N/A'
                    results_data.append([
                        result['benchmark'],
                        result['metric_name'],
                        result['subset_name'],
                        score_text,
                        str(result['num_samples']) if result['num_samples'] else 'N/A'
                    ])
                
                results_table = Table(results_data, colWidths=[1.2*inch, 1.5*inch, 1.2*inch, 1*inch, 0.8*inch])
                results_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.blue),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('FONTSIZE', (0, 1), (-1, -1), 9)
                ]))
                
                story.append(results_table)
            
            story.append(Spacer(1, 25))
            
            # 如果不是最后一个任务，添加分页
            if task_data != tasks_data[-1]:
                story.append(PageBreak())
        
        # 报告配置信息
        story.append(Paragraph("报告配置", heading_style))
        
        # 添加分隔线
        story.append(Paragraph("─" * 60, normal_style))
        story.append(Spacer(1, 8))
        
        config_items = []
        if config.get('includeCharts', False):
            config_items.append('图表和可视化')
        if config.get('includeRawData', False):
            config_items.append('原始数据')
        if config.get('includeModelComparison', False):
            config_items.append('模型对比分析')
        if config.get('includeSummary', False):
            config_items.append('执行摘要')
        
        config_text = f"包含内容: {', '.join(config_items) if config_items else '无'}"
        story.append(Paragraph(config_text, normal_style))
        
        # 页脚信息
        story.append(Spacer(1, 20))
        footer_text = f"报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | EvalScope 评测系统"
        story.append(Paragraph(footer_text, ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=8,
            alignment=TA_CENTER,
            textColor=colors.grey,
            fontName='Helvetica'
        )))
        
        # 生成PDF
        doc.build(story)
        
        logger.info(f"PDF报告生成成功 (reportlab方案): {filepath}")
        return filepath, filename
    
    def _generate_markdown_content(self, tasks_data: List[Dict[str, Any]], config: Dict[str, Any]) -> str:
        """生成Markdown格式的报告内容"""
        title = config.get('customTitle', 'EvalScope 评测报告')
        template = config.get('template', 'standard')
        
        # 根据模板生成不同的内容结构
        if template == 'executive':
            return self._generate_executive_markdown(tasks_data, config, title)
        elif template == 'detailed':
            return self._generate_detailed_markdown(tasks_data, config, title)
        else:  # standard
            return self._generate_standard_markdown(tasks_data, config, title)
    
    def _generate_standard_markdown(self, tasks_data: List[Dict[str, Any]], config: Dict[str, Any], title: str) -> str:
        """生成标准报告Markdown内容"""
        md_content = f"""# {title}

---

## 报告概览

| 项目 | 值 |
|------|-----|
| 生成时间 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} |
| 评测任务数 | {len(tasks_data)} |
| 报告模板 | 标准报告 |
| 输出格式 | {config.get('format', 'pdf').upper()} |

---

## 执行摘要

{self._generate_summary(tasks_data)}

---

## 评测任务详情

"""
        
        for i, task_data in enumerate(tasks_data, 1):
            md_content += f"""### {i}. {task_data['task_name']} ({task_data['model_id']})

#### 任务信息

| 项目 | 值 |
|------|-----|
| 模型ID | {task_data['model_id']} |
| 数据集 | {', '.join(task_data['datasets'])} |
| 状态 | {task_data['status']} |
| 完成时间 | {task_data['completed_at'].strftime('%Y-%m-%d %H:%M:%S') if task_data['completed_at'] else 'N/A'} |

"""
            
            if task_data['results']:
                md_content += """#### 评测结果

| 数据集 | 指标 | 子集 | 分数 | 样本数 |
|--------|------|------|------|--------|
"""
                for result in task_data['results']:
                    score_text = f"{result['metric_value']:.4f}" if result['metric_value'] is not None else 'N/A'
                    md_content += f"| {result['benchmark']} | {result['metric_name']} | {result['subset_name']} | {score_text} | {result['num_samples'] if result['num_samples'] else 'N/A'} |\n"
            
            md_content += "\n---\n\n"
        
        # 报告配置信息
        config_items = []
        if config.get('includeCharts', False):
            config_items.append('图表和可视化')
        if config.get('includeRawData', False):
            config_items.append('原始数据')
        if config.get('includeModelComparison', False):
            config_items.append('模型对比分析')
        if config.get('includeSummary', False):
            config_items.append('执行摘要')
        
        config_text = ', '.join(config_items) if config_items else '无'
        
        md_content += f"""## 报告配置

**包含内容**: {config_text}

---

*报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | EvalScope 评测系统*
"""
        
        return md_content
    
    def _generate_detailed_markdown(self, tasks_data: List[Dict[str, Any]], config: Dict[str, Any], title: str) -> str:
        """生成详细报告Markdown内容"""
        md_content = f"""# {title}

---

## 报告概览

| 项目 | 值 |
|------|-----|
| 生成时间 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} |
| 评测任务数 | {len(tasks_data)} |
| 报告模板 | 详细报告 |
| 输出格式 | {config.get('format', 'pdf').upper()} |

---

## 执行摘要

{self._generate_detailed_summary(tasks_data)}

---

## 评测任务详情

"""
        
        for i, task_data in enumerate(tasks_data, 1):
            md_content += f"""### {i}. {task_data['task_name']} ({task_data['model_id']})

#### 任务信息

| 项目 | 值 |
|------|-----|
| 模型ID | {task_data['model_id']} |
| 数据集 | {', '.join(task_data['datasets'])} |
| 状态 | {task_data['status']} |
| 完成时间 | {task_data['completed_at'].strftime('%Y-%m-%d %H:%M:%S') if task_data['completed_at'] else 'N/A'} |

"""
            
            if task_data['results']:
                md_content += """#### 评测结果

| 数据集 | 指标 | 子集 | 分数 | 样本数 | 评级 |
|--------|------|------|------|--------|------|
"""
                for result in task_data['results']:
                    score_text = f"{result['metric_value']:.4f}" if result['metric_value'] is not None else 'N/A'
                    score = result['metric_value'] if result['metric_value'] is not None else 0
                    if score >= 0.8:
                        grade = '优秀'
                    elif score >= 0.6:
                        grade = '良好'
                    elif score >= 0.4:
                        grade = '一般'
                    else:
                        grade = '较差'
                    md_content += f"| {result['benchmark']} | {result['metric_name']} | {result['subset_name']} | {score_text} | {result['num_samples'] if result['num_samples'] else 'N/A'} | {grade} |\n"
            
            # 添加错误分析
            md_content += """
#### 错误分析

基于评测结果，我们发现以下关键问题：

1. **性能瓶颈**: 某些数据集上表现不佳，需要进一步优化
2. **数据质量**: 部分样本可能存在标注问题
3. **模型适应性**: 模型在不同类型任务上的表现差异较大

#### 改进建议

1. **模型优化**: 针对低分数据集进行专门训练
2. **数据增强**: 增加困难样本的训练数据
3. **超参数调优**: 针对特定任务调整模型参数

"""
            md_content += "\n---\n\n"
        
        # 模型对比分析
        md_content += """## 模型对比分析

| 模型 | 平均分数 | 排名 | 优势领域 | 改进空间 |
|------|----------|------|----------|----------|
"""
        
        # 计算模型对比数据
        model_scores = {}
        for task_data in tasks_data:
            if task_data['results']:
                scores = [r['metric_value'] for r in task_data['results'] if r['metric_value'] is not None]
                if scores:
                    avg_score = sum(scores) / len(scores)
                    model_scores[task_data['model_id']] = avg_score
        
        sorted_models = sorted(model_scores.items(), key=lambda x: x[1], reverse=True)
        for rank, (model, score) in enumerate(sorted_models, 1):
            md_content += f"| {model} | {score:.4f} | {rank} | 综合表现良好 | 持续优化 |\n"
        
        md_content += f"""

---

## 报告配置

**包含内容**: 详细评测数据、错误分析、模型对比、改进建议

---

*报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | EvalScope 评测系统*
"""
        
        return md_content
    
    def _generate_executive_markdown(self, tasks_data: List[Dict[str, Any]], config: Dict[str, Any], title: str) -> str:
        """生成执行摘要Markdown内容"""
        md_content = f"""# {title}

---

## 执行摘要

{self._generate_executive_summary(tasks_data)}

---

## 关键发现

### 性能指标概览

| 关键指标 | 数值 | 状态 |
|----------|------|------|
"""
        
        # 计算关键指标
        total_tasks = len(tasks_data)
        completed_tasks = len([t for t in tasks_data if t['status'] == 'completed'])
        
        all_scores = []
        for task_data in tasks_data:
            if task_data['results']:
                scores = [r['metric_value'] for r in task_data['results'] if r['metric_value'] is not None]
                all_scores.extend(scores)
        
        avg_score = sum(all_scores) / len(all_scores) if all_scores else 0
        max_score = max(all_scores) if all_scores else 0
        min_score = min(all_scores) if all_scores else 0
        
        # 生成状态指示器
        def get_status_indicator(score=None, is_good=True):
            if score is not None:
                if score >= 0.8:
                    return "优秀"
                elif score >= 0.6:
                    return "良好"
                elif score >= 0.4:
                    return "一般"
                else:
                    return "较差"
            return "正常" if is_good else "异常"
        
        md_content += f"""| 评测任务数 | {total_tasks} | {get_status_indicator(is_good=True)} |
| 完成率 | {(completed_tasks/total_tasks*100):.1f}% | {get_status_indicator(is_good=True)} |
| 平均分数 | {avg_score:.4f} | {get_status_indicator(avg_score)} |
| 最高分数 | {max_score:.4f} | {get_status_indicator(max_score)} |
| 最低分数 | {min_score:.4f} | {get_status_indicator(min_score)} |

---

## 建议行动

### 短期行动 (1-2周)
1. **性能优化**: 针对低分模型进行调优
2. **数据质量**: 检查并修正问题数据集
3. **监控机制**: 建立持续评测流程

### 中期行动 (1-2月)
1. **模型升级**: 考虑引入更先进的模型架构
2. **数据扩充**: 增加训练数据规模
3. **团队培训**: 提升团队技术能力

### 长期规划 (3-6月)
1. **技术路线**: 制定模型发展路线图
2. **资源投入**: 规划人力和计算资源
3. **业务整合**: 将评测结果应用到实际业务

---

## 风险提示

- **性能风险**: 部分模型在某些任务上表现不佳
- **数据风险**: 数据集质量可能影响评测结果
- **技术风险**: 模型更新可能影响现有性能

---

*报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | EvalScope 评测系统*
"""
        
        return md_content
    
    def _convert_markdown_to_html(self, md_content: str) -> str:
        """将Markdown内容转换为HTML"""
        if not MARKDOWN_AVAILABLE:
            raise ImportError("Markdown库未安装，请安装 markdown")
        
        # 配置markdown扩展
        md = markdown.Markdown(
            extensions=[
                'tables',  # 表格支持
                'codehilite',  # 代码高亮
                'fenced_code',  # 围栏代码块
                'attr_list',  # 属性列表
                'def_list',  # 定义列表
                'footnotes',  # 脚注
                'md_in_html',  # HTML中的markdown
            ],
            extension_configs={
                'codehilite': {
                    'css_class': 'highlight',
                    'use_pygments': False,
                }
            }
        )
        
        html_body = md.convert(md_content)
        
        # 应用评级样式
        html_body = html_body.replace('优秀', '<span class="grade-excellent">优秀</span>')
        html_body = html_body.replace('良好', '<span class="grade-good">良好</span>')
        html_body = html_body.replace('一般', '<span class="grade-average">一般</span>')
        html_body = html_body.replace('较差', '<span class="grade-poor">较差</span>')
        html_body = html_body.replace('正常', '<span class="status-normal">正常</span>')
        
        # 完整的HTML文档
        html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>EvalScope 评测报告</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', 'Helvetica Neue', Helvetica, Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background-color: #fff;
        }}
        
        h1 {{
            color: #2c3e50;
            text-align: center;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
            margin-bottom: 30px;
        }}
        
        h2 {{
            color: #34495e;
            border-bottom: 2px solid #3498db;
            padding-bottom: 5px;
            margin-top: 30px;
        }}
        
        h2:before {{
            content: "■ ";
            color: #3498db;
            font-weight: bold;
        }}
        
        h3 {{
            color: #3498db;
            margin-top: 25px;
        }}
        
        h4 {{
            color: #7f8c8d;
            margin-top: 20px;
        }}
        
        table {{
            border-collapse: collapse;
            width: 100%;
            margin: 15px 0;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        
        th, td {{
            border: 1px solid #ddd;
            padding: 12px;
            text-align: left;
        }}
        
        th {{
            background-color: #3498db;
            color: white;
            font-weight: bold;
        }}
        
        tr:nth-child(even) {{
            background-color: #f8f9fa;
        }}
        
        tr:hover {{
            background-color: #e8f4fd;
        }}
        
        hr {{
            border: none;
            border-top: 2px solid #ecf0f1;
            margin: 30px 0;
        }}
        
        code {{
            background-color: #f8f9fa;
            padding: 2px 4px;
            border-radius: 3px;
            font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
        }}
        
        pre {{
            background-color: #f8f9fa;
            padding: 15px;
            border-radius: 5px;
            overflow-x: auto;
        }}
        
        blockquote {{
            border-left: 4px solid #3498db;
            margin: 0;
            padding-left: 20px;
            color: #7f8c8d;
        }}
        
        .highlight {{
            background-color: #f8f9fa;
            padding: 15px;
            border-radius: 5px;
            overflow-x: auto;
        }}
        
        /* 评级样式 */
        .grade-excellent {{
            background-color: #d4edda;
            color: #155724;
            padding: 4px 8px;
            border-radius: 4px;
            font-weight: bold;
        }}
        
        .grade-good {{
            background-color: #d1ecf1;
            color: #0c5460;
            padding: 4px 8px;
            border-radius: 4px;
            font-weight: bold;
        }}
        
        .grade-average {{
            background-color: #fff3cd;
            color: #856404;
            padding: 4px 8px;
            border-radius: 4px;
            font-weight: bold;
        }}
        
        .grade-poor {{
            background-color: #f8d7da;
            color: #721c24;
            padding: 4px 8px;
            border-radius: 4px;
            font-weight: bold;
        }}
        
        .status-normal {{
            background-color: #d4edda;
            color: #155724;
            padding: 4px 8px;
            border-radius: 4px;
            font-weight: bold;
        }}
        
        /* PDF优化样式 */
        @media print {{
            body {{
                margin: 0;
                padding: 15px;
                font-size: 12px;
            }}
            
            h1 {{
                font-size: 20px;
            }}
            
            h2 {{
                font-size: 16px;
            }}
            
            h3 {{
                font-size: 14px;
            }}
            
            h1, h2, h3 {{
                page-break-after: avoid;
            }}
            
            table {{
                page-break-inside: avoid;
                font-size: 11px;
            }}
            
            /* PDF中的评级样式 */
            .grade-excellent, .status-normal {{
                background-color: #e8f5e8 !important;
                color: #2d5a2d !important;
            }}
            
            .grade-good {{
                background-color: #e8f4f8 !important;
                color: #2d4a5a !important;
            }}
            
            .grade-average {{
                background-color: #fff8e1 !important;
                color: #5a4a2d !important;
            }}
            
            .grade-poor {{
                background-color: #fde8e8 !important;
                color: #5a2d2d !important;
            }}
        }}
    </style>
</head>
<body>
    {html_body}
</body>
</html>"""
        
        return html_content
    
    def _convert_html_to_pdf(self, html_content: str, output_path: str) -> None:
        """将HTML转换为PDF"""
        # 保存HTML到临时文件
        html_file = os.path.join(self.temp_dir, f"temp_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html")
        
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        try:
            # 尝试使用wkhtmltopdf
            self._convert_with_wkhtmltopdf(html_file, output_path)
        except Exception as e:
            logger.warning(f"wkhtmltopdf转换失败: {e}")
            try:
                # 回退到weasyprint
                self._convert_with_weasyprint(html_content, output_path)
            except Exception as e2:
                logger.warning(f"weasyprint转换失败: {e2}")
                # 最后回退到浏览器打印
                self._convert_with_browser_print(html_file, output_path)
    
    def _convert_with_wkhtmltopdf(self, html_file: str, output_path: str) -> None:
        """使用wkhtmltopdf转换HTML为PDF"""
        cmd = [
            'wkhtmltopdf',
            '--page-size', 'A4',
            '--margin-top', '20mm',
            '--margin-right', '20mm',
            '--margin-bottom', '20mm',
            '--margin-left', '20mm',
            '--encoding', 'UTF-8',
            '--enable-local-file-access',
            '--disable-smart-shrinking',
            html_file,
            output_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(f"wkhtmltopdf失败: {result.stderr}")
    
    def _convert_with_weasyprint(self, html_content: str, output_path: str) -> None:
        """使用weasyprint转换HTML为PDF"""
        try:
            from weasyprint import HTML, CSS
            from weasyprint.text.fonts import FontConfiguration
            
            font_config = FontConfiguration()
            
            html_doc = HTML(string=html_content)
            css = CSS(string='''
                @page {
                    size: A4;
                    margin: 20mm;
                }
                body {
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', 'Helvetica Neue', Helvetica, Arial, sans-serif;
                }
            ''', font_config=font_config)
            
            html_doc.write_pdf(output_path, stylesheets=[css], font_config=font_config)
            
        except ImportError:
            raise Exception("weasyprint未安装")
    
    def _convert_with_browser_print(self, html_file: str, output_path: str) -> None:
        """使用浏览器打印功能转换HTML为PDF（备用方案）"""
        # 这是一个简化的备用方案，实际使用时可能需要更复杂的实现
        logger.warning("使用浏览器打印备用方案，可能效果不佳")
        
        # 复制HTML文件为PDF（临时方案）
        import shutil
        shutil.copy(html_file, output_path.replace('.pdf', '.html'))
        
        # 在实际环境中，这里应该调用浏览器的打印API
        # 例如使用selenium或playwright
        raise Exception("浏览器打印方案需要额外配置")
    
    def _generate_excel_report(self, tasks_data: List[Dict[str, Any]], config: Dict[str, Any]) -> Tuple[str, str]:
        """生成Excel报告"""
        if not EXCEL_AVAILABLE:
            raise ImportError("Excel生成库未安装，请安装 pandas 和 openpyxl")
        
        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"EvalScope_Report_{timestamp}.xlsx"
        filepath = os.path.join(self.temp_dir, filename)
        
        # 创建工作簿
        wb = Workbook()
        
        # 删除默认工作表
        wb.remove(wb.active)
        
        # 创建概览工作表
        overview_ws = wb.create_sheet("概览")
        self._create_overview_sheet(overview_ws, tasks_data, config)
        
        # 创建详细结果工作表
        details_ws = wb.create_sheet("详细结果")
        self._create_details_sheet(details_ws, tasks_data)
        
        # 创建模型对比工作表
        if config.get('includeModelComparison', True):
            comparison_ws = wb.create_sheet("模型对比")
            self._create_comparison_sheet(comparison_ws, tasks_data)
        
        # 保存文件
        wb.save(filepath)
        
        logger.info(f"Excel报告生成成功: {filepath}")
        return filepath, filename
    
    def _create_overview_sheet(self, ws, tasks_data: List[Dict[str, Any]], config: Dict[str, Any]):
        """创建概览工作表"""
        # 标题
        ws['A1'] = config.get('customTitle', 'EvalScope 评测报告')
        ws['A1'].font = Font(size=16, bold=True)
        ws['A1'].alignment = Alignment(horizontal='center')
        ws.merge_cells('A1:E1')
        
        # 报告信息
        ws['A3'] = '生成时间'
        ws['B3'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ws['A4'] = '评测任务数'
        ws['B4'] = len(tasks_data)
        ws['A5'] = '报告模板'
        ws['B5'] = config.get('template', 'standard')
        
        # 任务概览
        row = 7
        ws[f'A{row}'] = '任务概览'
        ws[f'A{row}'].font = Font(size=14, bold=True)
        row += 1
        
        # 表头
        headers = ['任务名称', '模型ID', '数据集', '状态', '完成时间']
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=row, column=col, value=header)
            cell.font = Font(bold=True)
            cell.fill = PatternFill(start_color='CCCCCC', end_color='CCCCCC', fill_type='solid')
        
        row += 1
        
        # 数据行
        for task_data in tasks_data:
            ws.cell(row=row, column=1, value=task_data['task_name'])
            ws.cell(row=row, column=2, value=task_data['model_id'])
            ws.cell(row=row, column=3, value=', '.join(task_data['datasets']))
            ws.cell(row=row, column=4, value=task_data['status'])
            ws.cell(row=row, column=5, value=task_data['completed_at'].strftime('%Y-%m-%d %H:%M:%S') if task_data['completed_at'] else 'N/A')
            row += 1
    
    def _create_details_sheet(self, ws, tasks_data: List[Dict[str, Any]]):
        """创建详细结果工作表"""
        # 标题
        ws['A1'] = '详细评测结果'
        ws['A1'].font = Font(size=16, bold=True)
        ws['A1'].alignment = Alignment(horizontal='center')
        ws.merge_cells('A1:G1')
        
        # 表头
        row = 3
        headers = ['任务名称', '模型ID', '数据集', '指标', '子集', '分数', '样本数']
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=row, column=col, value=header)
            cell.font = Font(bold=True)
            cell.fill = PatternFill(start_color='CCCCCC', end_color='CCCCCC', fill_type='solid')
        
        row += 1
        
        # 数据行
        for task_data in tasks_data:
            for result in task_data['results']:
                ws.cell(row=row, column=1, value=task_data['task_name'])
                ws.cell(row=row, column=2, value=task_data['model_id'])
                ws.cell(row=row, column=3, value=result['benchmark'])
                ws.cell(row=row, column=4, value=result['metric_name'])
                ws.cell(row=row, column=5, value=result['subset_name'])
                ws.cell(row=row, column=6, value=result['metric_value'] if result['metric_value'] is not None else 'N/A')
                ws.cell(row=row, column=7, value=result['num_samples'] if result['num_samples'] else 'N/A')
                row += 1
    
    def _create_comparison_sheet(self, ws, tasks_data: List[Dict[str, Any]]):
        """创建模型对比工作表"""
        # 标题
        ws['A1'] = '模型对比分析'
        ws['A1'].font = Font(size=16, bold=True)
        ws['A1'].alignment = Alignment(horizontal='center')
        ws.merge_cells('A1:D1')
        
        # 收集所有模型和数据集
        models = set()
        datasets = set()
        model_scores = {}
        
        for task_data in tasks_data:
            models.add(task_data['model_id'])
            for dataset in task_data['datasets']:
                datasets.add(dataset)
            
            # 计算平均分数
            if task_data['results']:
                scores = [r['metric_value'] for r in task_data['results'] if r['metric_value'] is not None]
                if scores:
                    avg_score = sum(scores) / len(scores)
                    model_scores[task_data['model_id']] = avg_score
        
        # 创建对比表格
        row = 3
        ws[f'A{row}'] = '模型'
        ws[f'B{row}'] = '平均分数'
        ws[f'C{row}'] = '排名'
        ws[f'D{row}'] = '评级'
        
        # 设置表头样式
        for col in range(1, 5):
            cell = ws.cell(row=row, column=col)
            cell.font = Font(bold=True)
            cell.fill = PatternFill(start_color='CCCCCC', end_color='CCCCCC', fill_type='solid')
        
        row += 1
        
        # 按分数排序
        sorted_models = sorted(model_scores.items(), key=lambda x: x[1], reverse=True)
        
        for rank, (model, score) in enumerate(sorted_models, 1):
            ws.cell(row=row, column=1, value=model)
            ws.cell(row=row, column=2, value=f"{score:.4f}")
            ws.cell(row=row, column=3, value=rank)
            
            # 评级
            if score >= 0.8:
                grade = '优秀'
            elif score >= 0.6:
                grade = '良好'
            elif score >= 0.4:
                grade = '一般'
            else:
                grade = '较差'
            
            ws.cell(row=row, column=4, value=grade)
            row += 1
    
    def _generate_html_report(self, tasks_data: List[Dict[str, Any]], config: Dict[str, Any]) -> Tuple[str, str]:
        """生成HTML报告 - 使用与PDF相同的Markdown转HTML方案"""
        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"EvalScope_Report_{timestamp}.html"
        filepath = os.path.join(self.temp_dir, filename)
        
        # 使用与PDF相同的Markdown内容生成方法
        md_content = self._generate_markdown_content(tasks_data, config)
        
        # 转换Markdown为HTML
        html_content = self._convert_markdown_to_html(md_content)
        
        # 写入文件
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        logger.info(f"HTML报告生成成功: {filepath}")
        return filepath, filename
    
    def _generate_summary(self, tasks_data: List[Dict[str, Any]]) -> str:
        """生成执行摘要"""
        total_tasks = len(tasks_data)
        completed_tasks = len([t for t in tasks_data if t['status'] == 'completed'])
        
        # 计算平均分数
        all_scores = []
        for task_data in tasks_data:
            if task_data['results']:
                scores = [r['metric_value'] for r in task_data['results'] if r['metric_value'] is not None]
                all_scores.extend(scores)
        
        avg_score = sum(all_scores) / len(all_scores) if all_scores else 0
        
        summary = f"""
        本次评测共包含 {total_tasks} 个任务，其中 {completed_tasks} 个任务已完成。
        评测涉及 {len(set(t['model_id'] for t in tasks_data))} 个不同的模型，
        覆盖 {len(set(dataset for t in tasks_data for dataset in t['datasets']))} 个数据集。
        
        整体评测结果：平均分数为 {avg_score:.4f}，表现{'优秀' if avg_score >= 0.8 else '良好' if avg_score >= 0.6 else '一般' if avg_score >= 0.4 else '较差'}。
        """
        
        return summary
    
    def _generate_detailed_summary(self, tasks_data: List[Dict[str, Any]]) -> str:
        """生成详细报告摘要"""
        total_tasks = len(tasks_data)
        completed_tasks = len([t for t in tasks_data if t['status'] == 'completed'])
        
        # 计算详细统计
        all_scores = []
        model_performance = {}
        
        for task_data in tasks_data:
            if task_data['results']:
                scores = [r['metric_value'] for r in task_data['results'] if r['metric_value'] is not None]
                all_scores.extend(scores)
                
                # 按模型统计
                if task_data['model_id'] not in model_performance:
                    model_performance[task_data['model_id']] = []
                model_performance[task_data['model_id']].extend(scores)
        
        avg_score = sum(all_scores) / len(all_scores) if all_scores else 0
        max_score = max(all_scores) if all_scores else 0
        min_score = min(all_scores) if all_scores else 0
        
        # 找出最佳和最差模型
        best_model = None
        worst_model = None
        if model_performance:
            model_avg_scores = {model: sum(scores)/len(scores) for model, scores in model_performance.items()}
            best_model = max(model_avg_scores.items(), key=lambda x: x[1])
            worst_model = min(model_avg_scores.items(), key=lambda x: x[1])
        
        summary = f"""
        本次详细评测共包含 {total_tasks} 个任务，其中 {completed_tasks} 个任务已完成。
        评测涉及 {len(set(t['model_id'] for t in tasks_data))} 个不同的模型，
        覆盖 {len(set(dataset for t in tasks_data for dataset in t['datasets']))} 个数据集。
        
        **性能统计**：
        - 平均分数：{avg_score:.4f} ({'优秀' if avg_score >= 0.8 else '良好' if avg_score >= 0.6 else '一般' if avg_score >= 0.4 else '较差'})
        - 最高分数：{max_score:.4f}
        - 最低分数：{min_score:.4f}
        - 分数范围：{max_score - min_score:.4f}
        
        **模型表现**：
        - 最佳模型：{best_model[0] if best_model else 'N/A'} (平均分：{best_model[1]:.4f} if best_model else 'N/A')
        - 需要改进：{worst_model[0] if worst_model else 'N/A'} (平均分：{worst_model[1]:.4f} if worst_model else 'N/A')
        
        **详细分析**：本报告包含错误分析、模型对比和改进建议，为模型优化提供数据支持。
        """
        
        return summary
    
    def _generate_executive_summary(self, tasks_data: List[Dict[str, Any]]) -> str:
        """生成执行摘要"""
        total_tasks = len(tasks_data)
        completed_tasks = len([t for t in tasks_data if t['status'] == 'completed'])
        
        # 计算关键指标
        all_scores = []
        for task_data in tasks_data:
            if task_data['results']:
                scores = [r['metric_value'] for r in task_data['results'] if r['metric_value'] is not None]
                all_scores.extend(scores)
        
        avg_score = sum(all_scores) / len(all_scores) if all_scores else 0
        completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
        
        summary = f"""
        **评测概览**
        本次评测共完成 {completed_tasks}/{total_tasks} 个任务，完成率 {completion_rate:.1f}%。
        涉及 {len(set(t['model_id'] for t in tasks_data))} 个模型，{len(set(dataset for t in tasks_data for dataset in t['datasets']))} 个数据集。
        
        **关键指标**
        - 整体性能：{avg_score:.4f} ({'优秀' if avg_score >= 0.8 else '良好' if avg_score >= 0.6 else '一般' if avg_score >= 0.4 else '较差'})
        - 任务完成率：{completion_rate:.1f}%
        - 评测规模：{len(all_scores)} 个评测结果
        
        **决策建议**
        基于评测结果，建议{'继续推进' if avg_score >= 0.8 else '优化改进' if avg_score >= 0.6 else '重点关注' if avg_score >= 0.4 else '紧急处理'}当前模型性能。
        """
        
        return summary
    
    def cleanup_temp_files(self):
        """清理临时文件"""
        try:
            import shutil
            shutil.rmtree(self.temp_dir)
            logger.info(f"清理临时目录: {self.temp_dir}")
        except Exception as e:
            logger.warning(f"清理临时文件失败: {str(e)}")
    
    def get_supported_formats(self) -> List[str]:
        """获取支持的格式"""
        return self.supported_formats.copy()
    
    def is_format_supported(self, format_type: str) -> bool:
        """检查格式是否支持"""
        return format_type.lower() in self.supported_formats
