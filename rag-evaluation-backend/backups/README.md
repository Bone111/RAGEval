# PostgreSQL数据库备份

## 备份信息

**备份时间**: 2025-10-12 15:40  
**数据库名**: rag_evaluation  
**PostgreSQL版本**: 14  

---

## 备份文件

### 1. 自定义格式备份（推荐用于恢复）
- **文件**: `rag_evaluation_backup_20251012_153954.dump`
- **大小**: 676 KB
- **格式**: PostgreSQL 自定义格式（压缩）
- **用途**: 完整备份，支持选择性恢复

**恢复方法**:
```bash
# 完整恢复到新数据库
createdb -h localhost -U postgres rag_evaluation_new
pg_restore -h localhost -U postgres -d rag_evaluation_new rag_evaluation_backup_20251012_153954.dump

# 只恢复特定表
pg_restore -h localhost -U postgres -d rag_evaluation -t users rag_evaluation_backup_20251012_153954.dump
```

### 2. SQL格式备份（方便查看）
- **文件**: `rag_evaluation_backup_20251012_154006.sql`
- **大小**: 2.6 MB
- **格式**: 纯SQL文本
- **用途**: 可读性强，便于检查和修改

**恢复方法**:
```bash
# 恢复整个数据库
psql -h localhost -U postgres -d rag_evaluation_new < rag_evaluation_backup_20251012_154006.sql
```

---

## 数据统计

备份包含以下主要数据：

| 表名 | 行数 | 大小 | 说明 |
|------|------|------|------|
| questions | 3,830 | 2.2 MB | 问题数据 |
| rag_answers | 827 | 656 KB | RAG回答 |
| accuracy_test_items | 253 | 528 KB | 精度测试项 |
| evalscope_tasks | 51 | 416 KB | 评测任务 |
| datasets | 24 | 32 KB | 数据集 |
| project_datasets | 23 | 40 KB | 项目数据集关联 |
| evalscope_results | 22 | 64 KB | 评测结果 |
| model_info | 12 | 208 KB | 模型信息 |
| performance_tests | 11 | 120 KB | 性能测试 |
| dataset_cache | 10 | 80 KB | 数据集缓存 |
| local_model_registry | 9 | 160 KB | 本地模型注册 |
| model_categories | 8 | 96 KB | 模型分类 |
| accuracy_test | 6 | 224 KB | 精度测试 |
| user_model_configs | 4 | 96 KB | 用户模型配置 |
| users | 2 | 48 KB | 用户账号 |

**总计**: 30个表，6,000+条记录

---

## 自动备份脚本

为了定期备份，可以使用以下脚本：

```bash
#!/bin/bash
# 自动备份PostgreSQL数据库

BACKUP_DIR="/Users/Bone/Documents/工作/10月/代码测试区/RAGEval/rag-evaluation-backend/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/auto_backup_$TIMESTAMP.dump"

# 执行备份
pg_dump -h localhost -U postgres -d rag_evaluation -F c -b -f "$BACKUP_FILE"

# 保留最近7天的备份
find "$BACKUP_DIR" -name "auto_backup_*.dump" -mtime +7 -delete

echo "✅ 备份完成: $BACKUP_FILE"
```

---

## 注意事项

1. ⚠️ **备份文件包含敏感数据**（用户密码哈希），请妥善保管
2. 🔒 建议定期备份（每天或每周）
3. 💾 建议将备份文件存储到其他位置（云存储、外部硬盘）
4. ✅ 定期测试备份恢复流程，确保备份可用

---

## 快速恢复指南

### 场景1: 数据库损坏，需要完全恢复

```bash
# 1. 删除旧数据库（谨慎！）
dropdb -h localhost -U postgres rag_evaluation

# 2. 创建新数据库
createdb -h localhost -U postgres rag_evaluation

# 3. 恢复备份
pg_restore -h localhost -U postgres -d rag_evaluation rag_evaluation_backup_20251012_153954.dump
```

### 场景2: 只恢复特定数据（如用户表）

```bash
pg_restore -h localhost -U postgres -d rag_evaluation -t users -c rag_evaluation_backup_20251012_153954.dump
```

### 场景3: 迁移到新服务器

```bash
# 在新服务器上
createdb -h new_server -U postgres rag_evaluation
pg_restore -h new_server -U postgres -d rag_evaluation rag_evaluation_backup_20251012_153954.dump
```

---

**备份创建时间**: 2025-10-12 15:40  
**备份有效性**: 已验证 ✅

