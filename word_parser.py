# -*- coding: utf-8 -*-
"""
单词解析模块 - 解析所有单词.txt文件
提取单词、音标、词性、释义、页码和年级信息
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional
import json


@dataclass
class Word:
    """单词数据类"""
    word: str                          # 单词
    phonetic: str = ""                 # 音标
    pos: str = ""                      # 词性 (n. v. adj. adv. etc.)
    definition: str = ""               # 中文释义
    page: str = ""                     # 页码
    grade: str = ""                    # 年级来源
    difficulty: int = 1                # 难度等级 1-4
    is_phrase: bool = False            # 是否为短语
    root: str = ""                     # 词根（用于词根关联）
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "word": self.word,
            "phonetic": self.phonetic,
            "pos": self.pos,
            "definition": self.definition,
            "page": self.page,
            "grade": self.grade,
            "difficulty": self.difficulty,
            "is_phrase": self.is_phrase,
            "root": self.root
        }


class WordParser:
    """单词文件解析器"""
    
    # 常见词根表（用于建立词根关联）
    COMMON_ROOTS = {
        "act": ["act", "action", "active", "activity", "actor", "actress", "actually", "react", "interaction"],
        "port": ["port", "import", "export", "transport", "portable", "report", "support", "airport"],
        "dict": ["dictionary", "predict", "contradict", "indicate"],
        "ject": ["project", "reject", "inject", "object", "subject"],
        "spect": ["respect", "expect", "inspect", "aspect", "spectator"],
        "struct": ["structure", "construct", "instruct", "destroy"],
        "vis/vid": ["visible", "visit", "vision", "video", "provide", "divide"],
        "aud": ["audience", "audio", "auditorium"],
        "scrib/script": ["describe", "subscribe", "script", "prescription"],
        "duc/duct": ["produce", "reduce", "introduce", "conduct", "educate"],
        "form": ["form", "inform", "perform", "transform", "uniform"],
        "mit/mis": ["permit", "submit", "admit", "promise", "mission"],
        "vent/ven": ["event", "prevent", "invent", "adventure", "avenue"],
        "tend/tens": ["attend", "extend", "intend", "tension"],
        "cess/ced": ["process", "success", "access", "proceed"],
        "press": ["express", "impress", "pressure", "depress"],
        "serve": ["serve", "reserve", "preserve", "observe", "service"],
        "sist": ["assist", "consist", "insist", "resist", "exist"],
        "cap/cep/ceiv": ["accept", "receive", "capable", "capture"],
        "cred": ["credit", "incredible", "credible"],
    }
    
    # 年级到难度的映射
    GRADE_DIFFICULTY = {
        "7年级上册": 1,
        "7年级下册": 1,
        "8年级上册": 2,
        "8年级下册": 2,
        "9年级": 3,
    }
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.words: List[Word] = []
        
    def parse(self) -> List[Word]:
        """解析单词文件"""
        with open(self.file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            word_obj = self._parse_line(line)
            if word_obj:
                self.words.append(word_obj)
        
        # 识别词根关联
        self._identify_roots()
        
        return self.words
    
    def _parse_line(self, line: str) -> Optional[Word]:
        """解析单行单词条目"""
        try:
            # 提取年级信息
            grade_match = re.search(r'\(来自:\s*([^)]+)\)', line)
            grade = grade_match.group(1).strip() if grade_match else ""
            
            # 提取页码
            page_match = re.search(r'p\.(\S+)', line)
            page = page_match.group(1) if page_match else ""
            
            # 提取音标（在 /.../ 中）
            phonetic_match = re.search(r'(/[^/]+/(?:,\s*/[^/]+/)?)', line)
            phonetic = phonetic_match.group(1) if phonetic_match else ""
            
            # 提取单词（行首到音标或词性之前）
            # 处理短语和单词两种情况
            if phonetic:
                word = line.split('/')[0].strip()
            else:
                # 对于短语或没有音标的词条
                # 查找词性标记或第一个中文字符
                pos_match = re.search(r'\s+(n\.|v\.|adj\.|adv\.|prep\.|conj\.|pron\.|art\.|num\.)', line)
                if pos_match:
                    word = line[:pos_match.start()].strip()
                else:
                    # 查找第一个中文字符位置
                    chinese_match = re.search(r'[\u4e00-\u9fff]', line)
                    if chinese_match:
                        word = line[:chinese_match.start()].strip()
                    else:
                        word = line.split()[0] if line.split() else ""
            
            # 清理单词中可能残留的音标
            word = re.sub(r'\s*/.*', '', word).strip()
            
            # 判断是否为短语
            is_phrase = ' ' in word or len(word.split()) > 1
            
            # 提取词性
            pos_match = re.search(r'\b(n\.|v\.|adj\.|adv\.|prep\.|conj\.|pron\.|art\.|num\.)', line)
            pos = pos_match.group(1) if pos_match else ""
            
            # 提取释义（词性后到页码前）
            definition = ""
            if pos:
                # 从词性后开始提取
                pos_end = line.find(pos) + len(pos)
                remaining = line[pos_end:]
                # 到页码或年级标记结束
                def_match = re.match(r'\s*(.+?)(?:\s+p\.\S+|\s*\(来自:)', remaining)
                if def_match:
                    definition = def_match.group(1).strip()
            else:
                # 没有词性的情况（通常是短语）
                # 从单词后提取到页码前
                chinese_match = re.search(r'([\u4e00-\u9fff].+?)(?:\s+p\.\S+|\s*\(来自:)', line)
                if chinese_match:
                    definition = chinese_match.group(1).strip()
            
            # 确定难度等级
            difficulty = self.GRADE_DIFFICULTY.get(grade, 2)
            
            if word:
                return Word(
                    word=word,
                    phonetic=phonetic,
                    pos=pos,
                    definition=definition,
                    page=page,
                    grade=grade,
                    difficulty=difficulty,
                    is_phrase=is_phrase
                )
            
        except Exception as e:
            print(f"解析行失败: {line[:50]}... 错误: {e}")
        
        return None
    
    def _identify_roots(self):
        """识别单词的词根"""
        word_lower_map = {w.word.lower(): w for w in self.words}
        
        for root, root_words in self.COMMON_ROOTS.items():
            for word_text in root_words:
                if word_text.lower() in word_lower_map:
                    word_lower_map[word_text.lower()].root = root.split('/')[0]  # 取第一个词根形式
    
    def get_words_by_grade(self, grade: str) -> List[Word]:
        """按年级获取单词"""
        return [w for w in self.words if grade in w.grade]
    
    def get_words_by_difficulty(self, difficulty: int) -> List[Word]:
        """按难度获取单词"""
        return [w for w in self.words if w.difficulty == difficulty]
    
    def get_words_with_root(self, root: str) -> List[Word]:
        """获取同一词根的单词"""
        return [w for w in self.words if w.root == root]
    
    def get_all_roots(self) -> List[str]:
        """获取所有已识别的词根"""
        return list(set(w.root for w in self.words if w.root))
    
    def to_json(self, output_path: str = None) -> str:
        """导出为JSON格式"""
        data = [w.to_dict() for w in self.words]
        json_str = json.dumps(data, ensure_ascii=False, indent=2)
        
        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(json_str)
        
        return json_str
    
    def get_statistics(self) -> dict:
        """获取统计信息"""
        grade_count = {}
        for w in self.words:
            if w.grade:
                grade_count[w.grade] = grade_count.get(w.grade, 0) + 1
        
        return {
            "total": len(self.words),
            "phrases": sum(1 for w in self.words if w.is_phrase),
            "single_words": sum(1 for w in self.words if not w.is_phrase),
            "with_phonetic": sum(1 for w in self.words if w.phonetic),
            "with_root": sum(1 for w in self.words if w.root),
            "by_grade": grade_count,
            "roots_identified": len(self.get_all_roots())
        }


# 测试代码
if __name__ == "__main__":
    import os
    
    # 获取当前目录
    current_dir = os.path.dirname(os.path.abspath(__file__))
    word_file = os.path.join(current_dir, "所有单词.txt")
    
    if os.path.exists(word_file):
        parser = WordParser(word_file)
        words = parser.parse()
        
        print("=" * 50)
        print("单词解析统计")
        print("=" * 50)
        
        stats = parser.get_statistics()
        print(f"总单词数: {stats['total']}")
        print(f"单词数: {stats['single_words']}")
        print(f"短语数: {stats['phrases']}")
        print(f"有音标: {stats['with_phonetic']}")
        print(f"已识别词根: {stats['with_root']}")
        print(f"词根种类: {stats['roots_identified']}")
        print("\n按年级分布:")
        for grade, count in stats['by_grade'].items():
            print(f"  {grade}: {count}")
        
        print("\n" + "=" * 50)
        print("示例单词（前10个）")
        print("=" * 50)
        for w in words[:10]:
            print(f"单词: {w.word}")
            print(f"  音标: {w.phonetic}")
            print(f"  词性: {w.pos}")
            print(f"  释义: {w.definition}")
            print(f"  年级: {w.grade}")
            print(f"  难度: {w.difficulty}")
            if w.root:
                print(f"  词根: {w.root}")
            print()
        
        # 导出JSON
        json_file = os.path.join(current_dir, "words_parsed.json")
        parser.to_json(json_file)
        print(f"已导出JSON到: {json_file}")
    else:
        print(f"找不到单词文件: {word_file}")
