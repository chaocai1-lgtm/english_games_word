# -*- coding: utf-8 -*-
"""
单词魔塔探险 - Streamlit 主应用
一个基于 Neo4j 图数据库的英语单词学习游戏
"""

import streamlit as st
import os
import random
from neo4j import GraphDatabase
from dotenv import load_dotenv
from datetime import datetime, timedelta
import json

# 加载环境变量
load_dotenv()

# 页面配置
st.set_page_config(
    page_title="单词魔塔探险",
    page_icon="🏰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 管理员密码配置
ADMIN_PASSWORDS = {
    "parent": "admin666",   # 家长端密码
    "teacher": "admin888"   # 教师端密码
}

# 自定义CSS样式
st.markdown("""
<style>
    .main-title {
        text-align: center;
        color: #1e3a5f;
        font-size: 3rem;
        margin-bottom: 1rem;
    }
    .floor-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 15px;
        padding: 20px;
        color: white;
        text-align: center;
        margin: 10px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
    }
    .word-card {
        background: white;
        border-radius: 10px;
        padding: 20px;
        margin: 10px 0;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        border-left: 5px solid #667eea;
    }
    .correct {
        background-color: #d4edda;
        border-color: #28a745;
    }
    .wrong {
        background-color: #f8d7da;
        border-color: #dc3545;
    }
    .stats-card {
        background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
        border-radius: 10px;
        padding: 15px;
        color: white;
        text-align: center;
    }
    .admin-card {
        background: linear-gradient(135deg, #ff6b6b 0%, #ffa500 100%);
        border-radius: 10px;
        padding: 15px;
        color: white;
        text-align: center;
    }
    .teacher-card {
        background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
        border-radius: 10px;
        padding: 15px;
        color: white;
        text-align: center;
    }
    .progress-text {
        font-size: 1.2rem;
        font-weight: bold;
    }
    .student-row {
        background: #f8f9fa;
        border-radius: 8px;
        padding: 10px;
        margin: 5px 0;
        border-left: 4px solid #667eea;
    }
</style>
""", unsafe_allow_html=True)


class Neo4jConnection:
    """Neo4j 数据库连接管理"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.driver = None
        return cls._instance
    
    def connect(self):
        if self.driver is None:
            uri = os.getenv("NEO4J_URI")
            username = os.getenv("NEO4J_USERNAME")
            password = os.getenv("NEO4J_PASSWORD")
            
            if all([uri, username, password]):
                try:
                    # 为 Neo4j Aura 添加连接配置
                    self.driver = GraphDatabase.driver(
                        uri, 
                        auth=(username, password),
                        max_connection_lifetime=3600,
                        max_connection_pool_size=50,
                        connection_acquisition_timeout=60
                    )
                    # 简单验证
                    with self.driver.session() as session:
                        session.run("RETURN 1").single()
                    return True
                except Exception as e:
                    st.error(f"数据库连接失败: {e}")
                    return False
        return self.driver is not None
    
    def get_session(self):
        if self.connect():
            return self.driver.session()
        return None
    
    def close(self):
        if self.driver:
            self.driver.close()
            self.driver = None


class WordGame:
    """单词游戏核心逻辑"""
    
    def __init__(self, db: Neo4jConnection):
        self.db = db
    
    def get_words_for_floor(self, floor: int, limit: int = 10) -> list:
        """获取指定楼层的单词"""
        # 根据楼层确定难度和年级
        floor_grade_map = {
            1: ["7年级上册"],
            2: ["7年级上册", "7年级下册"],
            3: ["7年级下册"],
            4: ["8年级上册"],
            5: ["8年级上册", "8年级下册"],
            6: ["8年级下册"],
            7: ["9年级"],
            8: ["9年级"],
            9: ["9年级"],
        }
        
        grades = floor_grade_map.get(floor, ["7年级上册"])
        
        query = """
        MATCH (w:Word)-[:BELONGS_TO]->(g:Grade)
        WHERE g.name IN $grades AND w.is_phrase = false
        RETURN w.word AS word, w.phonetic AS phonetic, 
               w.definition AS definition, w.pos AS pos,
               g.name AS grade
        ORDER BY rand()
        LIMIT $limit
        """
        
        session = self.db.get_session()
        if session:
            with session:
                result = session.run(query, grades=grades, limit=limit)
                return [dict(record) for record in result]
        return []
    
    def get_random_definitions(self, correct_def: str, count: int = 3) -> list:
        """获取随机的错误选项"""
        query = """
        MATCH (w:Word)
        WHERE w.definition <> $correct_def AND w.definition IS NOT NULL
        RETURN DISTINCT w.definition AS definition
        ORDER BY rand()
        LIMIT $count
        """
        
        session = self.db.get_session()
        if session:
            with session:
                result = session.run(query, correct_def=correct_def, count=count)
                return [record["definition"] for record in result]
        return []
    
    def get_words_by_root(self, root: str) -> list:
        """获取同词根的单词"""
        query = """
        MATCH (w:Word)-[:HAS_ROOT]->(r:Root {name: $root})
        RETURN w.word AS word, w.definition AS definition, w.phonetic AS phonetic
        """
        
        session = self.db.get_session()
        if session:
            with session:
                result = session.run(query, root=root)
                return [dict(record) for record in result]
        return []
    
    def get_all_roots(self) -> list:
        """获取所有词根"""
        query = """
        MATCH (r:Root)<-[:HAS_ROOT]-(w:Word)
        WITH r, count(w) AS word_count
        WHERE word_count >= 2
        RETURN r.name AS root, word_count
        ORDER BY word_count DESC
        """
        
        session = self.db.get_session()
        if session:
            with session:
                result = session.run(query)
                return [dict(record) for record in result]
        return []
    
    def get_database_stats(self) -> dict:
        """获取数据库统计"""
        query = """
        MATCH (w:Word) 
        WITH count(w) AS total_words
        MATCH (g:Grade)<-[:BELONGS_TO]-(w2:Word)
        WITH total_words, g.name AS grade, count(w2) AS count
        RETURN total_words, collect({grade: grade, count: count}) AS by_grade
        """
        
        session = self.db.get_session()
        if session:
            with session:
                result = session.run(query).single()
                if result:
                    return {
                        "total_words": result["total_words"],
                        "by_grade": result["by_grade"]
                    }
        return {"total_words": 0, "by_grade": []}
    
    def save_user_record(self, user_id: str, record: dict):
        """保存用户学习记录到数据库"""
        query = """
        MERGE (u:User {id: $user_id})
        SET u.last_active = datetime(),
            u.total_questions = $total_questions,
            u.correct_answers = $correct_answers,
            u.score = $score,
            u.current_floor = $current_floor,
            u.mastered_count = $mastered_count,
            u.wrong_count = $wrong_count
        """
        
        session = self.db.get_session()
        if session:
            with session:
                session.run(query, 
                           user_id=user_id,
                           total_questions=record.get("total_questions", 0),
                           correct_answers=record.get("correct_answers", 0),
                           score=record.get("score", 0),
                           current_floor=record.get("current_floor", 1),
                           mastered_count=record.get("mastered_count", 0),
                           wrong_count=record.get("wrong_count", 0))
    
    def get_all_users(self) -> list:
        """获取所有用户（教师端用）"""
        query = """
        MATCH (u:User)
        RETURN u.id AS user_id, 
               u.total_questions AS total_questions,
               u.correct_answers AS correct_answers,
               u.score AS score,
               u.current_floor AS current_floor,
               u.mastered_count AS mastered_count,
               u.wrong_count AS wrong_count,
               u.last_active AS last_active
        ORDER BY u.score DESC
        """
        
        session = self.db.get_session()
        if session:
            with session:
                result = session.run(query)
                return [dict(record) for record in result]
        return []
    
    def get_user_by_id(self, user_id: str) -> dict:
        """根据ID获取用户（家长端用）"""
        query = """
        MATCH (u:User {id: $user_id})
        RETURN u.id AS user_id, 
               u.total_questions AS total_questions,
               u.correct_answers AS correct_answers,
               u.score AS score,
               u.current_floor AS current_floor,
               u.mastered_count AS mastered_count,
               u.wrong_count AS wrong_count,
               u.last_active AS last_active
        """
        
        session = self.db.get_session()
        if session:
            with session:
                result = session.run(query, user_id=user_id).single()
                if result:
                    return dict(result)
        return None
    
    def delete_user(self, user_id: str) -> bool:
        """删除指定用户的所有数据"""
        query = """
        MATCH (u:User {id: $user_id})
        DELETE u
        """
        
        session = self.db.get_session()
        if session:
            try:
                with session:
                    session.run(query, user_id=user_id)
                return True
            except:
                return False
        return False
    
    def delete_all_users(self) -> bool:
        """删除所有用户数据"""
        query = """
        MATCH (u:User)
        DELETE u
        """
        
        session = self.db.get_session()
        if session:
            try:
                with session:
                    session.run(query)
                return True
            except:
                return False
        return False
    
    def reset_user_data(self, user_id: str) -> bool:
        """重置指定用户的学习数据（保留用户但清零）"""
        query = """
        MATCH (u:User {id: $user_id})
        SET u.total_questions = 0,
            u.correct_answers = 0,
            u.score = 0,
            u.current_floor = 1,
            u.mastered_count = 0,
            u.wrong_count = 0,
            u.last_active = datetime()
        """
        
        session = self.db.get_session()
        if session:
            try:
                with session:
                    session.run(query, user_id=user_id)
                return True
            except:
                return False
        return False
    
    def set_parent_password(self, user_id: str, password: str) -> bool:
        """设置学生对应的家长密码"""
        query = """
        MERGE (u:User {id: $user_id})
        SET u.parent_password = $password
        """
        
        session = self.db.get_session()
        if session:
            try:
                with session:
                    session.run(query, user_id=user_id, password=password)
                return True
            except:
                return False
        return False
    
    def get_parent_password(self, user_id: str) -> str:
        """获取学生对应的家长密码"""
        query = """
        MATCH (u:User {id: $user_id})
        RETURN u.parent_password AS password
        """
        
        session = self.db.get_session()
        if session:
            with session:
                result = session.run(query, user_id=user_id).single()
                if result and result["password"]:
                    return result["password"]
        return None


def init_session_state():
    """初始化会话状态"""
    defaults = {
        "current_floor": 1,
        "score": 0,
        "total_questions": 0,
        "correct_answers": 0,
        "current_question": None,
        "show_result": False,
        "last_answer_correct": None,
        "game_mode": "menu",  # menu, tower, tower_select, root_explore, review, parent_login, parent_dashboard, teacher_login, teacher_dashboard, speed_challenge, spelling, lucky_wheel, prize_settings
        "mastered_words": set(),
        "wrong_words": [],
        "floor_words": [],
        "question_index": 0,
        "user_id": None,
        "user_id_confirmed": False,  # 用户ID是否已确认
        "temp_user_id": "",  # 临时存储输入的用户ID
        "admin_logged_in": None,  # None, "parent", "teacher"
        "selected_student_id": None,
        # 新玩法相关状态
        "speed_timer_start": None,
        "speed_score": 0,
        "speed_combo": 0,
        "speed_max_combo": 0,
        "speed_words": [],
        "speed_index": 0,
        "speed_finished": False,
        "spelling_word": None,
        "spelling_hint_used": False,
        "spelling_attempts": 0,
        "custom_prizes": None,  # 自定义奖励列表
        "lucky_spins_today": 0,
        "last_spin_date": None,
        "lottery_result": None,  # 抽奖结果
        "achievements": set(),
        "daily_streak": 0,
        "last_play_date": None,
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
    
    # 检查并更新每日连续登录
    check_daily_streak()


def check_daily_streak():
    """检查每日连续登录"""
    from datetime import date
    today = date.today().isoformat()
    
    if st.session_state.last_play_date != today:
        if st.session_state.last_play_date:
            last_date = datetime.fromisoformat(st.session_state.last_play_date).date()
            diff = (date.today() - last_date).days
            if diff == 1:
                st.session_state.daily_streak += 1
            elif diff > 1:
                st.session_state.daily_streak = 1
        else:
            st.session_state.daily_streak = 1
        st.session_state.last_play_date = today
        st.session_state.lucky_spins_today = 0  # 重置每日抽奖次数


def check_achievements():
    """检查并解锁成就"""
    achievements_config = {
        "first_blood": ("🩸 首杀", "答对第一道题", lambda: st.session_state.correct_answers >= 1),
        "ten_correct": ("🎯 十发十中", "累计答对10题", lambda: st.session_state.correct_answers >= 10),
        "fifty_correct": ("💯 半百达成", "累计答对50题", lambda: st.session_state.correct_answers >= 50),
        "hundred_correct": ("🏆 百题大师", "累计答对100题", lambda: st.session_state.correct_answers >= 100),
        "floor_3": ("🏰 初级探险家", "通关第3层", lambda: st.session_state.current_floor >= 3),
        "floor_6": ("🗼 中级探险家", "通关第6层", lambda: st.session_state.current_floor >= 6),
        "floor_9": ("👑 魔塔征服者", "通关第9层", lambda: st.session_state.current_floor >= 9),
        "score_100": ("⭐ 百分新星", "积分达到100", lambda: st.session_state.score >= 100),
        "score_500": ("🌟 五百强者", "积分达到500", lambda: st.session_state.score >= 500),
        "score_1000": ("💫 千分大神", "积分达到1000", lambda: st.session_state.score >= 1000),
        "streak_3": ("🔥 三连胜", "连续答对3题", lambda: st.session_state.get("speed_max_combo", 0) >= 3),
        "streak_10": ("🔥🔥 十连胜", "连续答对10题", lambda: st.session_state.get("speed_max_combo", 0) >= 10),
        "daily_3": ("📅 三天打卡", "连续登录3天", lambda: st.session_state.daily_streak >= 3),
        "daily_7": ("📆 一周坚持", "连续登录7天", lambda: st.session_state.daily_streak >= 7),
        "spelling_master": ("✍️ 拼写达人", "拼写模式答对20题", lambda: st.session_state.get("spelling_correct", 0) >= 20),
        "speed_demon": ("⚡ 闪电侠", "限时挑战单局答对15题", lambda: st.session_state.get("speed_best", 0) >= 15),
    }
    
    newly_unlocked = []
    for key, (name, desc, check) in achievements_config.items():
        if key not in st.session_state.achievements:
            try:
                if check():
                    st.session_state.achievements.add(key)
                    newly_unlocked.append((name, desc))
            except:
                pass
    
    return newly_unlocked, achievements_config


def reset_game_progress():
    """重置游戏进度"""
    st.session_state.current_floor = 1
    st.session_state.score = 0
    st.session_state.total_questions = 0
    st.session_state.correct_answers = 0
    st.session_state.current_question = None
    st.session_state.show_result = False
    st.session_state.last_answer_correct = None
    st.session_state.mastered_words = set()
    st.session_state.wrong_words = []
    st.session_state.floor_words = []
    st.session_state.question_index = 0
    st.session_state.game_mode = "menu"


def render_sidebar(game: WordGame = None):
    """渲染侧边栏"""
    with st.sidebar:
        st.markdown("## 🏰 单词魔塔探险")
        st.markdown("---")
        
        # 如果是管理员模式，显示不同的侧边栏
        if st.session_state.admin_logged_in:
            if st.session_state.admin_logged_in == "parent":
                st.markdown("### 👨‍👩‍👧 家长端")
            else:
                st.markdown("### 👨‍🏫 教师端")
            
            if st.button("🚪 退出管理端", use_container_width=True):
                st.session_state.admin_logged_in = None
                st.session_state.game_mode = "menu"
                st.rerun()
            return
        
        # 用户ID输入
        st.markdown("### 👤 我的账号")
        
        # 如果用户ID已确认，显示当前用户
        if st.session_state.user_id_confirmed and st.session_state.user_id:
            st.success(f"✅ 当前用户: **{st.session_state.user_id}**")
            
            if st.button("🔄 切换账号", use_container_width=True):
                st.session_state.user_id_confirmed = False
                st.session_state.temp_user_id = ""
                st.rerun()
        else:
            # 未确认用户ID，显示输入框
            with st.form("user_id_form", clear_on_submit=False):
                temp_id = st.text_input(
                    "请输入你的姓名/学号",
                    value=st.session_state.temp_user_id,
                    key="temp_user_input",
                    help="输入后点击确认按钮"
                )
                
                col1, col2 = st.columns(2)
                with col1:
                    confirm = st.form_submit_button("✅ 确认", use_container_width=True)
                with col2:
                    cancel = st.form_submit_button("❌ 清空", use_container_width=True)
                
                if confirm and temp_id:
                    # 检查是否是新用户
                    if st.session_state.user_id and st.session_state.user_id != temp_id:
                        # 切换用户，重置游戏进度
                        reset_game_progress()
                        st.session_state.user_id = temp_id
                        st.session_state.user_id_confirmed = True
                        st.success(f"已切换到新用户: {temp_id}，游戏进度已重置")
                        st.rerun()
                    else:
                        # 确认当前用户
                        st.session_state.user_id = temp_id
                        st.session_state.user_id_confirmed = True
                        st.session_state.temp_user_id = temp_id
                        st.rerun()
                
                if cancel:
                    st.session_state.temp_user_id = ""
                    st.rerun()
                
                if not temp_id and confirm:
                    st.warning("请输入姓名/学号")
        
        st.markdown("---")
        
        # 玩家统计
        st.markdown("### 📊 我的进度")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("当前楼层", f"{st.session_state.current_floor}F")
        with col2:
            st.metric("总积分", st.session_state.score)
        
        accuracy = 0
        if st.session_state.total_questions > 0:
            accuracy = (st.session_state.correct_answers / st.session_state.total_questions) * 100
        st.progress(accuracy / 100)
        st.caption(f"正确率: {accuracy:.1f}%")
        
        st.markdown("---")
        
        # 游戏模式选择
        st.markdown("### 🎮 游戏模式")
        
        if st.button("🏰 魔塔闯关", use_container_width=True, key="sb_tower"):
            st.session_state.game_mode = "tower_select"
            st.rerun()
        
        if st.button("🌱 词根探索", use_container_width=True, key="sb_root"):
            st.session_state.game_mode = "root_explore"
            st.rerun()
        
        if st.button("📖 复习错题", use_container_width=True, key="sb_review"):
            st.session_state.game_mode = "review"
            st.rerun()
        
        if st.button("⏱️ 限时挑战", use_container_width=True, key="sb_speed"):
            st.session_state.game_mode = "speed_challenge"
            st.rerun()
        
        if st.button("✍️ 拼写大师", use_container_width=True, key="sb_spelling"):
            st.session_state.game_mode = "spelling"
            st.rerun()
        
        if st.button("🎁 幸运抽奖", use_container_width=True, key="sb_lucky"):
            st.session_state.game_mode = "lucky_wheel"
            st.rerun()
        
        if st.button("🏅 成就殿堂", use_container_width=True, key="sb_achieve"):
            st.session_state.game_mode = "achievements"
            st.rerun()
        
        if st.button("🏠 返回主页", use_container_width=True, key="sb_home"):
            st.session_state.game_mode = "menu"
            st.rerun()
        
        st.markdown("---")
        st.markdown("### 📚 错题本")
        st.caption(f"待复习: {len(st.session_state.wrong_words)} 个")
        
        # 侧边栏排行榜
        st.markdown("---")
        st.markdown("### 🏆 排行榜 TOP 3")
        
        if game:
            top_students = get_top_students(game, 3)
            if top_students:
                medals = ["🥇", "🥈", "🥉"]
                for i, student in enumerate(top_students):
                    name = student.get("user_id", "未知")
                    score = student.get("score", 0) or 0
                    floor = student.get("current_floor", 1) or 1
                    st.markdown(f"""
                    <div style='background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); 
                                border-radius: 8px; padding: 8px; margin: 4px 0;
                                border-left: 4px solid {"#ffd700" if i==0 else "#c0c0c0" if i==1 else "#cd7f32"};'>
                        <span style='font-size: 1.2rem;'>{medals[i]}</span>
                        <strong style='font-size: 0.9rem;'>{name}</strong>
                        <span style='float: right; font-size: 0.85rem;'>🏆{score} 🏰{floor}F</span>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.caption("暂无排行数据")
        else:
            st.caption("加载中...")
        
        st.markdown("---")
        
        # 管理入口
        st.markdown("### 🔐 管理入口")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("👨‍👩‍👧 家长", use_container_width=True, key="sb_parent"):
                st.session_state.game_mode = "parent_login"
                st.rerun()
        with col2:
            if st.button("👨‍🏫 教师", use_container_width=True, key="sb_teacher"):
                st.session_state.game_mode = "teacher_login"
                st.rerun()


def render_main_menu(game: WordGame):
    """渲染主菜单"""
    st.markdown("<h1 class='main-title'>🏰 单词魔塔探险</h1>", unsafe_allow_html=True)
    
    # 获取数据库统计
    stats = game.get_database_stats()
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        <div class='stats-card'>
            <h2>📚</h2>
            <p class='progress-text'>总单词数</p>
            <h3>{}</h3>
        </div>
        """.format(stats.get("total_words", 0)), unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class='stats-card'>
            <h2>✅</h2>
            <p class='progress-text'>已掌握</p>
            <h3>{}</h3>
        </div>
        """.format(len(st.session_state.mastered_words)), unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div class='stats-card'>
            <h2>🏆</h2>
            <p class='progress-text'>当前楼层</p>
            <h3>{}F</h3>
        </div>
        """.format(st.session_state.current_floor), unsafe_allow_html=True)
    
    st.markdown("---")
    
    # 🏆 排行榜 TOP 3
    st.markdown("### 🏆 积分排行榜 TOP 3")
    top_students = get_top_students(game, 3)
    
    if top_students:
        cols = st.columns(3)
        medals = ["🥇", "🥈", "🥉"]
        colors = [
            "linear-gradient(135deg, #ffd700 0%, #ffb347 100%)",  # 金
            "linear-gradient(135deg, #c0c0c0 0%, #a8a8a8 100%)",  # 银
            "linear-gradient(135deg, #cd7f32 0%, #b87333 100%)",  # 铜
        ]
        
        for i, student in enumerate(top_students):
            with cols[i]:
                score = student.get("score", 0) or 0
                floor = student.get("current_floor", 1) or 1
                name = student.get("user_id", "???")
                
                st.markdown(f"""
                <div style='background: {colors[i]}; 
                            border-radius: 15px; padding: 20px; text-align: center;
                            box-shadow: 0 4px 15px rgba(0,0,0,0.2);'>
                    <h1 style='margin:0; font-size: 2.5rem;'>{medals[i]}</h1>
                    <h3 style='margin: 10px 0; color: #333;'>{name}</h3>
                    <p style='margin: 5px 0; font-size: 1.2rem;'>🏆 {score} 分</p>
                    <p style='margin: 0; font-size: 0.9rem;'>🏰 {floor}F</p>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.info("暂无排行榜数据，快来成为第一名吧！")
    
    st.markdown("---")
    
    # 快速开始
    st.markdown("### 🚀 快速开始")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🏰 魔塔闯关", key="quick_tower", use_container_width=True):
            st.session_state.game_mode = "tower_select"
            st.rerun()
    with col2:
        if st.button("🌱 词根探索", key="quick_root", use_container_width=True):
            st.session_state.game_mode = "root_explore"
            st.rerun()
    with col3:
        if st.button("📖 错题复习", key="quick_review", use_container_width=True):
            st.session_state.game_mode = "review"
            st.rerun()
    
    # 新增玩法入口
    st.markdown("### 🎮 更多玩法")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("""
        <div style='background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); 
                    border-radius: 10px; padding: 15px; color: white; text-align: center;'>
            <h3>⏱️</h3>
            <p>限时挑战</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("开始挑战", key="quick_speed", use_container_width=True):
            st.session_state.game_mode = "speed_challenge"
            st.rerun()
    
    with col2:
        st.markdown("""
        <div style='background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); 
                    border-radius: 10px; padding: 15px; color: white; text-align: center;'>
            <h3>✍️</h3>
            <p>拼写大师</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("开始拼写", key="quick_spell", use_container_width=True):
            st.session_state.game_mode = "spelling"
            st.rerun()
    
    with col3:
        st.markdown("""
        <div style='background: linear-gradient(135deg, #ffecd2 0%, #fcb69f 100%); 
                    border-radius: 10px; padding: 15px; color: #333; text-align: center;'>
            <h3>🎁</h3>
            <p>幸运抽奖</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("去抽奖", key="quick_lucky", use_container_width=True):
            st.session_state.game_mode = "lucky_wheel"
            st.rerun()
    
    # 成就展示
    st.markdown("---")
    st.markdown("### 🏅 我的成就")
    
    _, achievements_config = check_achievements()
    unlocked = st.session_state.achievements
    
    if unlocked:
        cols = st.columns(min(len(unlocked), 6))
        for i, key in enumerate(list(unlocked)[:6]):
            if key in achievements_config:
                name, desc, _ = achievements_config[key]
                with cols[i % 6]:
                    st.markdown(f"""
                    <div style='background: linear-gradient(135deg, #ffd700 0%, #ffb347 100%); 
                                border-radius: 10px; padding: 10px; text-align: center;'>
                        <p style='margin:0; font-size: 1.5rem;'>{name.split()[0]}</p>
                        <p style='margin:0; font-size: 0.7rem;'>{name.split()[-1] if len(name.split()) > 1 else ''}</p>
                    </div>
                    """, unsafe_allow_html=True)
        
        if len(unlocked) > 6:
            st.caption(f"还有 {len(unlocked) - 6} 个成就...")
        
        if st.button("🏅 查看全部成就", key="view_achievements"):
            st.session_state.game_mode = "achievements"
            st.rerun()
    else:
        st.info("还没有解锁成就，开始游戏来获取你的第一个成就吧！")


def render_floor_select(game: WordGame):
    """渲染楼层选择页面"""
    st.markdown("## 🗼 选择楼层挑战")
    st.markdown("选择一个楼层开始你的单词挑战之旅！")
    
    st.markdown("---")
    
    # 楼层信息
    floor_info = [
        (1, "⭐", "7年级上册", "初级词汇，适合入门"),
        (2, "⭐", "7年级混合", "7年级上下册混合"),
        (3, "⭐", "7年级下册", "巩固7年级词汇"),
        (4, "⭐⭐", "8年级上册", "进阶词汇开始"),
        (5, "⭐⭐", "8年级混合", "8年级上下册混合"),
        (6, "⭐⭐", "8年级下册", "8年级词汇冲刺"),
        (7, "⭐⭐⭐", "9年级初", "高级词汇入门"),
        (8, "⭐⭐⭐", "9年级中", "高级词汇进阶"),
        (9, "⭐⭐⭐⭐", "9年级Boss", "终极挑战！"),
    ]
    
    # 3列布局显示楼层
    for row in range(3):
        cols = st.columns(3)
        for col_idx in range(3):
            floor_idx = row * 3 + col_idx
            if floor_idx < len(floor_info):
                floor, stars, name, desc = floor_info[floor_idx]
                with cols[col_idx]:
                    # 使用容器创建楼层卡片
                    with st.container():
                        st.markdown(f"""
                        <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                                    border-radius: 15px; padding: 20px; color: white; text-align: center;
                                    margin: 5px 0; min-height: 150px;'>
                            <h2>🏰 {floor}F</h2>
                            <p>{stars}</p>
                            <p><strong>{name}</strong></p>
                            <p style='font-size: 0.9rem;'>{desc}</p>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        if st.button(f"挑战 {floor}F", key=f"select_floor_{floor}", use_container_width=True):
                            st.session_state.current_floor = floor
                            st.session_state.game_mode = "tower"
                            st.session_state.floor_words = []
                            st.session_state.question_index = 0
                            st.rerun()
    
    st.markdown("---")
    
    # 返回按钮
    if st.button("🏠 返回主页", use_container_width=True, key="floor_back_home"):
        st.session_state.game_mode = "menu"
        st.rerun()


def render_tower_mode(game: WordGame):
    """渲染魔塔闯关模式"""
    floor = st.session_state.current_floor
    
    # 顶部导航
    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        if st.button("⬅️ 返回楼层选择", key="tower_back"):
            st.session_state.game_mode = "tower_select"
            st.session_state.floor_words = []
            st.session_state.question_index = 0
            st.session_state.current_question = None
            st.session_state.show_result = False
            st.rerun()
    with col2:
        st.markdown(f"## 🏰 第 {floor} 层挑战")
    with col3:
        st.markdown(f"**积分: {st.session_state.score}**")
    
    st.markdown("---")
    
    # 获取当前楼层的单词
    if not st.session_state.floor_words:
        st.session_state.floor_words = game.get_words_for_floor(floor, limit=10)
        st.session_state.question_index = 0
    
    words = st.session_state.floor_words
    
    if not words:
        st.warning("暂无单词数据，请先运行 neo4j_import.py 导入数据")
        return
    
    # 进度条
    progress = st.session_state.question_index / len(words)
    st.progress(progress)
    st.caption(f"进度: {st.session_state.question_index}/{len(words)}")
    
    # 检查是否完成本层
    if st.session_state.question_index >= len(words):
        st.success(f"🎉 恭喜通过第 {floor} 层！")
        st.balloons()
        
        # 保存用户记录
        if st.session_state.user_id:
            game.save_user_record(st.session_state.user_id, {
                "total_questions": st.session_state.total_questions,
                "correct_answers": st.session_state.correct_answers,
                "score": st.session_state.score,
                "current_floor": st.session_state.current_floor,
                "mastered_count": len(st.session_state.mastered_words),
                "wrong_count": len(st.session_state.wrong_words)
            })
        
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("📋 返回楼层选择", use_container_width=True, key="pass_back"):
                st.session_state.game_mode = "tower_select"
                st.session_state.floor_words = []
                st.session_state.question_index = 0
                st.rerun()
        with col2:
            if floor < 9 and st.button("⬆️ 挑战下一层", use_container_width=True, key="pass_next"):
                st.session_state.current_floor = floor + 1
                st.session_state.floor_words = []
                st.session_state.question_index = 0
                st.rerun()
        with col3:
            if st.button("🔄 重新挑战本层", use_container_width=True, key="pass_retry"):
                st.session_state.floor_words = []
                st.session_state.question_index = 0
                st.rerun()
        return
    
    # 当前单词
    current_word = words[st.session_state.question_index]
    
    # 显示单词卡片
    st.markdown(f"""
    <div class='word-card'>
        <h2>{current_word['word']}</h2>
        <p style='color: #666; font-style: italic;'>{current_word.get('phonetic', '')}</p>
        <p><strong>词性:</strong> {current_word.get('pos', '未知')}</p>
    </div>
    """, unsafe_allow_html=True)
    
    # 显示答题结果
    if st.session_state.show_result:
        if st.session_state.last_answer_correct:
            st.success(f"✅ 正确！答案是: {current_word['definition']}")
        else:
            st.error(f"❌ 错误！正确答案是: {current_word['definition']}")
        
        if st.button("➡️ 下一题", use_container_width=True, key="next_question"):
            st.session_state.question_index += 1
            st.session_state.show_result = False
            st.session_state.current_question = None
            st.rerun()
        return
    
    # 生成选项
    if st.session_state.current_question is None:
        correct_def = current_word['definition']
        wrong_defs = game.get_random_definitions(correct_def, 3)
        all_options = [correct_def] + wrong_defs
        random.shuffle(all_options)
        st.session_state.current_question = {
            "options": all_options,
            "correct": correct_def
        }
    
    question = st.session_state.current_question
    
    # 显示选项
    st.markdown("### 请选择正确的释义:")
    
    for i, option in enumerate(question["options"]):
        if st.button(f"{chr(65+i)}. {option}", key=f"option_{i}", use_container_width=True):
            is_correct = (option == question["correct"])
            
            st.session_state.total_questions += 1
            st.session_state.show_result = True
            st.session_state.last_answer_correct = is_correct
            
            if is_correct:
                st.session_state.correct_answers += 1
                st.session_state.score += 10
                st.session_state.mastered_words.add(current_word['word'])
            else:
                st.session_state.wrong_words.append(current_word)
            
            st.rerun()


def render_root_explore(game: WordGame):
    """渲染词根探索模式"""
    st.markdown("## 🌱 词根探索")
    st.markdown("探索词根，一次记住一组单词！")
    
    # 获取所有词根
    roots = game.get_all_roots()
    
    if not roots:
        st.warning("暂无词根数据，请先运行 neo4j_import.py 导入数据")
        return
    
    # 词根选择
    root_names = [f"{r['root']} ({r['word_count']}个单词)" for r in roots]
    selected = st.selectbox("选择一个词根:", root_names)
    
    if selected:
        root_name = selected.split(" (")[0]
        words = game.get_words_by_root(root_name)
        
        st.markdown(f"### 词根 「{root_name}」 家族")
        
        for word in words:
            st.markdown(f"""
            <div class='word-card'>
                <h4>{word['word']}</h4>
                <p style='color: #666;'>{word.get('phonetic', '')}</p>
                <p>{word['definition']}</p>
            </div>
            """, unsafe_allow_html=True)


def render_review_mode(game: WordGame):
    """渲染复习模式"""
    st.markdown("## 📖 错题复习")
    
    wrong_words = st.session_state.wrong_words
    
    if not wrong_words:
        st.success("🎉 太棒了！没有需要复习的单词！")
        return
    
    st.markdown(f"共有 **{len(wrong_words)}** 个单词需要复习")
    
    for i, word in enumerate(wrong_words):
        with st.expander(f"📝 {word['word']}", expanded=(i == 0)):
            st.markdown(f"**音标:** {word.get('phonetic', '无')}")
            st.markdown(f"**词性:** {word.get('pos', '未知')}")
            st.markdown(f"**释义:** {word['definition']}")
            
            if st.button(f"✅ 我记住了", key=f"review_{i}"):
                st.session_state.wrong_words.pop(i)
                st.session_state.mastered_words.add(word['word'])
                st.rerun()
    
    if st.button("🗑️ 清空错题本", use_container_width=True, key="clear_review"):
        st.session_state.wrong_words = []
        st.rerun()


def render_speed_challenge(game: WordGame):
    """渲染限时挑战模式 - 60秒内答对越多分越高"""
    import time
    
    st.markdown("## ⏱️ 限时挑战赛")
    st.markdown("60秒内答对尽可能多的题目！答对加10分，连击有加成！")
    
    # 初始化限时挑战
    if not st.session_state.speed_words or st.session_state.speed_finished:
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🚀 开始挑战", use_container_width=True, key="speed_start"):
                # 获取大量单词用于挑战
                st.session_state.speed_words = game.get_words_for_floor(
                    random.randint(1, 9), limit=50
                )
                st.session_state.speed_timer_start = time.time()
                st.session_state.speed_score = 0
                st.session_state.speed_combo = 0
                st.session_state.speed_max_combo = 0
                st.session_state.speed_index = 0
                st.session_state.speed_finished = False
                st.session_state.current_question = None
                st.rerun()
        with col2:
            if st.button("🏠 返回主页", use_container_width=True, key="speed_home"):
                st.session_state.game_mode = "menu"
                st.rerun()
        
        # 显示历史最佳
        best = st.session_state.get("speed_best", 0)
        if best > 0:
            st.info(f"🏆 你的历史最佳: 答对 {best} 题")
        return
    
    # 计算剩余时间
    elapsed = time.time() - st.session_state.speed_timer_start
    remaining = max(0, 60 - elapsed)
    
    # 时间到
    if remaining <= 0:
        st.session_state.speed_finished = True
        correct_count = st.session_state.speed_index
        
        # 更新最佳成绩
        if correct_count > st.session_state.get("speed_best", 0):
            st.session_state.speed_best = correct_count
        
        st.balloons()
        st.success(f"⏰ 时间到！")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("答对题数", correct_count)
        with col2:
            st.metric("获得积分", st.session_state.speed_score)
        with col3:
            st.metric("最大连击", st.session_state.speed_max_combo)
        
        # 加分到总积分
        st.session_state.score += st.session_state.speed_score
        
        # 检查成就
        newly_unlocked, _ = check_achievements()
        for name, desc in newly_unlocked:
            st.success(f"🎉 解锁成就: {name} - {desc}")
        
        if st.button("🔄 再来一次", use_container_width=True, key="speed_retry"):
            st.session_state.speed_words = []
            st.session_state.speed_finished = True
            st.rerun()
        return
    
    # 显示倒计时和连击
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        # 倒计时颜色变化
        color = "#28a745" if remaining > 30 else "#ffc107" if remaining > 10 else "#dc3545"
        st.markdown(f"""
        <div style='background: {color}; border-radius: 10px; padding: 15px; color: white; text-align: center;'>
            <h2>⏱️ {remaining:.0f}s</h2>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.metric("得分", st.session_state.speed_score)
    with col3:
        combo = st.session_state.speed_combo
        combo_text = f"🔥 x{combo}" if combo > 0 else "x0"
        st.metric("连击", combo_text)
    with col4:
        st.metric("题数", st.session_state.speed_index)
    
    st.markdown("---")
    
    # 当前单词
    if st.session_state.speed_index >= len(st.session_state.speed_words):
        st.warning("题目已用完，挑战结束！")
        st.session_state.speed_finished = True
        st.rerun()
        return
    
    word = st.session_state.speed_words[st.session_state.speed_index]
    
    st.markdown(f"""
    <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                border-radius: 15px; padding: 30px; color: white; text-align: center;'>
        <h1>{word['word']}</h1>
        <p>{word.get('phonetic', '')}</p>
    </div>
    """, unsafe_allow_html=True)
    
    # 生成选项
    if st.session_state.current_question is None:
        correct_def = word['definition']
        wrong_defs = game.get_random_definitions(correct_def, 3)
        all_options = [correct_def] + wrong_defs
        random.shuffle(all_options)
        st.session_state.current_question = {
            "options": all_options,
            "correct": correct_def
        }
    
    question = st.session_state.current_question
    
    # 两列显示选项
    col1, col2 = st.columns(2)
    for i, option in enumerate(question["options"]):
        with col1 if i < 2 else col2:
            if st.button(f"{chr(65+i)}. {option}", key=f"speed_opt_{i}", use_container_width=True):
                is_correct = (option == question["correct"])
                
                if is_correct:
                    st.session_state.speed_combo += 1
                    st.session_state.speed_max_combo = max(
                        st.session_state.speed_max_combo, 
                        st.session_state.speed_combo
                    )
                    # 连击加成
                    combo_bonus = min(st.session_state.speed_combo, 5)  # 最多5倍
                    points = 10 + (combo_bonus - 1) * 2
                    st.session_state.speed_score += points
                    st.session_state.speed_index += 1
                    st.session_state.correct_answers += 1
                    st.session_state.mastered_words.add(word['word'])
                else:
                    st.session_state.speed_combo = 0
                    st.session_state.wrong_words.append(word)
                    st.session_state.speed_index += 1
                
                st.session_state.total_questions += 1
                st.session_state.current_question = None
                st.rerun()


def render_spelling_mode(game: WordGame):
    """渲染拼写大师模式 - 看释义拼写单词"""
    st.markdown("## ✍️ 拼写大师")
    st.markdown("看释义，拼写正确的单词！")
    
    # 初始化拼写练习
    if st.session_state.spelling_word is None:
        words = game.get_words_for_floor(st.session_state.current_floor, limit=1)
        if words:
            st.session_state.spelling_word = words[0]
            st.session_state.spelling_hint_used = False
            st.session_state.spelling_attempts = 0
    
    word_data = st.session_state.spelling_word
    
    if not word_data:
        st.warning("暂无单词数据")
        if st.button("🏠 返回主页", key="spell_no_word_home"):
            st.session_state.game_mode = "menu"
            st.rerun()
        return
    
    correct_word = word_data['word'].lower().strip()
    
    # 显示释义
    st.markdown(f"""
    <div style='background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); 
                border-radius: 15px; padding: 30px; color: white; text-align: center;'>
        <h3>📖 释义</h3>
        <h2>{word_data['definition']}</h2>
        <p>词性: {word_data.get('pos', '未知')}</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # 提示功能
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("💡 显示首字母", disabled=st.session_state.spelling_hint_used, key="spell_hint"):
            st.session_state.spelling_hint_used = True
            st.rerun()
    with col2:
        if st.button("🔊 显示音标", key="spell_phonetic"):
            st.info(f"音标: {word_data.get('phonetic', '无')}")
    with col3:
        if st.button("⏭️ 跳过本题", key="spell_skip"):
            st.session_state.wrong_words.append(word_data)
            st.session_state.spelling_word = None
            st.rerun()
    
    # 显示提示
    if st.session_state.spelling_hint_used:
        hint_len = min(2, len(correct_word))
        hint = correct_word[:hint_len] + "_" * (len(correct_word) - hint_len)
        st.info(f"💡 提示: {hint} (共 {len(correct_word)} 个字母)")
    
    # 输入答案
    with st.form("spelling_form"):
        user_input = st.text_input("请拼写单词:", placeholder="输入你的答案...")
        submitted = st.form_submit_button("✅ 提交", use_container_width=True)
    
    # 处理表单提交结果（在form外部）
    if submitted and user_input:
        user_answer = user_input.lower().strip()
        
        if user_answer == correct_word:
            st.success(f"🎉 正确！单词是: **{correct_word}**")
            
            # 计分：无提示20分，有提示10分
            points = 10 if st.session_state.spelling_hint_used else 20
            st.session_state.score += points
            st.session_state.correct_answers += 1
            st.session_state.total_questions += 1
            st.session_state.mastered_words.add(correct_word)
            
            # 更新拼写计数
            st.session_state.spelling_correct = st.session_state.get("spelling_correct", 0) + 1
            
            # 检查成就
            newly_unlocked, _ = check_achievements()
            for name, desc in newly_unlocked:
                st.success(f"🏆 解锁成就: {name}")
            
            st.session_state.spelling_word = None
        else:
            st.session_state.spelling_attempts += 1
            if st.session_state.spelling_attempts >= 3:
                st.error(f"❌ 答案是: **{correct_word}**")
                st.session_state.wrong_words.append(word_data)
                st.session_state.total_questions += 1
                st.session_state.spelling_word = None
            else:
                st.warning(f"❌ 再试试！还有 {3 - st.session_state.spelling_attempts} 次机会")
    
    # 下一题按钮（独立于表单）
    if st.session_state.spelling_word is None:
        if st.button("➡️ 下一题", use_container_width=True, key="spelling_next"):
            st.rerun()  # 刷新页面获取新单词
    
    st.markdown("---")
    if st.button("🏠 返回主页", use_container_width=True, key="spelling_home"):
        st.session_state.game_mode = "menu"
        st.rerun()


def get_custom_prizes(game: WordGame, prize_type: str = "all") -> list:
    """从数据库获取自定义奖励列表
    prize_type: 'parent' - 家长奖励, 'teacher' - 教师奖励, 'all' - 全部
    """
    if prize_type == "all":
        query = """
        MATCH (p:Prize)
        RETURN p.name AS name, p.description AS description, p.weight AS weight, p.type AS type
        ORDER BY p.weight DESC
        """
    else:
        query = """
        MATCH (p:Prize {type: $prize_type})
        RETURN p.name AS name, p.description AS description, p.weight AS weight, p.type AS type
        ORDER BY p.weight DESC
        """
    
    session = game.db.get_session()
    if session:
        with session:
            if prize_type == "all":
                result = session.run(query)
            else:
                result = session.run(query, prize_type=prize_type)
            prizes = [dict(record) for record in result]
            if prizes:
                return prizes
    
    # 默认奖励（如果没有自定义奖励）
    default_parent = [
        {"name": "🍫 巧克力", "description": "一块巧克力", "weight": 20, "type": "parent"},
        {"name": "🎮 游戏时间", "description": "15分钟游戏", "weight": 15, "type": "parent"},
        {"name": "🍦 冰淇淋", "description": "一个冰淇淋", "weight": 15, "type": "parent"},
        {"name": "💪 继续加油", "description": "下次好运", "weight": 50, "type": "parent"},
    ]
    default_teacher = [
        {"name": "⭐ 积分+50", "description": "+50积分", "weight": 15, "type": "teacher"},
        {"name": "📖 免作业卡", "description": "一次免作业", "weight": 10, "type": "teacher"},
        {"name": "🌟 表扬信", "description": "老师表扬信", "weight": 25, "type": "teacher"},
        {"name": "💪 再接再厉", "description": "下次好运", "weight": 50, "type": "teacher"},
    ]
    
    if prize_type == "parent":
        return default_parent
    elif prize_type == "teacher":
        return default_teacher
    else:
        return default_parent + default_teacher


def save_custom_prizes(game: WordGame, prizes: list, prize_type: str):
    """保存自定义奖励到数据库
    prize_type: 'parent' - 家长奖励, 'teacher' - 教师奖励
    """
    # 先删除该类型的旧奖励
    delete_query = "MATCH (p:Prize {type: $prize_type}) DELETE p"
    
    # 创建新的奖励
    create_query = """
    CREATE (p:Prize {name: $name, description: $description, weight: $weight, type: $prize_type})
    """
    
    session = game.db.get_session()
    if session:
        with session:
            session.run(delete_query, prize_type=prize_type)
            for prize in prizes:
                session.run(create_query, 
                           name=prize["name"],
                           description=prize["description"],
                           weight=prize["weight"],
                           prize_type=prize_type)


def get_top_students(game: WordGame, limit: int = 3) -> list:
    """获取排行榜前N名学生"""
    query = """
    MATCH (u:User)
    WHERE u.score IS NOT NULL
    RETURN u.id AS user_id, 
           u.score AS score,
           u.total_questions AS total_questions,
           u.correct_answers AS correct_answers,
           u.current_floor AS current_floor
    ORDER BY u.score DESC
    LIMIT $limit
    """
    
    session = game.db.get_session()
    if session:
        with session:
            result = session.run(query, limit=limit)
            return [dict(record) for record in result]
    return []


def render_lucky_wheel(game: WordGame):
    """渲染幸运抽奖 - 分家长奖和教师奖"""
    st.markdown("## 🎁 幸运抽奖")
    st.markdown("每天答对10题可抽奖一次，最多3次！选择抽取家长奖或教师奖～")
    
    # 检查今日抽奖资格
    questions_today = st.session_state.total_questions
    spins_allowed = min(questions_today // 10, 3)
    spins_used = st.session_state.lucky_spins_today
    spins_remaining = spins_allowed - spins_used
    
    st.markdown("---")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("今日答题", st.session_state.total_questions)
    with col2:
        st.metric("可抽次数", spins_remaining)
    with col3:
        st.metric("当前积分", st.session_state.score)
    
    st.markdown("---")
    
    # 获取家长和教师奖励
    parent_prizes = get_custom_prizes(game, "parent")
    teacher_prizes = get_custom_prizes(game, "teacher")
    
    # 显示两个奖池 - 每个奖池下面直接带抽奖按钮
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 👨‍👩‍👧 家长奖池")
        for prize in parent_prizes:
            weight = prize.get("weight", 10)
            if weight <= 15:
                bg_color = "linear-gradient(135deg, #ff6b6b 0%, #ee5a24 100%)"
            elif weight <= 25:
                bg_color = "linear-gradient(135deg, #ffd700 0%, #ffb347 100%)"
            else:
                bg_color = "linear-gradient(135deg, #a8edea 0%, #fed6e3 100%)"
            
            st.markdown(f"""
            <div style='background: {bg_color}; 
                        border-radius: 8px; padding: 10px; text-align: center; margin: 5px 0;'>
                <span style='font-size: 1.1rem;'>{prize['name']}</span>
                <span style='font-size: 0.85rem; color: #555;'> - {prize['description']}</span>
            </div>
            """, unsafe_allow_html=True)
        
        # 家长奖抽奖按钮 - 直接在奖池下方
        st.markdown("")
        if spins_remaining > 0:
            if st.button("🎰 抽家长奖！", use_container_width=True, type="primary", key="draw_parent"):
                if parent_prizes:
                    weights = [p.get("weight", 10) for p in parent_prizes]
                    result = random.choices(parent_prizes, weights=weights, k=1)[0]
                    
                    st.session_state.lucky_spins_today += 1
                    
                    # 检查积分奖励
                    desc = result.get("description", "")
                    if "积分" in desc:
                        try:
                            points = int(''.join(filter(str.isdigit, desc)))
                            st.session_state.score += points
                        except:
                            pass
                    
                    st.session_state.lottery_result = {
                        "type": "parent",
                        "name": result['name'],
                        "description": result['description']
                    }
                    st.rerun()
        else:
            st.button("🎰 抽家长奖！", use_container_width=True, disabled=True, key="draw_parent_disabled")
    
    with col2:
        st.markdown("### 👨‍🏫 教师奖池")
        for prize in teacher_prizes:
            weight = prize.get("weight", 10)
            if weight <= 15:
                bg_color = "linear-gradient(135deg, #667eea 0%, #764ba2 100%)"
            elif weight <= 25:
                bg_color = "linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)"
            else:
                bg_color = "linear-gradient(135deg, #11998e 0%, #38ef7d 100%)"
            
            st.markdown(f"""
            <div style='background: {bg_color}; 
                        border-radius: 8px; padding: 10px; text-align: center; margin: 5px 0;'>
                <span style='font-size: 1.1rem; color: white;'>{prize['name']}</span>
                <span style='font-size: 0.85rem; color: #eee;'> - {prize['description']}</span>
            </div>
            """, unsafe_allow_html=True)
        
        # 教师奖抽奖按钮 - 直接在奖池下方
        st.markdown("")
        if spins_remaining > 0:
            if st.button("🎰 抽教师奖！", use_container_width=True, type="secondary", key="draw_teacher"):
                if teacher_prizes:
                    weights = [p.get("weight", 10) for p in teacher_prizes]
                    result = random.choices(teacher_prizes, weights=weights, k=1)[0]
                    
                    st.session_state.lucky_spins_today += 1
                    
                    # 检查积分奖励
                    desc = result.get("description", "")
                    if "积分" in desc:
                        try:
                            points = int(''.join(filter(str.isdigit, desc)))
                            st.session_state.score += points
                        except:
                            pass
                    
                    st.session_state.lottery_result = {
                        "type": "teacher",
                        "name": result['name'],
                        "description": result['description']
                    }
                    st.rerun()
        else:
            st.button("🎰 抽教师奖！", use_container_width=True, disabled=True, key="draw_teacher_disabled")
    
    # 显示抽奖结果
    if st.session_state.get("lottery_result"):
        result = st.session_state.lottery_result
        st.markdown("---")
        st.balloons()
        if result["type"] == "parent":
            st.success(f"🎉 恭喜获得家长奖: **{result['name']}**")
            st.info(f"🎁 奖励内容: {result['description']}")
            st.caption("请找家长领取奖励哦～")
        else:
            st.success(f"🎉 恭喜获得教师奖: **{result['name']}**")
            st.info(f"🎁 奖励内容: {result['description']}")
            st.caption("请找老师领取奖励哦～")
        
        if st.button("🎁 继续抽奖", use_container_width=True):
            st.session_state.lottery_result = None
            st.rerun()
    
    # 显示抽奖提示
    if spins_remaining <= 0:
        st.markdown("---")
        if spins_allowed == 0:
            st.warning("📚 答对10题解锁第一次抽奖机会！加油学习吧！")
        else:
            st.info("😊 今日抽奖次数已用完，明天再来！")
    
    st.markdown("---")
    if st.button("🏠 返回主页", use_container_width=True):
        st.session_state.game_mode = "menu"
        st.rerun()


def render_prize_settings(game: WordGame):
    """渲染奖励设置页面（家长/教师端）"""
    st.markdown("## ⚙️ 抽奖奖励设置")
    st.markdown("自定义抽奖奖励，激励学生学习！")
    
    # 判断当前是家长端还是教师端
    is_parent = st.session_state.admin_logged_in == "parent"
    prize_type = "parent" if is_parent else "teacher"
    role_name = "家长" if is_parent else "教师"
    role_icon = "👨‍👩‍👧" if is_parent else "👨‍🏫"
    
    st.markdown(f"### {role_icon} 设置{role_name}奖励")
    st.caption(f"这里设置的奖励会显示在学生抽奖页面的「{role_name}奖池」中")
    
    st.markdown("---")
    
    # 获取当前奖励
    current_prizes = get_custom_prizes(game, prize_type)
    
    st.markdown(f"### 📋 当前{role_name}奖励")
    
    if current_prizes:
        for i, prize in enumerate(current_prizes):
            col1, col2, col3 = st.columns([2, 3, 2])
            with col1:
                st.text(f"{prize['name']}")
            with col2:
                st.text(prize['description'])
            with col3:
                st.text(f"权重: {prize.get('weight', 10)}")
    else:
        st.info("暂未设置奖励，请添加")
    
    st.markdown("---")
    st.markdown("### ✏️ 编辑奖励")
    st.caption("💡 权重越高，抽中概率越大。建议大奖权重5-15，小奖权重30-50")
    
    with st.form("prize_form"):
        st.markdown(f"#### 设置{role_name}奖励列表")
        
        # 4个奖励输入
        new_prizes = []
        for i in range(4):
            st.markdown(f"**奖励 {i+1}**")
            cols = st.columns([2, 3, 2])
            
            default_name = current_prizes[i]['name'] if i < len(current_prizes) else f"奖励{i+1}"
            default_desc = current_prizes[i]['description'] if i < len(current_prizes) else "奖励描述"
            default_weight = current_prizes[i].get('weight', 20) if i < len(current_prizes) else 20
            
            with cols[0]:
                name = st.text_input(f"名称", value=default_name, key=f"prize_name_{prize_type}_{i}")
            with cols[1]:
                desc = st.text_input(f"描述", value=default_desc, key=f"prize_desc_{prize_type}_{i}")
            with cols[2]:
                weight = st.number_input(f"权重", min_value=1, max_value=100, value=default_weight, key=f"prize_weight_{prize_type}_{i}")
            
            if name and desc:
                new_prizes.append({"name": name, "description": desc, "weight": weight})
        
        submitted = st.form_submit_button("💾 保存奖励设置", use_container_width=True)
        
        if submitted and new_prizes:
            save_custom_prizes(game, new_prizes, prize_type)
            st.success(f"✅ {role_name}奖励设置已保存！")
            st.rerun()
    
    st.markdown("---")
    
    # 预设模板（根据角色不同提供不同模板）
    st.markdown("### 📦 快速模板")
    
    if is_parent:
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🍬 零食奖励", use_container_width=True):
                template = [
                    {"name": "🍫 巧克力", "description": "一块巧克力", "weight": 20},
                    {"name": "🍦 冰淇淋", "description": "一个冰淇淋", "weight": 15},
                    {"name": "🎮 游戏时间", "description": "15分钟游戏", "weight": 15},
                    {"name": "💪 继续加油", "description": "下次好运", "weight": 50},
                ]
                save_custom_prizes(game, template, "parent")
                st.success("✅ 已应用零食奖励模板！")
                st.rerun()
        with col2:
            if st.button("🎁 综合奖励", use_container_width=True):
                template = [
                    {"name": "🎁 神秘礼物", "description": "家长准备惊喜", "weight": 10},
                    {"name": "📺 看动画", "description": "看一集动画", "weight": 20},
                    {"name": "🍕 美食", "description": "选一顿好吃的", "weight": 20},
                    {"name": "💪 再接再厉", "description": "下次好运", "weight": 50},
                ]
                save_custom_prizes(game, template, "parent")
                st.success("✅ 已应用综合奖励模板！")
                st.rerun()
    else:
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📚 学习奖励", use_container_width=True):
                template = [
                    {"name": "📖 免作业卡", "description": "一次免作业", "weight": 10},
                    {"name": "⭐ 积分+50", "description": "+50积分", "weight": 20},
                    {"name": "🌟 表扬信", "description": "老师表扬信", "weight": 20},
                    {"name": "💪 再接再厉", "description": "下次好运", "weight": 50},
                ]
                save_custom_prizes(game, template, "teacher")
                st.success("✅ 已应用学习奖励模板！")
                st.rerun()
        with col2:
            if st.button("🏆 荣誉奖励", use_container_width=True):
                template = [
                    {"name": "🎖️ 学习之星", "description": "获得学习之星称号", "weight": 10},
                    {"name": "📣 课堂表扬", "description": "课堂公开表扬", "weight": 25},
                    {"name": "⭐ 积分+30", "description": "+30积分", "weight": 25},
                    {"name": "💪 继续努力", "description": "下次好运", "weight": 40},
                ]
                save_custom_prizes(game, template, "teacher")
                st.success("✅ 已应用荣誉奖励模板！")
                st.rerun()
    
    st.markdown("---")
    if st.button("🔙 返回管理面板", use_container_width=True):
        if st.session_state.admin_logged_in == "parent":
            st.session_state.game_mode = "parent_dashboard"
        else:
            st.session_state.game_mode = "teacher_dashboard"
        st.rerun()


def render_achievements():
    """渲染成就殿堂"""
    st.markdown("## 🏅 成就殿堂")
    st.markdown("收集所有成就，成为单词大师！")
    
    _, achievements_config = check_achievements()
    unlocked = st.session_state.achievements
    
    total_achievements = len(achievements_config)
    unlocked_count = len(unlocked)
    
    st.progress(unlocked_count / total_achievements)
    st.caption(f"已解锁: {unlocked_count}/{total_achievements}")
    
    st.markdown("---")
    
    # 分类显示成就
    categories = {
        "📝 答题成就": ["first_blood", "ten_correct", "fifty_correct", "hundred_correct"],
        "🏰 闯关成就": ["floor_3", "floor_6", "floor_9"],
        "⭐ 积分成就": ["score_100", "score_500", "score_1000"],
        "🔥 连击成就": ["streak_3", "streak_10"],
        "📅 坚持成就": ["daily_3", "daily_7"],
        "🎮 特殊成就": ["spelling_master", "speed_demon"],
    }
    
    for category, keys in categories.items():
        st.markdown(f"### {category}")
        cols = st.columns(len(keys))
        
        for i, key in enumerate(keys):
            if key in achievements_config:
                name, desc, _ = achievements_config[key]
                is_unlocked = key in unlocked
                
                with cols[i]:
                    if is_unlocked:
                        st.markdown(f"""
                        <div style='background: linear-gradient(135deg, #ffd700 0%, #ffb347 100%); 
                                    border-radius: 10px; padding: 15px; text-align: center;'>
                            <p style='margin:0; font-size: 1.5rem;'>{name.split()[0]}</p>
                            <p style='margin:0; font-weight: bold;'>{' '.join(name.split()[1:])}</p>
                            <p style='margin:0; font-size: 0.8rem; color: #666;'>{desc}</p>
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.markdown(f"""
                        <div style='background: #ddd; border-radius: 10px; padding: 15px; text-align: center;'>
                            <p style='margin:0; font-size: 1.5rem;'>🔒</p>
                            <p style='margin:0; font-weight: bold; color: #999;'>???</p>
                            <p style='margin:0; font-size: 0.8rem; color: #999;'>{desc}</p>
                        </div>
                        """, unsafe_allow_html=True)
    
    st.markdown("---")
    if st.button("🏠 返回主页", use_container_width=True):
        st.session_state.game_mode = "menu"
        st.rerun()


def render_parent_login(game: WordGame):
    """渲染家长端登录页面"""
    st.markdown("## 👨‍👩‍👧 家长端登录")
    st.markdown("登录后可查看您孩子的学习数据")
    
    st.markdown("---")
    
    with st.form("parent_login_form"):
        student_id = st.text_input("请输入学生姓名/学号")
        password = st.text_input("请输入家长密码", type="password")
        
        submitted = st.form_submit_button("登录", use_container_width=True)
        
        if submitted:
            if not student_id:
                st.error("请输入学生姓名/学号")
            else:
                # 先检查教师设置的学生专属密码
                student_password = game.get_parent_password(student_id)
                
                # 如果有学生专属密码，使用专属密码验证
                # 否则使用默认的家长密码
                if student_password:
                    if password == student_password:
                        st.session_state.admin_logged_in = "parent"
                        st.session_state.selected_student_id = student_id
                        st.session_state.game_mode = "parent_dashboard"
                        st.rerun()
                    else:
                        st.error("密码错误！请使用教师为该学生设置的家长密码")
                else:
                    # 没有专属密码，使用默认密码
                    if password == ADMIN_PASSWORDS["parent"]:
                        st.session_state.admin_logged_in = "parent"
                        st.session_state.selected_student_id = student_id
                        st.session_state.game_mode = "parent_dashboard"
                        st.rerun()
                    else:
                        st.error("密码错误！")
    
    st.markdown("---")
    st.info("💡 提示：如果老师为您的孩子设置了专属密码，请使用专属密码登录")
    
    if st.button("🏠 返回主页"):
        st.session_state.game_mode = "menu"
        st.rerun()


def render_parent_dashboard(game: WordGame):
    """渲染家长端仪表盘"""
    st.markdown("## 👨‍👩‍👧 家长端 - 学习报告")
    
    student_id = st.session_state.selected_student_id
    st.markdown(f"### 学生: **{student_id}**")
    
    st.markdown("---")
    
    # 获取学生数据
    student = game.get_user_by_id(student_id)
    
    if student:
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown("""
            <div class='admin-card'>
                <h3>📝</h3>
                <p>总答题数</p>
                <h2>{}</h2>
            </div>
            """.format(student.get("total_questions", 0)), unsafe_allow_html=True)
        
        with col2:
            st.markdown("""
            <div class='admin-card'>
                <h3>✅</h3>
                <p>正确数</p>
                <h2>{}</h2>
            </div>
            """.format(student.get("correct_answers", 0)), unsafe_allow_html=True)
        
        with col3:
            total = student.get("total_questions", 0)
            correct = student.get("correct_answers", 0)
            accuracy = (correct / total * 100) if total > 0 else 0
            st.markdown("""
            <div class='admin-card'>
                <h3>📊</h3>
                <p>正确率</p>
                <h2>{:.1f}%</h2>
            </div>
            """.format(accuracy), unsafe_allow_html=True)
        
        with col4:
            st.markdown("""
            <div class='admin-card'>
                <h3>🏆</h3>
                <p>总积分</p>
                <h2>{}</h2>
            </div>
            """.format(student.get("score", 0)), unsafe_allow_html=True)
        
        st.markdown("---")
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("### 📈 学习详情")
            st.markdown(f"- **当前楼层**: {student.get('current_floor', 1)}F")
            st.markdown(f"- **已掌握单词**: {student.get('mastered_count', 0)} 个")
            st.markdown(f"- **待复习单词**: {student.get('wrong_count', 0)} 个")
        
        with col2:
            st.markdown("### 📅 学习时间")
            last_active = student.get("last_active")
            if last_active:
                st.markdown(f"- **最后活跃**: {last_active}")
            else:
                st.markdown("- **最后活跃**: 暂无记录")
    else:
        st.warning(f"未找到学生 **{student_id}** 的学习记录")
        st.info("提示：学生需要先在游戏中输入姓名/学号并完成至少一层挑战才会有记录")
    
    st.markdown("---")
    
    # 奖励设置入口
    st.markdown("### ⚙️ 管理功能")
    if st.button("🎁 设置抽奖奖励", use_container_width=True):
        st.session_state.game_mode = "prize_settings"
        st.rerun()
    
    # 数据管理
    st.markdown("---")
    st.markdown("### 🗑️ 数据管理")
    st.caption(f"清空 **{student_id}** 的学习数据")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 重置数据", use_container_width=True, help="保留账号但清零所有学习记录"):
            if "confirm_reset_child" not in st.session_state:
                st.session_state.confirm_reset_child = True
                st.rerun()
    with col2:
        if st.button("🗑️ 删除账号", use_container_width=True, type="secondary", help="完全删除该学生账号"):
            if "confirm_delete_child" not in st.session_state:
                st.session_state.confirm_delete_child = True
                st.rerun()
    
    # 确认重置对话框
    if st.session_state.get("confirm_reset_child"):
        st.warning(f"⚠️ 确定要重置 **{student_id}** 的所有学习数据吗？积分、答题记录将清零！")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ 确认重置", use_container_width=True, type="primary"):
                if game.reset_user_data(student_id):
                    st.success(f"✅ 已重置 {student_id} 的学习数据")
                    st.session_state.confirm_reset_child = False
                    st.rerun()
                else:
                    st.error("重置失败，请重试")
        with col2:
            if st.button("❌ 取消", use_container_width=True, key="cancel_reset_child"):
                st.session_state.confirm_reset_child = False
                st.rerun()
    
    # 确认删除对话框
    if st.session_state.get("confirm_delete_child"):
        st.error(f"⚠️ 确定要完全删除 **{student_id}** 的账号吗？此操作不可恢复！")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ 确认删除", use_container_width=True, type="primary"):
                if game.delete_user(student_id):
                    st.success(f"✅ 已删除 {student_id} 的账号")
                    st.session_state.confirm_delete_child = False
                    st.session_state.selected_student_id = None
                    st.rerun()
                else:
                    st.error("删除失败，请重试")
        with col2:
            if st.button("❌ 取消", use_container_width=True, key="cancel_delete_child"):
                st.session_state.confirm_delete_child = False
                st.rerun()
    
    st.markdown("---")
    if st.button("🚪 退出家长端", use_container_width=True):
        st.session_state.admin_logged_in = None
        st.session_state.selected_student_id = None
        st.session_state.game_mode = "menu"
        st.rerun()


def render_teacher_login():
    """渲染教师端登录页面"""
    st.markdown("## 👨‍🏫 教师端登录")
    st.markdown("登录后可查看所有学生的学习情况")
    
    st.markdown("---")
    
    with st.form("teacher_login_form"):
        password = st.text_input("请输入教师密码", type="password")
        
        submitted = st.form_submit_button("登录", use_container_width=True)
        
        if submitted:
            if password == ADMIN_PASSWORDS["teacher"]:
                st.session_state.admin_logged_in = "teacher"
                st.session_state.game_mode = "teacher_dashboard"
                st.rerun()
            else:
                st.error("密码错误！")
    
    st.markdown("---")
    if st.button("🏠 返回主页"):
        st.session_state.game_mode = "menu"
        st.rerun()


def render_teacher_dashboard(game: WordGame):
    """渲染教师端仪表盘"""
    st.markdown("## 👨‍🏫 教师端 - 全班学习数据")
    
    st.markdown("---")
    
    # 获取所有学生数据
    students = game.get_all_users()
    
    if not students:
        st.warning("暂无学生学习记录")
        st.info("提示：学生需要先在游戏中输入姓名/学号并完成至少一层挑战才会有记录")
    else:
        # 统计概览
        st.markdown("### 📊 班级概览")
        
        total_students = len(students)
        total_questions = sum(s.get("total_questions", 0) or 0 for s in students)
        total_correct = sum(s.get("correct_answers", 0) or 0 for s in students)
        avg_accuracy = (total_correct / total_questions * 100) if total_questions > 0 else 0
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown("""
            <div class='teacher-card'>
                <h3>👥</h3>
                <p>学生人数</p>
                <h2>{}</h2>
            </div>
            """.format(total_students), unsafe_allow_html=True)
        
        with col2:
            st.markdown("""
            <div class='teacher-card'>
                <h3>📝</h3>
                <p>总答题数</p>
                <h2>{}</h2>
            </div>
            """.format(total_questions), unsafe_allow_html=True)
        
        with col3:
            st.markdown("""
            <div class='teacher-card'>
                <h3>📊</h3>
                <p>平均正确率</p>
                <h2>{:.1f}%</h2>
            </div>
            """.format(avg_accuracy), unsafe_allow_html=True)
        
        with col4:
            top_score = max(s.get("score", 0) or 0 for s in students) if students else 0
            st.markdown("""
            <div class='teacher-card'>
                <h3>🏆</h3>
                <p>最高积分</p>
                <h2>{}</h2>
            </div>
            """.format(top_score), unsafe_allow_html=True)
        
        st.markdown("---")
        
        # 学生排行榜
        st.markdown("### 🏅 学生排行榜（按积分排序）")
        
        for i, student in enumerate(students, 1):
            total = student.get("total_questions", 0) or 0
            correct = student.get("correct_answers", 0) or 0
            accuracy = (correct / total * 100) if total > 0 else 0
            
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            
            st.markdown(f"""
            <div class='student-row'>
                <strong>{medal} {student.get('user_id', '未知')}</strong><br>
                📝 答题: {total} | ✅ 正确: {correct} | 📊 正确率: {accuracy:.1f}% | 
                🏆 积分: {student.get('score', 0) or 0} | 🏰 楼层: {student.get('current_floor', 1) or 1}F
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # 导出功能
        st.markdown("### 📥 数据导出")
        
        import pandas as pd
        df = pd.DataFrame([{
            "学生": s.get("user_id", ""),
            "总答题": s.get("total_questions", 0) or 0,
            "正确数": s.get("correct_answers", 0) or 0,
            "正确率": f"{((s.get('correct_answers', 0) or 0) / (s.get('total_questions', 1) or 1) * 100):.1f}%",
            "积分": s.get("score", 0) or 0,
            "楼层": s.get("current_floor", 1) or 1,
            "已掌握": s.get("mastered_count", 0) or 0,
            "待复习": s.get("wrong_count", 0) or 0,
        } for s in students])
        
        st.dataframe(df, use_container_width=True)
        
        csv = df.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            "📥 下载CSV报表",
            csv,
            "学生学习报表.csv",
            "text/csv",
            use_container_width=True
        )
    
    st.markdown("---")
    
    # 奖励设置入口
    st.markdown("### ⚙️ 管理功能")
    if st.button("🎁 设置抽奖奖励", use_container_width=True, key="teacher_prize_settings"):
        st.session_state.game_mode = "prize_settings"
        st.rerun()
    
    # 家长密码设置
    st.markdown("---")
    st.markdown("### 🔐 家长密码管理")
    st.caption("为每个学生设置专属的家长登录密码")
    
    # 获取所有学生列表
    students_for_password = game.get_all_users()
    if students_for_password:
        student_list_for_pwd = [s.get("user_id", "") for s in students_for_password if s.get("user_id")]
        
        selected_student_pwd = st.selectbox(
            "选择学生:", 
            student_list_for_pwd, 
            key="select_student_for_password"
        )
        
        if selected_student_pwd:
            # 显示当前密码状态
            current_pwd = game.get_parent_password(selected_student_pwd)
            if current_pwd:
                st.info(f"📍 当前家长密码: **{current_pwd}**")
            else:
                st.warning("⚠️ 该学生暂未设置专属密码，将使用默认密码")
            
            # 设置新密码
            new_password = st.text_input(
                "设置新的家长密码",
                key="new_parent_password",
                placeholder="输入新密码..."
            )
            
            if st.button("💾 保存密码", use_container_width=True, key="save_parent_password"):
                if new_password:
                    if game.set_parent_password(selected_student_pwd, new_password):
                        st.success(f"✅ 已为 **{selected_student_pwd}** 设置家长密码: **{new_password}**")
                        st.rerun()
                    else:
                        st.error("保存失败，请重试")
                else:
                    st.warning("请输入密码")
    else:
        st.info("暂无学生记录。学生需要先在游戏中注册才能设置密码。")
    
    # 数据管理
    st.markdown("---")
    st.markdown("### 🗑️ 数据管理")
    
    # 清空所有学生数据
    st.markdown("#### 批量操作")
    if st.button("🗑️ 清空所有学生数据", use_container_width=True, type="secondary"):
        if "confirm_delete_all" not in st.session_state:
            st.session_state.confirm_delete_all = True
            st.rerun()
    
    if st.session_state.get("confirm_delete_all"):
        st.error("⚠️ 确定要删除所有学生的数据吗？此操作不可恢复！")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ 确认删除全部", use_container_width=True, type="primary"):
                if game.delete_all_users():
                    st.success("✅ 已删除所有学生数据")
                    st.session_state.confirm_delete_all = False
                    st.rerun()
                else:
                    st.error("删除失败，请重试")
        with col2:
            if st.button("❌ 取消", use_container_width=True, key="cancel_delete_all"):
                st.session_state.confirm_delete_all = False
                st.rerun()
    
    # 删除单个学生
    st.markdown("#### 单个学生操作")
    if students:
        student_list = [s.get("user_id", "") for s in students if s.get("user_id")]
        selected_student = st.selectbox("选择要操作的学生:", student_list, key="select_student_to_manage")
        
        if selected_student:
            col1, col2 = st.columns(2)
            with col1:
                if st.button(f"🔄 重置 {selected_student}", use_container_width=True):
                    if "confirm_reset_student" not in st.session_state:
                        st.session_state.confirm_reset_student = selected_student
                        st.rerun()
            with col2:
                if st.button(f"🗑️ 删除 {selected_student}", use_container_width=True, type="secondary"):
                    if "confirm_delete_student" not in st.session_state:
                        st.session_state.confirm_delete_student = selected_student
                        st.rerun()
            
            # 确认重置单个学生
            if st.session_state.get("confirm_reset_student") == selected_student:
                st.warning(f"⚠️ 确定要重置 **{selected_student}** 的学习数据吗？")
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✅ 确认重置", use_container_width=True, type="primary", key="confirm_reset_btn"):
                        if game.reset_user_data(selected_student):
                            st.success(f"✅ 已重置 {selected_student} 的数据")
                            st.session_state.confirm_reset_student = None
                            st.rerun()
                with col2:
                    if st.button("❌ 取消", use_container_width=True, key="cancel_reset_student"):
                        st.session_state.confirm_reset_student = None
                        st.rerun()
            
            # 确认删除单个学生
            if st.session_state.get("confirm_delete_student") == selected_student:
                st.error(f"⚠️ 确定要删除 **{selected_student}** 的账号吗？")
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✅ 确认删除", use_container_width=True, type="primary", key="confirm_delete_btn"):
                        if game.delete_user(selected_student):
                            st.success(f"✅ 已删除 {selected_student}")
                            st.session_state.confirm_delete_student = None
                            st.rerun()
                with col2:
                    if st.button("❌ 取消", use_container_width=True, key="cancel_delete_student"):
                        st.session_state.confirm_delete_student = None
                        st.rerun()
    
    st.markdown("---")
    if st.button("🚪 退出教师端", use_container_width=True):
        st.session_state.admin_logged_in = None
        st.session_state.game_mode = "menu"
        st.rerun()


def main():
    """主函数"""
    # 初始化会话状态
    init_session_state()
    
    # 连接数据库
    db = Neo4jConnection()
    game = WordGame(db)
    
    # 渲染侧边栏（传递game以显示排行榜）
    render_sidebar(game)
    
    # 根据游戏模式渲染不同页面
    mode = st.session_state.game_mode
    
    if mode == "menu":
        render_main_menu(game)
    elif mode == "tower_select":
        render_floor_select(game)
    elif mode == "tower":
        render_tower_mode(game)
    elif mode == "root_explore":
        render_root_explore(game)
    elif mode == "review":
        render_review_mode(game)
    elif mode == "speed_challenge":
        render_speed_challenge(game)
    elif mode == "spelling":
        render_spelling_mode(game)
    elif mode == "lucky_wheel":
        render_lucky_wheel(game)
    elif mode == "prize_settings":
        render_prize_settings(game)
    elif mode == "achievements":
        render_achievements()
    elif mode == "parent_login":
        render_parent_login(game)
    elif mode == "parent_dashboard":
        render_parent_dashboard(game)
    elif mode == "teacher_login":
        render_teacher_login()
    elif mode == "teacher_dashboard":
        render_teacher_dashboard(game)


if __name__ == "__main__":
    main()
