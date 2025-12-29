# -*- coding: utf-8 -*-
"""
Neo4j 连接测试脚本
用于诊断连接问题
"""

import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

uri = os.getenv("NEO4J_URI")
username = os.getenv("NEO4J_USERNAME")
password = os.getenv("NEO4J_PASSWORD")

print("=" * 60)
print("Neo4j 连接测试")
print("=" * 60)
print(f"URI: {uri}")
print(f"Username: {username}")
print(f"Password: {'*' * len(password) if password else 'None'}")
print()

# 尝试不同的 URI 格式
uri_variants = [
    uri,  # 原始 URI
    uri.replace("neo4j+s://", "neo4j+ssc://") if "neo4j+s://" in uri else None,  # SSC 变体
    uri.replace("neo4j+s://", "bolt+ssc://") if "neo4j+s://" in uri else None,   # Bolt SSC
]

# 去除 None 值
uri_variants = [u for u in uri_variants if u]

for i, test_uri in enumerate(uri_variants, 1):
    print(f"尝试 {i}: {test_uri}")
    try:
        driver = GraphDatabase.driver(
            test_uri,
            auth=(username, password),
            max_connection_lifetime=3600,
            max_connection_pool_size=50,
            connection_acquisition_timeout=60
        )
        
        # 测试连接
        with driver.session() as session:
            result = session.run("RETURN 1 AS test, 'Connection OK' AS message")
            record = result.single()
            print(f"  ✅ 连接成功! 测试结果: {record['message']}")
            
            # 测试数据库信息
            db_info = session.run("CALL dbms.components() YIELD name, versions, edition")
            for record in db_info:
                print(f"  数据库: {record['name']} {record['versions'][0]} ({record['edition']})")
        
        driver.close()
        print(f"\n✅ 最佳 URI 格式: {test_uri}")
        print("\n请更新 .env 文件中的 NEO4J_URI 为上述格式")
        break
        
    except Exception as e:
        print(f"  ❌ 失败: {e}")
        print()

else:
    print("\n❌ 所有连接尝试都失败了")
    print("\n可能的原因:")
    print("1. Neo4j Aura 数据库未启动或已暂停")
    print("2. 网络连接问题（防火墙/代理）")
    print("3. 用户名或密码错误")
    print("4. 数据库地址错误")
    print("\n请检查:")
    print("- 登录 https://console.neo4j.io/ 确认数据库状态")
    print("- 确认数据库处于 'Running' 状态")
    print("- 重新生成密码（如果忘记）")
