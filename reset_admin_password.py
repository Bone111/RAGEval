#!/usr/bin/env python3
import psycopg2
import bcrypt
import sys

# 数据库连接配置
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'rag_evaluation',
    'user': 'postgres',
    'password': 'postgres'
}

def reset_admin_password():
    """重置管理员密码"""
    try:
        # 连接数据库
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # 新密码
        new_password = 'admin123'
        
        # 加密密码
        password_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        # 更新管理员密码
        cursor.execute("""
            UPDATE users 
            SET password_hash = %s 
            WHERE email = 'admin@rag.com'
        """, (password_hash,))
        
        # 提交更改
        conn.commit()
        
        print("✅ 管理员密码已重置！")
        print(f"邮箱: admin@rag.com")
        print(f"密码: {new_password}")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ 重置密码失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    print("正在重置管理员密码...")
    reset_admin_password() 