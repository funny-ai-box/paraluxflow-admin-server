"""RSA加密工具"""
import base64
import logging
import os
from typing import Tuple

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from flask import current_app

logger = logging.getLogger(__name__)

def generate_rsa_keys(key_size: int = 2048) -> Tuple[str, str]:
    """生成RSA密钥对
    
    Args:
        key_size: 密钥大小,默认2048位
        
    Returns:
        (私钥PEM字符串, 公钥PEM字符串)
    """
    # 生成私钥
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=key_size,
        backend=default_backend()
    )
    
    # 导出私钥为PEM格式
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    ).decode('utf-8')
    
    # 导出公钥为PEM格式
    public_key = private_key.public_key()
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode('utf-8')
    
    return private_pem, public_pem

def encrypt_with_public_key(message: str, public_key_pem: str) -> str:
    """使用RSA公钥加密消息
    
    Args:
        message: 要加密的消息
        public_key_pem: PEM格式的公钥
        
    Returns:
        Base64编码的加密消息
    """
    try:
        # 加载公钥
        public_key = serialization.load_pem_public_key(
            public_key_pem.encode('utf-8'),
            backend=default_backend()
        )
        
        # 加密消息
        encrypted = public_key.encrypt(
            message.encode('utf-8'),
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        
        # Base64编码
        return base64.b64encode(encrypted).decode('utf-8')
    except Exception as e:
        logger.error(f"Encryption error: {str(e)}")
        raise

def decrypt_with_private_key(encrypted_message: str, private_key_pem: str = None) -> str:
    """使用RSA私钥解密消息
    
    Args:
        encrypted_message: Base64编码的加密消息
        private_key_pem: PEM格式的私钥,默认从应用配置获取
        
    Returns:
        解密后的消息
    """
    try:
        # 如果未提供私钥，从应用配置获取
        if not private_key_pem and current_app:
            private_key_pem = current_app.config.get('RSA_PRIVATE_KEY')
            
        if not private_key_pem:
            raise ValueError("未提供私钥")
            
        # 加载私钥
        private_key = serialization.load_pem_private_key(
            private_key_pem.encode('utf-8'),
            password=None,
            backend=default_backend()
        )
        
        # Base64解码
        encrypted = base64.b64decode(encrypted_message)
        
        # 尝试使用OAEP填充解密
        try:
            decrypted = private_key.decrypt(
                encrypted,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
        except Exception as oaep_error:
            # 如果OAEP解密失败，尝试使用PKCS#1 v1.5填充解密
            try:
                decrypted = private_key.decrypt(
                    encrypted,
                    padding.PKCS1v15()
                )
                logger.info("使用PKCS#1 v1.5填充解密成功")
            except Exception as pkcs_error:
                # 如果两种方法都失败，记录详细错误并重新抛出原始异常
                logger.error(f"OAEP解密失败: {str(oaep_error)}")
                logger.error(f"PKCS#1 v1.5解密失败: {str(pkcs_error)}")
                raise oaep_error
        
        return decrypted.decode('utf-8')
    except Exception as e:
        logger.error(f"Decryption error: {str(e)}")
        raise
def save_keys_to_files(private_key: str, public_key: str, private_key_path: str, public_key_path: str) -> None:
    """将RSA密钥保存到文件
    
    Args:
        private_key: 私钥PEM字符串
        public_key: 公钥PEM字符串
        private_key_path: 私钥文件路径
        public_key_path: 公钥文件路径
    """
    try:
        # 确保目录存在
        os.makedirs(os.path.dirname(private_key_path), exist_ok=True)
        os.makedirs(os.path.dirname(public_key_path), exist_ok=True)
        
        # 写入私钥
        with open(private_key_path, 'w') as f:
            f.write(private_key)
        
        # 写入公钥
        with open(public_key_path, 'w') as f:
            f.write(public_key)
            
        logger.info(f"RSA keys saved to {private_key_path} and {public_key_path}")
    except Exception as e:
        logger.error(f"Failed to save RSA keys to files: {str(e)}")
        raise

def load_key_from_file(key_path: str) -> str:
    """从文件加载RSA密钥
    
    Args:
        key_path: 密钥文件路径
        
    Returns:
        密钥PEM字符串
    """
    try:
        with open(key_path, 'r') as f:
            return f.read()
    except Exception as e:
        logger.error(f"Failed to load key from {key_path}: {str(e)}")
        raise

def init_rsa_keys(app) -> None:
    """初始化RSA密钥对并存储到应用配置
    
    Args:
        app: Flask应用实例
    """
    print( "init_rsa_keys" )
    try:
        # 检查是否已配置
        if app.config.get('RSA_PRIVATE_KEY') and app.config.get('RSA_PUBLIC_KEY'):
            logger.info("RSA keys already configured")
            return
        
        # 从文件加载密钥(如果文件存在)
        instance_path = app.instance_path
        private_key_path = os.path.join(instance_path, 'keys', 'rsa_private.pem')
        public_key_path = os.path.join(instance_path, 'keys', 'rsa_public.pem')
        
        if os.path.exists(private_key_path) and os.path.exists(public_key_path):
            private_key = load_key_from_file(private_key_path)
            public_key = load_key_from_file(public_key_path)
        else:
            # 生成新的密钥对
            private_key, public_key = generate_rsa_keys()
            
            # 保存到文件
            os.makedirs(os.path.join(instance_path, 'keys'), exist_ok=True)
            save_keys_to_files(
                private_key=private_key, 
                public_key=public_key,
                private_key_path=private_key_path,
                public_key_path=public_key_path
            )
        
        # 存储到应用配置
        app.config['RSA_PRIVATE_KEY'] = private_key
        app.config['RSA_PUBLIC_KEY'] = public_key

        logger.info("RSA keys initialized successfully")
    except Exception as e:
  
        logger.error(f"Failed to initialize RSA keys: {str(e)}")
        # 使用应急密钥对
        private_key, public_key = generate_rsa_keys()
        app.config['RSA_PRIVATE_KEY'] = private_key
        app.config['RSA_PUBLIC_KEY'] = public_key
        logger.warning("Using temporary RSA keys")