# -*- coding: utf-8 -*-
"""
Neo4j 数据库导入脚本
将解析后的单词数据导入到 Neo4j 图数据库
"""

import os
from neo4j import GraphDatabase
from dotenv import load_dotenv
from word_parser import WordParser, Word
from typing import List


class Neo4jWordImporter:
    """Neo4j 单词数据导入器"""
    
    def __init__(self):
        # 加载环境变量
        load_dotenv()
        
        self.uri = os.getenv("NEO4J_URI")
        self.username = os.getenv("NEO4J_USERNAME")
        self.password = os.getenv("NEO4J_PASSWORD")
        
        if not all([self.uri, self.username, self.password]):
            raise ValueError("请在 .env 文件中配置 Neo4j 连接信息")
        
        self.driver = None
        
    def connect(self):
        """连接到 Neo4j 数据库"""
        try:
            # 为 Neo4j Aura 云服务添加必要的配置
            self.driver = GraphDatabase.driver(
                self.uri, 
                auth=(self.username, self.password),
                max_connection_lifetime=3600,
                max_connection_pool_size=50,
                connection_acquisition_timeout=60
            )
            # 验证连接 - 使用简单查询而不是 verify_connectivity
            with self.driver.session() as session:
                result = session.run("RETURN 1 AS test")
                result.single()
            print("✅ Neo4j 连接成功!")
            return True
        except Exception as e:
            print(f"❌ Neo4j 连接失败: {e}")
            print(f"URI: {self.uri}")
            print(f"Username: {self.username}")
            print("提示: 请确保 Neo4j Aura 数据库正在运行，且网络连接正常")
            return False
    
    def close(self):
        """关闭连接"""
        if self.driver:
            self.driver.close()
            print("Neo4j 连接已关闭")
    
    def clear_database(self):
        """清空数据库（谨慎使用）"""
        with self.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
            print("⚠️ 数据库已清空")
    
    def create_constraints(self):
        """创建约束和索引"""
        constraints = [
            "CREATE CONSTRAINT word_unique IF NOT EXISTS FOR (w:Word) REQUIRE w.word IS UNIQUE",
            "CREATE CONSTRAINT grade_unique IF NOT EXISTS FOR (g:Grade) REQUIRE g.name IS UNIQUE",
            "CREATE CONSTRAINT root_unique IF NOT EXISTS FOR (r:Root) REQUIRE r.name IS UNIQUE",
            "CREATE CONSTRAINT user_unique IF NOT EXISTS FOR (u:User) REQUIRE u.id IS UNIQUE",
        ]
        
        with self.driver.session() as session:
            for constraint in constraints:
                try:
                    session.run(constraint)
                except Exception as e:
                    print(f"约束创建跳过（可能已存在）: {e}")
            
            print("✅ 约束和索引创建完成")
    
    def import_grades(self):
        """导入年级节点"""
        grades = [
            {"name": "7年级上册", "level": 1, "floor_start": 1, "floor_end": 2},
            {"name": "7年级下册", "level": 2, "floor_start": 2, "floor_end": 3},
            {"name": "8年级上册", "level": 3, "floor_start": 4, "floor_end": 5},
            {"name": "8年级下册", "level": 4, "floor_start": 5, "floor_end": 6},
            {"name": "9年级", "level": 5, "floor_start": 7, "floor_end": 9},
        ]
        
        query = """
        UNWIND $grades AS grade
        MERGE (g:Grade {name: grade.name})
        SET g.level = grade.level,
            g.floor_start = grade.floor_start,
            g.floor_end = grade.floor_end
        """
        
        with self.driver.session() as session:
            session.run(query, grades=grades)
            print(f"✅ 导入 {len(grades)} 个年级节点")
    
    def import_roots(self, roots: List[str]):
        """导入词根节点"""
        root_data = [{"name": r} for r in roots if r]
        
        if not root_data:
            return
        
        query = """
        UNWIND $roots AS root
        MERGE (r:Root {name: root.name})
        """
        
        with self.driver.session() as session:
            session.run(query, roots=root_data)
            print(f"✅ 导入 {len(root_data)} 个词根节点")
    
    def import_words(self, words: List[Word], batch_size: int = 100):
        """批量导入单词节点"""
        word_data = [w.to_dict() for w in words]
        
        # 创建单词节点
        create_word_query = """
        UNWIND $words AS w
        MERGE (word:Word {word: w.word})
        SET word.phonetic = w.phonetic,
            word.pos = w.pos,
            word.definition = w.definition,
            word.page = w.page,
            word.difficulty = w.difficulty,
            word.is_phrase = w.is_phrase,
            word.mastered_count = 0,
            word.wrong_count = 0
        """
        
        # 建立单词与年级的关系
        grade_relation_query = """
        UNWIND $words AS w
        MATCH (word:Word {word: w.word})
        MATCH (grade:Grade {name: w.grade})
        MERGE (word)-[:BELONGS_TO]->(grade)
        """
        
        # 建立单词与词根的关系
        root_relation_query = """
        UNWIND $words AS w
        MATCH (word:Word {word: w.word})
        WHERE w.root IS NOT NULL AND w.root <> ''
        MATCH (root:Root {name: w.root})
        MERGE (word)-[:HAS_ROOT]->(root)
        """
        
        with self.driver.session() as session:
            # 分批导入
            for i in range(0, len(word_data), batch_size):
                batch = word_data[i:i + batch_size]
                session.run(create_word_query, words=batch)
                print(f"  导入单词: {i + len(batch)}/{len(word_data)}")
            
            # 建立年级关系
            for i in range(0, len(word_data), batch_size):
                batch = word_data[i:i + batch_size]
                session.run(grade_relation_query, words=batch)
            
            # 建立词根关系
            words_with_root = [w for w in word_data if w.get('root')]
            if words_with_root:
                session.run(root_relation_query, words=words_with_root)
        
        print(f"✅ 导入 {len(words)} 个单词节点及关系")
    
    def create_same_root_relations(self):
        """创建同词根单词之间的关系"""
        query = """
        MATCH (w1:Word)-[:HAS_ROOT]->(r:Root)<-[:HAS_ROOT]-(w2:Word)
        WHERE id(w1) < id(w2)
        MERGE (w1)-[:SAME_ROOT {root: r.name}]->(w2)
        """
        
        with self.driver.session() as session:
            result = session.run(query)
            print("✅ 创建同词根关系完成")
    
    def create_difficulty_floor_mapping(self):
        """创建难度与楼层的映射"""
        query = """
        // 创建楼层节点
        UNWIND range(1, 9) AS floor_num
        MERGE (f:Floor {number: floor_num})
        SET f.difficulty = CASE 
            WHEN floor_num <= 3 THEN 1
            WHEN floor_num <= 5 THEN 2
            WHEN floor_num <= 7 THEN 3
            ELSE 4
        END
        """
        
        with self.driver.session() as session:
            session.run(query)
            print("✅ 创建楼层节点完成")
    
    def get_statistics(self) -> dict:
        """获取数据库统计信息"""
        queries = {
            "words": "MATCH (w:Word) RETURN count(w) AS count",
            "grades": "MATCH (g:Grade) RETURN count(g) AS count",
            "roots": "MATCH (r:Root) RETURN count(r) AS count",
            "belongs_to": "MATCH ()-[r:BELONGS_TO]->() RETURN count(r) AS count",
            "has_root": "MATCH ()-[r:HAS_ROOT]->() RETURN count(r) AS count",
            "same_root": "MATCH ()-[r:SAME_ROOT]->() RETURN count(r) AS count",
        }
        
        stats = {}
        with self.driver.session() as session:
            for key, query in queries.items():
                result = session.run(query).single()
                stats[key] = result["count"] if result else 0
        
        return stats


def main():
    """主函数：执行完整的数据导入流程"""
    print("=" * 60)
    print("单词魔塔探险 - Neo4j 数据导入")
    print("=" * 60)
    
    # 1. 解析单词文件
    current_dir = os.path.dirname(os.path.abspath(__file__))
    word_file = os.path.join(current_dir, "所有单词.txt")
    
    if not os.path.exists(word_file):
        print(f"❌ 找不到单词文件: {word_file}")
        return
    
    print("\n📖 正在解析单词文件...")
    parser = WordParser(word_file)
    words = parser.parse()
    
    stats = parser.get_statistics()
    print(f"  解析完成: {stats['total']} 个词条")
    print(f"  单词: {stats['single_words']}, 短语: {stats['phrases']}")
    print(f"  识别词根: {stats['roots_identified']} 种")
    
    # 2. 连接 Neo4j
    print("\n🔌 正在连接 Neo4j...")
    importer = Neo4jWordImporter()
    
    if not importer.connect():
        return
    
    try:
        # 3. 清空并重建数据库
        print("\n🗑️ 清空现有数据...")
        importer.clear_database()
        
        # 4. 创建约束
        print("\n📐 创建约束和索引...")
        importer.create_constraints()
        
        # 5. 导入年级
        print("\n📚 导入年级数据...")
        importer.import_grades()
        
        # 6. 导入词根
        print("\n🌱 导入词根数据...")
        roots = parser.get_all_roots()
        importer.import_roots(roots)
        
        # 7. 导入单词
        print("\n📝 导入单词数据...")
        importer.import_words(words)
        
        # 8. 创建同词根关系
        print("\n🔗 创建同词根关系...")
        importer.create_same_root_relations()
        
        # 9. 创建楼层
        print("\n🏗️ 创建楼层节点...")
        importer.create_difficulty_floor_mapping()
        
        # 10. 显示统计
        print("\n" + "=" * 60)
        print("📊 数据库统计")
        print("=" * 60)
        db_stats = importer.get_statistics()
        print(f"  单词节点: {db_stats['words']}")
        print(f"  年级节点: {db_stats['grades']}")
        print(f"  词根节点: {db_stats['roots']}")
        print(f"  年级关系: {db_stats['belongs_to']}")
        print(f"  词根关系: {db_stats['has_root']}")
        print(f"  同词根关系: {db_stats['same_root']}")
        
        print("\n✅ 数据导入完成!")
        
    except Exception as e:
        print(f"\n❌ 导入过程出错: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        importer.close()


if __name__ == "__main__":
    main()
