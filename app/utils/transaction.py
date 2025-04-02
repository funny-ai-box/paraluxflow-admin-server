# app/utils/transaction.py
from contextlib import contextmanager
from typing import Iterator, TypeVar, Generic, Callable, Any
from sqlalchemy.orm import Session
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')

@contextmanager
def transaction(session: Session) -> Iterator[Session]:
    """事务上下文管理器
    
    Args:
        session: 数据库会话
        
    Yields:
        会话对象
        
    Raises:
        Exception: 事务失败时抛出异常
    """
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Transaction error: {str(e)}")
        raise

def with_transaction(func: Callable[..., T]) -> Callable[..., T]:
    """事务装饰器
    
    Args:
        func: 要装饰的函数
        
    Returns:
        装饰后的函数
    """
    def wrapper(*args, **kwargs):
        # 获取会话参数
        session = None
        for arg in args:
            if isinstance(arg, Session):
                session = arg
                break
        
        if session is None:
            for _, value in kwargs.items():
                if isinstance(value, Session):
                    session = value
                    break
        
        if session is None:
            raise ValueError("No SQLAlchemy Session found in arguments")
        
        with transaction(session):
            return func(*args, **kwargs)
    
    return wrapper