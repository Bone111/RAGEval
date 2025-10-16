#!/usr/bin/env python3
"""
用户密码重置工具
支持重置任意用户的密码
"""
import psycopg2
import bcrypt
import sys
import argparse

# 数据库连接配置
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'rag_evaluation',
    'user': 'postgres',
    'password': 'postgres'
}

def list_users():
    """列出所有用户"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT email, name, is_admin, is_active, created_at 
            FROM users 
            ORDER BY created_at DESC
        """)
        
        users = cursor.fetchall()
        
        print("\n" + "="*80)
        print("系统用户列表：")
        print("="*80)
        print(f"{'邮箱':<30} {'姓名':<15} {'管理员':<10} {'状态':<10} {'创建时间':<20}")
        print("-"*80)
        
        for user in users:
            email, name, is_admin, is_active, created_at = user
            admin_str = "是" if is_admin else "否"
            active_str = "激活" if is_active else "禁用"
            name_str = name if name else "-"
            created_str = created_at.strftime('%Y-%m-%d %H:%M:%S') if created_at else "-"
            print(f"{email:<30} {name_str:<15} {admin_str:<10} {active_str:<10} {created_str:<20}")
        
        print("="*80)
        print(f"共 {len(users)} 个用户\n")
        
        cursor.close()
        conn.close()
        
        return users
        
    except Exception as e:
        print(f"❌ 获取用户列表失败: {e}")
        sys.exit(1)

def reset_password(email, new_password=None):
    """重置指定用户的密码"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # 检查用户是否存在
        cursor.execute("SELECT email, name FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        
        if not user:
            print(f"❌ 用户不存在: {email}")
            cursor.close()
            conn.close()
            return False
        
        # 如果没有指定新密码，使用默认密码
        if not new_password:
            new_password = 'user123'
        
        # 加密密码
        password_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        # 更新密码
        cursor.execute("""
            UPDATE users 
            SET password_hash = %s, updated_at = now()
            WHERE email = %s
        """, (password_hash, email))
        
        # 提交更改
        conn.commit()
        
        print("\n" + "="*60)
        print("✅ 密码重置成功！")
        print("="*60)
        print(f"邮箱: {email}")
        print(f"姓名: {user[1] if user[1] else '未设置'}")
        print(f"新密码: {new_password}")
        print("="*60)
        print("\n⚠️  请立即登录并修改密码以确保安全！\n")
        
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"❌ 重置密码失败: {e}")
        sys.exit(1)

def interactive_reset():
    """交互式重置密码"""
    print("\n🔐 用户密码重置工具\n")
    
    # 显示所有用户
    users = list_users()
    
    if not users:
        print("❌ 系统中没有用户")
        return
    
    # 输入要重置的用户邮箱
    email = input("请输入要重置密码的用户邮箱: ").strip()
    
    if not email:
        print("❌ 邮箱不能为空")
        return
    
    # 询问是否使用自定义密码
    use_custom = input("\n是否使用自定义密码？(y/n，默认为n): ").strip().lower()
    
    new_password = None
    if use_custom == 'y':
        new_password = input("请输入新密码: ").strip()
        if not new_password:
            print("❌ 密码不能为空")
            return
        confirm_password = input("请再次输入新密码确认: ").strip()
        if new_password != confirm_password:
            print("❌ 两次输入的密码不一致")
            return
    
    # 确认重置
    print(f"\n⚠️  即将重置用户 {email} 的密码")
    confirm = input("确认继续？(yes/no): ").strip().lower()
    
    if confirm != 'yes':
        print("已取消")
        return
    
    # 执行重置
    reset_password(email, new_password)

def main():
    parser = argparse.ArgumentParser(
        description='RAGEval 用户密码重置工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 交互式重置（推荐）
  python3 reset_user_password.py
  
  # 列出所有用户
  python3 reset_user_password.py --list
  
  # 重置指定用户密码为默认密码(user123)
  python3 reset_user_password.py --email user@example.com
  
  # 重置指定用户密码为自定义密码
  python3 reset_user_password.py --email user@example.com --password newpass123
        """
    )
    
    parser.add_argument('--list', '-l', action='store_true', 
                        help='列出所有用户')
    parser.add_argument('--email', '-e', type=str, 
                        help='要重置密码的用户邮箱')
    parser.add_argument('--password', '-p', type=str, 
                        help='新密码（不指定则使用默认密码 user123）')
    
    args = parser.parse_args()
    
    # 列出用户
    if args.list:
        list_users()
        return
    
    # 命令行指定邮箱
    if args.email:
        reset_password(args.email, args.password)
        return
    
    # 交互式模式
    interactive_reset()

if __name__ == "__main__":
    main()



