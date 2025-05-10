# app/commands/init_hot_topic_platforms.py
"""初始化热点平台数据的命令行脚本"""
import click
import logging
from flask.cli import with_appcontext
from flask import current_app

from app.infrastructure.database.repositories.hot_topic_repository import HotTopicPlatformRepository
from app.infrastructure.database.session import get_db_session

logger = logging.getLogger(__name__)

@click.command('init-hot-platforms')
@with_appcontext
def init_hot_platforms_command():
    """初始化热点平台数据"""
    try:
        db_session = get_db_session()
        platform_repo = HotTopicPlatformRepository(db_session)
        
        # 默认平台数据
        default_platforms = [
            {
                "code": "weibo",
                "name": "微博热搜",
                "icon": "fab fa-weibo",
                "description": "新浪微博热搜榜单",
                "url": "https://s.weibo.com/top/summary",
                "display_order": 10,
                "is_active": True
            },
            {
                "code": "zhihu",
                "name": "知乎热榜",
                "icon": "fab fa-zhihu",
                "description": "知乎热门话题榜单",
                "url": "https://www.zhihu.com/hot",
                "display_order": 20,
                "is_active": True
            },
            {
                "code": "baidu",
                "name": "百度热搜",
                "icon": "fas fa-search",
                "description": "百度搜索风云榜",
                "url": "https://top.baidu.com/board",
                "display_order": 30,
                "is_active": True
            },
            {
                "code": "toutiao",
                "name": "今日头条",
                "icon": "far fa-newspaper",
                "description": "今日头条热榜",
                "url": "https://tophub.today/n/x9ozB4KoXb",
                "display_order": 40,
                "is_active": True
            },
            {
                "code": "douyin",
                "name": "抖音热点",
                "icon": "fab fa-tiktok",
                "description": "抖音热门话题榜单",
                "url": "https://www.douyin.com/hot",
                "display_order": 50,
                "is_active": True
            }
        ]
        
        created_count = 0
        updated_count = 0
        
        # 遍历并添加/更新平台
        for platform_data in default_platforms:
            code = platform_data["code"]
            existing = platform_repo.get_platform_by_code(code)
            
            if existing:
                # 更新现有平台
                platform_repo.update_platform(code, platform_data)
                updated_count += 1
                click.echo(f"更新平台: {code} ({platform_data['name']})")
            else:
                # 创建新平台
                platform_repo.create_platform(platform_data)
                created_count += 1
                click.echo(f"新增平台: {code} ({platform_data['name']})")
        
        click.echo(f"初始化完成! 创建了 {created_count} 个新平台，更新了 {updated_count} 个现有平台。")
        
    except Exception as e:
        click.echo(f"初始化热点平台失败: {str(e)}")
        logger.error(f"初始化热点平台失败: {str(e)}", exc_info=True)

def register_commands(app):
    """注册命令到Flask应用"""
    app.cli.add_command(init_hot_platforms_command)