# 单词魔塔探险 🏰

基于 Neo4j 图数据库的英语单词学习游戏

## 项目结构

```
单词玩法/
├── .env                 # Neo4j 连接配置
├── requirements.txt     # Python 依赖
├── 所有单词.txt         # 单词数据源
├── word_parser.py       # 单词解析模块
├── neo4j_import.py      # Neo4j 数据导入脚本
├── app.py               # Streamlit 主应用
└── README.md            # 项目说明
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 导入单词数据到 Neo4j

```bash
python neo4j_import.py
```

这将会：
- 解析 `所有单词.txt` 文件
- 创建单词、年级、词根节点
- 建立单词之间的关系（同词根、所属年级等）

### 3. 启动游戏

```bash
streamlit run app.py
```

然后在浏览器打开 http://localhost:8501

## 游戏玩法

### 🏰 魔塔闯关
- 9层魔塔，对应不同年级难度
- 每层10道题，选择正确的单词释义
- 答对得分，错误进入错题本

### 🌱 词根探索
- 浏览同词根的单词家族
- 一次记住一组相关单词
- 理解词根含义，举一反三

### 📖 错题复习
- 复习答错的单词
- 标记已掌握后移出错题本

## 数据库结构

### 节点类型
- `Word` - 单词节点
- `Grade` - 年级节点
- `Root` - 词根节点
- `Floor` - 楼层节点

### 关系类型
- `BELONGS_TO` - 单词属于某年级
- `HAS_ROOT` - 单词拥有某词根
- `SAME_ROOT` - 同词根单词之间的关系

## Neo4j 配置

在 `.env` 文件中配置：

```
NEO4J_URI=neo4j+s://xxx.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_password
```

## 技术栈

- **前端**: Streamlit
- **数据库**: Neo4j Aura
- **语言**: Python 3.8+

## 开发计划

- [ ] 添加用户登录系统
- [ ] 实现艾宾浩斯复习曲线
- [ ] 添加单词发音功能
- [ ] 实现词根图谱可视化
- [ ] 添加排行榜系统
