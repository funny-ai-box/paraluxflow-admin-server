# app/core/constants/article_categories.py
"""
文章分类配置 - 通用分类体系
用于RSS文章、热点话题等内容的分类标注
"""

from typing import Dict, List

# 主要分类体系
ARTICLE_CATEGORIES = {
    "politics": {
        "name": "政治",
        "description": "政府政策、政治事件、官方发布等",
        "keywords": ["政府", "政策", "政治", "官方", "部门", "国务院", "发改委", "财政部"]
    },
    "economy": {
        "name": "经济",
        "description": "经济数据、市场动态、金融政策等",
        "keywords": ["经济", "金融", "股市", "房价", "GDP", "通胀", "央行", "投资"]
    },
    "technology": {
        "name": "科技",
        "description": "科技创新、互联网、人工智能等",
        "keywords": ["科技", "AI", "互联网", "芯片", "5G", "区块链", "数字化", "创新"]
    },
    "military": {
        "name": "军事",
        "description": "军事动态、国防安全、武器装备等",
        "keywords": ["军事", "国防", "武器", "军队", "战争", "安全", "导弹", "军演"]
    },
    "society": {
        "name": "社会",
        "description": "社会事件、民生新闻、社会问题等",
        "keywords": ["社会", "民生", "社区", "公共", "福利", "就业", "教育", "医疗"]
    },
    "culture": {
        "name": "文化",
        "description": "文化活动、娱乐新闻、艺术展览等",
        "keywords": ["文化", "娱乐", "艺术", "电影", "音乐", "展览", "文学", "传统"]
    },
    "sports": {
        "name": "体育",
        "description": "体育赛事、运动员动态、体育产业等",
        "keywords": ["体育", "运动", "比赛", "足球", "篮球", "奥运", "世界杯", "健身"]
    },
    "health": {
        "name": "健康",
        "description": "医疗健康、疾病防控、养生保健等",
        "keywords": ["健康", "医疗", "疾病", "疫苗", "药品", "医院", "养生", "保健"]
    },
    "education": {
        "name": "教育",
        "description": "教育政策、学校动态、升学考试等",
        "keywords": ["教育", "学校", "考试", "高考", "大学", "学生", "老师", "培训"]
    },
    "environment": {
        "name": "环境",
        "description": "环境保护、气候变化、生态治理等",
        "keywords": ["环境", "环保", "气候", "污染", "生态", "绿色", "碳排放", "新能源"]
    },
    "international": {
        "name": "国际",
        "description": "国际关系、外交事务、国外新闻等",
        "keywords": ["国际", "外交", "美国", "欧洲", "日本", "韩国", "俄罗斯", "合作"]
    },
    "disaster": {
        "name": "灾难",
        "description": "自然灾害、事故灾难、应急救援等",
        "keywords": ["地震", "台风", "洪水", "火灾", "事故", "救援", "灾害", "应急"]
    },
    "law": {
        "name": "法律",
        "description": "法律法规、司法案件、执法动态等",
        "keywords": ["法律", "法规", "法院", "司法", "案件", "判决", "执法", "律师"]
    },
    "travel": {
        "name": "旅游",
        "description": "旅游资讯、景点推荐、旅行攻略等",
        "keywords": ["旅游", "景点", "旅行", "假期", "酒店", "航班", "签证", "度假"]
    },
    "lifestyle": {
        "name": "生活",
        "description": "生活方式、消费时尚、日常生活等",
        "keywords": ["生活", "消费", "时尚", "美食", "购物", "家居", "汽车", "数码"]
    },
    "other": {
        "name": "其他",
        "description": "无法归类到以上分类的内容",
        "keywords": []
    }
}

def get_category_list() -> List[Dict[str, str]]:
    """获取分类列表
    
    Returns:
        分类列表，每个元素包含code和name
    """
    return [
        {"code": code, "name": info["name"]} 
        for code, info in ARTICLE_CATEGORIES.items()
    ]

def get_category_by_code(code: str) -> Dict[str, str]:
    """根据分类代码获取分类信息
    
    Args:
        code: 分类代码
        
    Returns:
        分类信息字典
    """
    if code in ARTICLE_CATEGORIES:
        info = ARTICLE_CATEGORIES[code]
        return {
            "code": code,
            "name": info["name"],
            "description": info["description"]
        }
    return {"code": "other", "name": "其他", "description": "无法归类的内容"}

def classify_content_by_keywords(title: str, content: str = "") -> str:
    """根据关键词自动分类内容
    
    Args:
        title: 标题
        content: 内容（可选）
        
    Returns:
        分类代码
    """
    text = (title + " " + content).lower()
    
    # 计算每个分类的匹配度
    category_scores = {}
    for code, info in ARTICLE_CATEGORIES.items():
        if code == "other":
            continue
            
        score = 0
        for keyword in info["keywords"]:
            if keyword in text:
                score += 1
        
        if score > 0:
            category_scores[code] = score
    
    # 返回得分最高的分类
    if category_scores:
        return max(category_scores.items(), key=lambda x: x[1])[0]
    
    return "other"

# 导出常用函数
__all__ = [
    "ARTICLE_CATEGORIES",
    "get_category_list", 
    "get_category_by_code",
    "classify_content_by_keywords"
]