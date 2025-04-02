"""分页工具"""
from typing import Dict, Any, List, TypeVar, Tuple, Generic
from sqlalchemy.orm.query import Query

T = TypeVar('T')

class PaginatedResult(Generic[T]):
    """分页结果类"""
    
    def __init__(self, items: List[T], total: int, page: int, per_page: int):
        """初始化分页结果
        
        Args:
            items: 当前页数据
            total: 总记录数
            page: 当前页码
            per_page: 每页记录数
        """
        self.items = items
        self.total = total
        self.page = page
        self.per_page = per_page
        self.pages = (total + per_page - 1) // per_page if per_page else 0
    
    @property
    def has_prev(self) -> bool:
        """是否有上一页"""
        return self.page > 1
    
    @property
    def has_next(self) -> bool:
        """是否有下一页"""
        return self.page < self.pages
    
    @property
    def prev_page(self) -> int:
        """上一页页码"""
        return self.page - 1 if self.has_prev else self.page
    
    @property
    def next_page(self) -> int:
        """下一页页码"""
        return self.page + 1 if self.has_next else self.page
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "items": self.items,
            "total": self.total,
            "page": self.page,
            "per_page": self.per_page,
            "pages": self.pages,
            "has_prev": self.has_prev,
            "has_next": self.has_next
        }

def paginate(query: Query, page: int = 1, per_page: int = 20) -> PaginatedResult:
    """对查询结果进行分页
    
    Args:
        query: SQLAlchemy查询对象
        page: 页码，从1开始
        per_page: 每页记录数
        
    Returns:
        分页结果对象
    """
    if page < 1:
        page = 1
    if per_page < 1:
        per_page = 20
    
    items = query.limit(per_page).offset((page - 1) * per_page).all()
    total = query.order_by(None).count()
    
    return PaginatedResult(items, total, page, per_page)

def format_pagination_response(paginated_result: PaginatedResult) -> Dict[str, Any]:
    """格式化分页响应
    
    Args:
        paginated_result: 分页结果对象
        
    Returns:
        格式化的分页响应字典
    """
    return {
        "items": paginated_result.items,
        "total": paginated_result.total,
        "page": paginated_result.page,
        "per_page": paginated_result.per_page,
        "pages": paginated_result.pages,
        "has_prev": paginated_result.has_prev,
        "has_next": paginated_result.has_next
    }